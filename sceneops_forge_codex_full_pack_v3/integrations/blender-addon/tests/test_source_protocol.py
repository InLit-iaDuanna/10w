import unittest
from datetime import datetime, timedelta, timezone
from sceneops_blender.agent_protocol import validate_command


class SourceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.binding = dict(task_id="task", grant_id="grant", project_id="project", workspace_root="/tmp/test", allowed_capabilities=["blender.asset.edit"], expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat())
        self.command = dict(operation="edit_nodes", request_id="request", candidate_id="candidate", asset_id="asset", edits=[dict(node_id="leaf", dimensions_m=[1, 0.2, 2])], authorization=dict(self.binding, action_id="action", change_set_id="change", approval_id="approval", capability_id="blender.asset.edit"))

    def test_bounded_stable_node_edit(self):
        validate_command(self.command, self.binding)
        for edits in ([dict(node_id="leaf", python="bad")], [dict(node_id="leaf", dimensions_m=[1, float("nan"), 2])], [dict(node_id="leaf", base_color=[2, 0, 0, 1])], []):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                validate_command(dict(self.command, edits=edits), self.binding)

    def test_paths_and_grant_cannot_be_supplied(self):
        for change in (dict(candidate_id="../source"), dict(source_path="/tmp/source.blend"), dict(authorization=dict(self.command["authorization"], capability_id="blender.asset.begin"))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_command(dict(self.command, **change), self.binding)
