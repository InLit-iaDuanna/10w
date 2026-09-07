"""Node adoption is tested without replacing any live acceptance evidence."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import sceneops_blender.agent_protocol as protocol


class SourceIdentityTests(unittest.TestCase):
    def adopt(self, objects):
        spec = importlib.util.spec_from_file_location('source_identity_test', Path(protocol.__file__).with_name('agent_source.py'))
        module = importlib.util.module_from_spec(spec)
        bpy = types.SimpleNamespace(context=types.SimpleNamespace(scene=types.SimpleNamespace(objects=objects)))
        with patch.dict(sys.modules, {'bpy': bpy}):
            spec.loader.exec_module(module)
            module.identify_scene('asset')

    def test_adopts_new_nodes_and_preserves_ids(self):
        old, new = {'sceneops_id': 'node_old', 'asset_id': 'asset'}, {}
        self.adopt([old, new])
        self.assertEqual(old['sceneops_id'], 'node_old')
        self.assertEqual(new['asset_id'], 'asset')
        self.assertTrue(new['sceneops_id'].startswith('node_'))
        identity = new['sceneops_id']
        self.adopt([old, new])
        self.assertEqual(new['sceneops_id'], identity)

    def test_foreign_and_duplicate_identities_rejected_before_adoption(self):
        for existing in ([{'asset_id': 'foreign'}], [{'sceneops_id': 'duplicate'}, {'sceneops_id': 'duplicate'}]):
            new = {}
            with self.assertRaises(ValueError):
                self.adopt([new, *existing])
            self.assertEqual(new, {})


class GrantContentTests(unittest.TestCase):
    def test_new_grant_owns_distinct_content_and_does_not_rebind_old_session(self):
        import tempfile
        from datetime import datetime, timedelta, timezone
        from sceneops_blender import BlenderAgentSession
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            source = workspace / "assets" / "registered.blend"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"BLENDER-fixture")
            binding = dict(task_id="task", project_id="project", grant_id="grant_one", workspace_root=str(workspace), allowed_capabilities=["blender.scene.inspect"], expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat())
            first = BlenderAgentSession(workspace, root / "state_one", grant_content=True)
            first.bind_authorization(binding)
            second = BlenderAgentSession(workspace, root / "state_two", grant_content=True)
            second.bind_authorization(dict(binding, grant_id="grant_two"))
            self.assertNotEqual(first.content_root, second.content_root)
            staged = Path(second.register_source("candidate", source))
            self.assertEqual(staged.read_bytes(), source.read_bytes())
            self.assertTrue(staged.is_relative_to(second.content_root))
            with self.assertRaises(ValueError):
                first.bind_authorization(dict(binding, grant_id="grant_two"))
