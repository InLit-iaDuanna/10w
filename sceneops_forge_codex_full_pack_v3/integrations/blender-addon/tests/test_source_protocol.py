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

    def test_imported_hierarchical_object_identity_is_not_a_file_path(self):
        for identity in ('sceneops-haven-kit/world-arena/cart/bottle.001', '模型:身体/面罩'):
            validate_command(dict(self.command, edits=[dict(node_id=identity, dimensions_m=[.12,.12,.25])]), self.binding)
        for identity in ('', 'bad\nidentifier', 'a' * 1025):
            with self.assertRaises(ValueError):
                validate_command(dict(self.command, edits=[dict(node_id=identity, dimensions_m=[1,1,1])]), self.binding)

    def test_local_rejection_is_explicitly_not_dispatched(self):
        from pathlib import Path
        from sceneops_blender import BlenderAgentSession, BlenderCommandRejected
        session = BlenderAgentSession(Path('/tmp/test'), Path('/tmp/test-state'))
        session.bind_authorization(self.binding)
        with self.assertRaises(BlenderCommandRejected):
            session.edit_nodes(**{key:value for key,value in dict(self.command,
                edits=[dict(node_id='bad\nidentity', dimensions_m=[1,1,1])]).items() if key!='operation'})

    def test_registered_glb_transfer_retains_exact_identity_bytes(self):
        import tempfile
        from pathlib import Path
        from sceneops_blender import BlenderAgentSession
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            session=BlenderAgentSession(root/'workspace',root/'state')
            data=b'glTF-fixture-with-hierarchical-identities'
            output=Path(session.register_glb('candidate',data))
            self.assertEqual(output.read_bytes(),data)
            with self.assertRaises(ValueError):session.register_glb('../other',data)
            with self.assertRaises(ValueError):session.register_glb('candidate',data)


class UnityDerivationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.binding = dict(task_id="task", grant_id="grant", project_id="project", workspace_root="/tmp/test", allowed_capabilities=["blender.asset.derive_unity"], expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat())
        self.command = dict(operation="derive_unity", request_id="request", candidate_id="candidate", asset_id="asset", authorization=dict(self.binding, action_id="action", change_set_id="change", approval_id="approval", capability_id="blender.asset.derive_unity"))

    def test_derivation_requires_its_exact_capability_and_no_paths(self):
        validate_command(self.command, self.binding)
        for change in (dict(candidate_id="../source"), dict(source_path="/tmp/source.blend"), dict(formats=["fbx"]), dict(authorization=dict(self.command["authorization"], capability_id="blender.asset.publish"))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_command(dict(self.command, **change), self.binding)

    def test_dry_run_writes_only_candidate_fbx_without_connecting(self):
        from pathlib import Path
        from sceneops_blender.agent_session import BlenderAgentSession
        session = BlenderAgentSession(Path('/tmp/test'), Path('/tmp/test-state'))
        session.bind_authorization(self.binding)
        result = session.derive_unity(**{key: value for key, value in self.command.items() if key != 'operation'}, dry_run=True)
        self.assertEqual(result['would_write'], [str(session.content_root / 'candidate.fbx')])

class GlbImportProtocolSmoke(unittest.TestCase):
    def test_import_accepts_only_registered_candidate_and_begin_grant(self):
        binding=dict(task_id='task',grant_id='grant',project_id='project',workspace_root='/tmp/model',
            allowed_capabilities=['blender.asset.begin'],expires_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
        command=dict(operation='import_source',request_id='request',asset_id='asset',candidate_id='candidate',
            authorization=dict(binding,action_id='action',change_set_id='change',approval_id='approval',capability_id='blender.asset.begin'))
        validate_command(command,binding)
        with self.assertRaises(ValueError):validate_command(dict(command,path='/tmp/unregistered.glb'),binding)
        with self.assertRaises(ValueError):validate_command(dict(command,candidate_id='../candidate'),binding)
