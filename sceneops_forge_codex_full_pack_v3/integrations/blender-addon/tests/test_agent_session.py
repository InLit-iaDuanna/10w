from __future__ import annotations

import tempfile
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from sceneops_blender import BlenderAgentSession
from sceneops_blender.agent_protocol import validate_binding, validate_command
from sceneops_blender.agent_session import sandbox_profile


def grant(root):
    return {"task_id": "task_test", "grant_id": "grant_test", "project_id": "project_test",
            "workspace_root": str(root), "allowed_capabilities": ["blender.scene.inspect", "blender.asset.create", "blender.asset.export"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()}


class AgentProtocolTests(unittest.TestCase):
    def setUp(self):
        self.binding = grant(Path("/tmp/owned"))
        self.command = {"operation": "create_asset", "request_id": "request_one", "asset_id": "asset_one",
                        "sceneops_id": "object_one", "dimensions_m": [1, 2, 3],
                        "authorization": {**self.binding, "action_id": "action_one", "change_set_id": "change_one",
                                          "approval_id": "approval_one", "capability_id": "blender.asset.create"}}

    def test_strict_bounded_command_and_grant(self):
        validate_binding(self.binding)
        validate_command(self.command, self.binding)
        for field, value in [("asset_id", "../escape"), ("dimensions_m", [1, float("nan"), 2]),
                             ("dimensions_m", [1, 2, True]), ("operation", "execute_python")]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_command({**self.command, field: value}, self.binding)
        with self.assertRaises(ValueError):
            validate_command({**self.command, "path": "/tmp/escape"}, self.binding)

    def test_authorization_scope_and_expiry(self):
        for key, value in [("task_id", "another_task"), ("grant_id", "another_grant"),
                           ("workspace_root", "/tmp/another"), ("capability_id", "blender.asset.export"),
                           ("change_set_id", ""), ("approval_id", "")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command({**self.command, "authorization": {**self.command["authorization"], key: value}}, self.binding)
        expired = {**self.binding, "expires_at": "2000-01-01T00:00:00Z"}
        with self.assertRaises(ValueError):
            validate_binding(expired)

    def test_inspection_requires_live_read_grant_but_cleanup_can_expire(self):
        validate_command({"operation": "inspect"}, self.binding)
        for binding in ({}, {**self.binding, "expires_at": "2000-01-01T00:00:00Z"},
                        {**self.binding, "allowed_capabilities": ["blender.asset.create"]}):
            with self.assertRaises(ValueError):
                validate_command({"operation": "inspect"}, binding)
        validate_command({"operation": "stop"}, {**self.binding, "expires_at": "2000-01-01T00:00:00Z"})

    def test_expired_cleanup_never_reads_or_returns_scene_information(self):
        import sceneops_blender.agent_protocol as protocol
        module_path = Path(protocol.__file__).with_name("agent_host.py")
        spec = importlib.util.spec_from_file_location("agent_host_stop_test", module_path)
        module = importlib.util.module_from_spec(spec)
        dispatcher = types.ModuleType("sceneops_forge_blender.dispatcher")
        dispatcher.dispatch = Mock()
        with patch.dict(sys.modules, {"bpy": types.ModuleType("bpy"), "agent_protocol": protocol,
                                     "sceneops_forge_blender.dispatcher": dispatcher}):
            spec.loader.exec_module(module)
        host = module.AgentHost.__new__(module.AgentHost)
        host.config = {"session_id": "session_test", "binding": {**self.binding, "expires_at": "2000-01-01T00:00:00Z"}}
        host.inspect = Mock(side_effect=AssertionError("cleanup must not read scene"))
        result = host.dispatch({"operation": "stop"})
        self.assertEqual(result, {"mode": "live", "session_id": "session_test", "status": "stopped"})
        self.assertTrue(host.stopping)
        host.inspect.assert_not_called()

    def test_no_start_without_bound_server_grant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = BlenderAgentSession(root / "workspace", root / "state")
            with self.assertRaises(ValueError):
                session.start()
            with self.assertRaises(ValueError):
                session.bind_authorization(grant(root / "other"))
            session.bind_authorization(grant(root / "workspace"))
            with self.assertRaises(ValueError):
                session.bind_authorization({**grant(root / "workspace"), "task_id": "other"})

    def test_profile_restricts_writes_and_external_network(self):
        result = sandbox_profile(Path("/tmp/work"), Path("/tmp/state"),
                                 Path("/Applications/Blender.app/Contents/MacOS/Blender"), Path("/tmp/source"))
        self.assertIn("(deny default)", result)
        self.assertIn('(allow file-read* file-write* (subpath "/tmp/work"))', result)
        self.assertNotIn('(allow file-write* (subpath "/Users"))', result)
        self.assertIn('(allow network-outbound (remote ip "localhost:*"))', result)

    def test_dry_run_does_not_create_files_or_start_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binding = grant(root / "workspace")
            session = BlenderAgentSession(root / "workspace", root / "state")
            session.bind_authorization(binding)
            auth = {**self.command["authorization"], **binding}
            result = session.create_asset(request_id="request_one", asset_id="asset_one", sceneops_id="object_one",
                                          dimensions_m=[1, 2, 3], authorization=auth, dry_run=True)
            self.assertEqual(result["mode"], "planned")
            self.assertEqual(list(root.iterdir()), [])

    def test_new_session_rejects_existing_content_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = root / "workspace/blender"
            content.mkdir(parents=True)
            (content / "user.blend").touch()
            session = BlenderAgentSession(root / "workspace", root / "state")
            session.bind_authorization(grant(root / "workspace"))
            with self.assertRaisesRegex(ValueError, "empty Blender"):
                session.start()


if __name__ == "__main__":
    unittest.main()
