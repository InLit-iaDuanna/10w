import json
import tempfile
import unittest
from pathlib import Path
from pydantic import ValidationError
from engine_unity.agent_session import UnityAgentSessionError
from engine_unity.content_contracts import ContentNodes, ContentEdit, ContentInput
from engine_unity.content_session import edit_content, import_content

class Session:
    def __init__(self, root):
        self.workspace_root = root
        self.project_root = root / 'unity'
        self.mailbox = self.project_root / '.sceneops-agent'
        self.mailbox.mkdir(parents=True)
        self._config = {'session_id': 'session'}
        self.sent = []
    def _validate_grant(self, authorization=None):
        pass
    def _exchange(self, request_id, command, **kwargs):
        self.sent.append((command, kwargs))
        return {'session_id': 'session', 'revision': 'r1', 'run_id': '', 'instances': []}

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(Path(self.directory.name).resolve())
    def auth(self, capability):
        return {'capability_id': capability, 'action_id': 'action', 'change_set_id': 'change', 'approval_id': 'approval'}
    def test_edit_binds_previous_fields_and_false_boolean(self):
        edit_content(self.session, request_id='edit1', instance_id='inst_one', expected={
            'position': [1, 2, 3], 'interaction_distance': 2, 'requires_key': True},
            requires_key=False, authorization=self.auth('unity.content.edit'))
        command, sent = self.session.sent[-1]
        payload = json.loads(sent['batch']['payloadJson'])
        self.assertEqual(command, 'unity.content.edit')
        self.assertTrue(payload['set_requires_key'])
        self.assertFalse(payload['requires_key'])
        self.assertEqual(payload['expected']['position'], [1, 2, 3])
    def test_import_retains_old_version_and_rejects_changed_same_version(self):
        source = self.session.workspace_root / 'derived.fbx'
        source.write_bytes(b'actual-derived-fixture')
        params = dict(request_id='i1', asset_id='libasset_one', source_version='1', expected_source_version='', fbx_path=source,
            node_ids={'frame': 'frame', 'leaf': 'leaf', 'hinge': 'hinge'}, instance_ids=['inst_one', 'inst_two'],
            authorization=self.auth('unity.content.import'))
        import_content(self.session, **params)
        params.update(request_id='i2', source_version='2', expected_source_version='1')
        source.write_bytes(b'new-derived-fixture')
        import_content(self.session, **params)
        staging = self.session.project_root / 'Staging/Content/libasset_one'
        self.assertEqual((staging / '1/model.fbx').read_bytes(), b'actual-derived-fixture')
        self.assertEqual((staging / '2/model.fbx').read_bytes(), b'new-derived-fixture')
        source.write_bytes(b'changed-registered-version')
        with self.assertRaises(UnityAgentSessionError) as error:
            import_content(self.session, **params)
        self.assertEqual(error.exception.code, 'UNITY_VERSION_CONFLICT')
    def test_node_identity_and_input_constraints(self):
        with self.assertRaises(ValidationError):
            ContentNodes(frame='same', leaf='same', hinge='pivot')
        with self.assertRaises(ValidationError):
            ContentInput(move_x=float('nan'))
        with self.assertRaises(ValidationError):
            ContentInput(duration_frames=121)
        with self.assertRaises(ValidationError):
            ContentEdit(instance_id='i', expected={'position': [0,0,0], 'interaction_distance':2, 'requires_key':True}, component_type='arbitrary')
    def test_wrong_capability_cannot_stage_content(self):
        with self.assertRaises(UnityAgentSessionError) as error:
            import_content(self.session, request_id='i', asset_id='asset', source_version='1', expected_source_version='',
                fbx_path='/outside.fbx', node_ids={}, instance_ids=[], authorization=self.auth('unity.content.edit'))
        self.assertEqual(error.exception.code, 'UNITY_AGENT_AUTH_DENIED')
        self.assertFalse((self.session.project_root / 'Staging').exists())

if __name__ == '__main__': unittest.main()
