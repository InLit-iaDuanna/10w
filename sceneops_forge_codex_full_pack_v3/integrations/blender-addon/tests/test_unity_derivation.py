"""Unit evidence for bounded derivation; live Blender/Unity acceptance is separate."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sceneops_blender.agent_protocol as protocol


class UnityDerivationTests(unittest.TestCase):
    def test_exports_properties_without_saving_or_repairing_source(self):
        class Object(dict):
            type = 'MESH'
            parent = None
            select_set = Mock()
        objects = [Object(asset_id='asset', sceneops_id='leaf', sceneops_role='leaf')]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'candidate.blend'
            source.write_bytes(b'immutable published source copy')
            bpy = types.SimpleNamespace(context=types.SimpleNamespace(scene=types.SimpleNamespace(objects=objects), view_layer=types.SimpleNamespace(update=Mock())), ops=types.SimpleNamespace(wm=types.SimpleNamespace(open_mainfile=Mock(), save_as_mainfile=Mock()), object=types.SimpleNamespace(select_all=Mock()), export_scene=types.SimpleNamespace(fbx=Mock())))
            host = types.SimpleNamespace(root=root)
            spec = importlib.util.spec_from_file_location('unity_source_test', Path(protocol.__file__).with_name('agent_source.py'))
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'bpy': bpy, 'agent_protocol': protocol, 'agent_host': types.SimpleNamespace(contained=lambda root, name: root / name)}):
                spec.loader.exec_module(module)
                result = module.derive_unity(host, dict(asset_id='asset', candidate_id='candidate'))
            self.assertEqual(source.read_bytes(), b'immutable published source copy')
            bpy.ops.wm.save_as_mainfile.assert_not_called()
            self.assertEqual(result['fbx_relative_path'], 'candidate.fbx')
            self.assertTrue(bpy.ops.export_scene.fbx.call_args.kwargs['use_custom_props'])
            self.assertEqual(objects[0]['sceneops_id'], 'leaf')
