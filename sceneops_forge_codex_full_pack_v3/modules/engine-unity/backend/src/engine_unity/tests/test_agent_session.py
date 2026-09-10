"""Task-session boundaries and durable IPC without launching Unity."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from engine_unity.agent_session import UnityAgentSession, UnityAgentSessionError, PACKAGE, _inside, _write


class AgentSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve() / 'prj_test'
        self.root.mkdir()
        self.session = UnityAgentSession(self.root, self.root / 'state')
        self.grant = dict(task_id='task_test', grant_id='grant_test', project_id='prj_test',
                          workspace_root=str(self.root), allowed_capabilities=['unity.asset.import', 'unity.scene.inspect'],
                          expires_at=(datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
        self.session.bind_authorization(self.grant)
        self.native_init = patch.object(UnityAgentSession, '_initialize_project', self.create_fixture_project)
        self.native_init.start()
        self.addCleanup(self.native_init.stop)

    @staticmethod
    def create_fixture_project(session, timeout=180):
        for name in ('Assets', 'Packages', 'ProjectSettings'):
            (session.project_root / name).mkdir(parents=True, exist_ok=True)
        (session.project_root / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 2022.3.62f3c1\n')
        _write(session.project_root / 'Packages/manifest.json', {'dependencies': {'com.unity.modules.physics': '1.0.0'}})

    def tearDown(self):
        self.temporary.cleanup()

    def test_prepare_creates_only_dedicated_empty_project_and_private_mailbox(self):
        self.session._prepare()
        self.assertEqual(list((self.root / 'unity/Assets').iterdir()), [])
        self.assertEqual(self.session.mailbox.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.session.mailbox / 'session.json').stat().st_mode & 0o777, 0o600)
        manifest = json.loads((self.root / 'unity/Packages/manifest.json').read_text())
        self.assertIn('com.sceneops.forge.unity', manifest['dependencies'])
        self.assertEqual(manifest['dependencies']['com.sceneops.forge.unity'], 'file:' + str(PACKAGE))
        self.assertFalse((self.root / 'unity/Packages/com.sceneops.forge.unity').exists())
        restored = UnityAgentSession(self.root, self.root / 'state')
        restored.bind_authorization(self.grant)
        restored._prepare()
        self.assertEqual(restored._config, self.session._config)

    def test_existing_project_not_adopted(self):
        (self.root / 'unity/Assets').mkdir(parents=True)
        with self.assertRaises(UnityAgentSessionError):
            self.session._prepare()

    def test_symlink_and_traversal_rejected(self):
        (self.root / 'link').symlink_to(self.root.parent, target_is_directory=True)
        for path in (self.root / 'link/file', self.root / '../outside', self.root.parent / 'outside'):
            with self.assertRaises(UnityAgentSessionError):
                _inside(path, self.root)

    def test_expired_and_changed_scope_rejected(self):
        with self.assertRaises(UnityAgentSessionError):
            self.session.bind_authorization({**self.grant, 'workspace_root': str(self.root.parent)})
        with self.assertRaises(UnityAgentSessionError):
            self.session._validate_grant({**self.grant, 'capability_id': 'unity.build.run'})
        with self.assertRaises(UnityAgentSessionError):
            self.session.bind_authorization({**self.grant, 'expires_at': '2020-01-01T00:00:00Z'})

    def test_durable_request_replay_rejects_different_inputs(self):
        self.session._prepare()
        _write(self.session.mailbox / 'req_test.result.json', {'status': 'succeeded', 'resultJson': '{"connected":true}'})
        self.assertTrue(self.session._exchange('req_test', 'inspect')['connected'])
        self.assertTrue(self.session._exchange('req_test', 'inspect')['connected'])
        with self.assertRaises(UnityAgentSessionError):
            self.session._exchange('req_test', 'unity.asset.import')

    def test_cancellation_is_visible(self):
        self.session._prepare()
        self.session.stop()
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._exchange('req_cancel', 'inspect')
        self.assertEqual(error.exception.code, 'UNITY_CANCELLED')

    def test_license_blocker_is_immediate_even_after_editor_exits(self):
        self.session._prepare()
        (self.session.mailbox / 'editor.log').write_text('No valid Unity Editor license found. Please activate your license.\n')
        self.session._process = Mock()
        self.session._process.poll.return_value = 1
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._exchange('req_license', 'inspect')
        self.assertEqual(error.exception.code, 'UNITY_LICENSE_REQUIRED')
        self.assertNotIn(self.session._config['token'], str(error.exception))

    def test_failure_log_redacts_private_session_token(self):
        self.session._prepare()
        token = self.session._config['token']
        (self.session.mailbox / 'editor.log').write_text('error CS1000: ' + token)
        self.assertNotIn(token, self.session._failure_reason())
        self.assertIn('[redacted]', self.session._failure_reason())

    def test_import_requires_action_record_before_staging(self):
        self.session.inspect = Mock(return_value={'session_id': 'session_test'})
        auth = {**self.grant, 'change_set_id': 'chg_test', 'approval_id': 'approval_test', 'capability_id': 'unity.asset.import'}
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session.import_asset(request_id='req_test', asset_id='ast_test', sceneops_id='obj_test',
                fbx_path=self.root / 'model.fbx', manifest_path=self.root / 'model.json', authorization=auth)
        self.assertEqual(error.exception.code, 'UNITY_AGENT_AUTH_DENIED')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_compilation_waits_for_ready_state(self):
        ready = {'compiling': False, 'capabilities': ['unity.asset.import']}
        self.session._inspect = Mock(side_effect=[{'compiling': True, 'capabilities': []}, ready])
        with patch('engine_unity.agent_session.time.sleep'):
            self.assertEqual(self.session._wait_ready(10), ready)
        self.assertEqual(self.session._inspect.call_count, 2)

    def test_started_import_timeout_is_uncertain_and_failure_result_is_retained(self):
        self.session._prepare()
        _write(self.session.mailbox / 'req_uncertain.started.json', {'status': 'started'})
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._exchange('req_uncertain', 'unity.asset.import', timeout=0)
        self.assertEqual(error.exception.code, 'UNITY_OUTCOME_UNCERTAIN')
        failed = {'status': 'failed', 'error_code': 'UNITY_OUTCOME_UNCERTAIN', 'message': 'scene save failed'}
        result = self.session.mailbox / 'req_uncertain.result.json'
        _write(result, failed)
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._exchange('req_uncertain', 'unity.asset.import')
        self.assertEqual(error.exception.code, 'UNITY_OUTCOME_UNCERTAIN')
        self.assertEqual(json.loads(result.read_text()), failed)

    def test_mailbox_result_symlink_cannot_read_outside_workspace(self):
        self.session._prepare()
        target = self.root.parent / 'foreign.json'
        target.write_text('{"private":true}')
        (self.session.mailbox / 'req_foreign.result.json').symlink_to(target)
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._exchange('req_foreign', 'inspect')
        self.assertEqual(error.exception.code, 'UNITY_PATH_OUTSIDE_PROJECT')

    def test_old_embedded_package_is_retained_and_fixed_bundle_is_selected(self):
        self.session._prepare()
        embedded = self.root / 'unity/Packages/com.sceneops.forge.unity'
        embedded.mkdir()
        (embedded / 'owned.txt').write_text('previous package')
        self.session._configure_package()
        self.assertFalse(embedded.exists())
        backups = list(self.session.mailbox.glob('bundled-package.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'owned.txt').read_text(), 'previous package')

    def test_readiness_diagnostic_excludes_license_success_and_update_checks(self):
        self.session._prepare()
        (self.session.mailbox / 'editor.log').write_text('[Project] Loading completed in 8 seconds\n'
            '[Licensing::Client] Successfully resolved entitlement details\n'
            '[Licensing::Module] Successfully updated access token: "secret-prefix"\n'
            'EditorUpdateCheck: Failed The requested URL returned error: 404\n')
        reason = self.session._failure_reason()
        self.assertIn('UNITY_SESSION_TIMEOUT', reason)
        self.assertIn('bridge assembly was not imported', reason)
        self.assertNotIn('secret-prefix', reason)
        self.assertNotIn('Licensing', reason)
        self.assertNotIn('404', reason)

    def test_start_rejects_launcher_log_symlink_before_spawning(self):
        self.session._prepare()
        outside = self.root.parent / 'foreign-launcher.log'
        outside.write_text('unchanged')
        (self.session.mailbox / 'launcher.log').symlink_to(outside)
        self.session.executable = Path(__file__)
        self.session._inspect = Mock(side_effect=UnityAgentSessionError('UNITY_SESSION_TIMEOUT', 'not started'))
        with patch('engine_unity.agent_session.subprocess.Popen') as spawn:
            with self.assertRaises(UnityAgentSessionError) as error:
                self.session.start()
        self.assertEqual(error.exception.code, 'UNITY_PATH_OUTSIDE_PROJECT')
        spawn.assert_not_called()
        self.assertEqual(outside.read_text(), 'unchanged')


if __name__ == '__main__':
    unittest.main()
