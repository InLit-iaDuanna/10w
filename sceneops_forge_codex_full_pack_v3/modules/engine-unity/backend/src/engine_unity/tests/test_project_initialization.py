"""Native project creation lifecycle; Editor process is mocked, never launched."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from engine_unity.agent_session import UnityAgentSession, UnityAgentSessionError

class ProjectInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'prj_init'
        self.root.mkdir()
        self.session = UnityAgentSession(self.root, self.root / 'state')
        self.session.bind_authorization(dict(task_id='task', grant_id='grant', project_id='prj_init',
            workspace_root=str(self.root), allowed_capabilities=['unity.content.import'],
            expires_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()))

    def create(self, args, **kwargs):
        self.assertEqual(args[1:4], ['-batchmode', '-quit', '-createProject'])
        self.assertEqual(args[4], str(self.session.project_root))
        self.assertFalse((self.session.project_root / 'Packages/manifest.json').exists())
        for folder in ('Assets', 'ProjectSettings', 'Packages'):
            (self.session.project_root / folder).mkdir(parents=True, exist_ok=True)
        (self.session.project_root / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 2022.3.62f3c1\n')
        (self.session.project_root / 'Packages/manifest.json').write_text(json.dumps({'dependencies': {
            'com.unity.modules.animation': '1.0.0', 'com.unity.modules.ui': '1.0.0', 'com.unity.modules.physics': '1.0.0'}}))
        (self.root / 'unity-initialization.log').write_text('Created project')
        process=Mock(pid=123, returncode=0)
        process.poll.return_value=0
        return process

    def test_native_template_is_preserved_before_bundle_configuration(self):
        with patch('engine_unity.agent_session.subprocess.Popen', side_effect=self.create) as launch:
            self.session._prepare()
        self.assertEqual(launch.call_count, 1)
        manifest=json.loads((self.session.project_root / 'Packages/manifest.json').read_text())
        self.assertIn('com.unity.modules.animation', manifest['dependencies'])
        self.assertIn('com.unity.modules.ui', manifest['dependencies'])
        self.assertIn('com.sceneops.forge.unity', manifest['dependencies'])
        self.assertEqual(json.loads((self.root/'unity-initialization.json').read_text())['status'],'succeeded')
        self.assertIsNone(self.session._process)

    def test_timeout_stops_only_owned_creation_and_preserves_record(self):
        process=Mock(pid=456)
        process.poll.return_value=None
        def finish(timeout): process.poll.return_value=1
        process.wait.side_effect=finish
        with patch('engine_unity.agent_session.subprocess.Popen', return_value=process):
            with self.assertRaises(UnityAgentSessionError) as error:
                self.session._initialize_project(timeout=0)
        self.assertEqual(error.exception.code,'UNITY_INITIALIZATION_TIMEOUT')
        process.terminate.assert_called_once()
        self.assertEqual(json.loads((self.root/'unity-initialization.json').read_text())['status'],'failed')
        with self.assertRaises(UnityAgentSessionError) as error:
            self.session._initialize_project()
        self.assertEqual(error.exception.code,'UNITY_INITIALIZATION_INCOMPLETE')
