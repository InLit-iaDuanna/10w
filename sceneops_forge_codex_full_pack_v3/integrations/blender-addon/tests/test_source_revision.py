"""Deterministic tests of the native saved-file revision contract."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sceneops_blender.agent_protocol as protocol


class SourceRevisionTests(unittest.TestCase):
    def test_conflicting_disk_and_memory_preserves_both(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'candidate.blend'
            target.write_bytes(b'first version')
            scene = {'sceneops_candidate_id': 'candidate'}
            bpy = types.SimpleNamespace(context=types.SimpleNamespace(scene=scene),
                                        data=types.SimpleNamespace(is_dirty=True),
                                        ops=types.SimpleNamespace(wm=types.SimpleNamespace(open_mainfile=Mock())))
            spec = importlib.util.spec_from_file_location('source_revision_test', Path(protocol.__file__).with_name('agent_source.py'))
            module = importlib.util.module_from_spec(spec)
            host_module = types.SimpleNamespace(contained=lambda root, name: root / name)
            with patch.dict(sys.modules, {'bpy': bpy, 'agent_host': host_module}):
                spec.loader.exec_module(module)
                host = types.SimpleNamespace(root=root)
                module.remember_source(host, target)
                target.write_bytes(b'external saved geometry')
                self.assertTrue(module.source_state(host)['disk_changed'])
                with self.assertRaisesRegex(ValueError, 'BLENDER_SOURCE_CONFLICT'):
                    module.synchronize_source(host, {'candidate_id': 'candidate', 'asset_id': 'asset'})
                self.assertEqual(target.read_bytes(), b'external saved geometry')
                bpy.ops.wm.open_mainfile.assert_not_called()

    def test_missing_loaded_source_is_a_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'candidate.blend'
            target.write_bytes(b'first')
            spec = importlib.util.spec_from_file_location('source_revision_test', Path(protocol.__file__).with_name('agent_source.py'))
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'bpy': types.SimpleNamespace()}):
                spec.loader.exec_module(module)
                revision = module.file_revision(target)
                self.assertEqual(revision['size'], 5)
                target.unlink()
                self.assertIsNone(module.file_revision(target))
