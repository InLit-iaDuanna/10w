"""Real service lifecycle with a controlled native port; never installs tools."""
import json
import time
import zipfile
from pathlib import Path
import unittest
from . import test_exports as fixtures
from build_release import ExportMessageRequest


class NativePort:
    def __init__(self):
        self.context = None
        self.hold = False
        self.report = True
        self.escape = False
        self.started = False
    def prepare(self, context, content, provider, model):
        self.context = context
        return 'native-task-1'
    def run(self, agent_id, emit, cancel):
        self.started = True
        emit('tool', 'checking local tools')
        while self.hold and not cancel.wait(.01):
            pass
        workspace = Path(self.context['workspace_root'])
        (workspace / 'repair.txt').write_text('preserved')
        if self.report:
            package = workspace / '可玩 游戏.zip'
            with zipfile.ZipFile(package, 'w') as archive:
                archive.writestr('Game.exe', b'MZfixture')
            path = '../outside.zip' if self.escape else package.name
            (workspace / 'sceneops-export-result.json').write_text(json.dumps({'artifacts': [{'platform': 'win-x64', 'path': path}]}))
        return {'status': 'succeeded', 'content': 'packaged'}


class NativeExportTests(unittest.TestCase):
    setUp = fixtures.ExportTests.setUp
    tearDown = fixtures.ExportTests.tearDown
    resolve = fixtures.ExportTests.resolve
    wait = fixtures.ExportTests.wait
    create = fixtures.ExportTests.create
    def wait_native(self, task_id):
        end = time.monotonic() + 3
        while time.monotonic() < end:
            task = self.service.get('p1', task_id)
            if task.native_runs and task.native_runs[-1].status not in ('queued', 'running'):
                return task
            time.sleep(.01)
        self.fail('native worker did not stop')
    def launch(self, task_id):
        return self.service.message('p1', task_id, ExportMessageRequest(content='修复并导出', execution_mode='native', accept_full_access=True))
    def test_native_link_events_manifest_and_immutable_download(self):
        task = self.wait(self.create(['win-x64']).id)
        port = self.service.native_agent = NativePort()
        self.launch(task.id)
        task = self.wait_native(task.id)
        self.assertEqual(task.native_runs[-1].agent_task_id, 'native-task-1')
        self.assertEqual(task.native_runs[-1].logs[0].message, 'checking local tools')
        self.assertEqual(task.platforms[0].status, 'succeeded')
        self.assertEqual(task.platforms[0].verification, 'pending')
        artifact = task.platforms[0].attempts[-1].artifacts[0]
        stored = self.service.artifact('p1', task.id, artifact.id)
        original = stored.read_bytes()
        (Path(port.context['workspace_root']) / artifact.name).write_text('changed')
        self.assertEqual(stored.read_bytes(), original)
        self.assertNotEqual(port.context['source_path'], str(self.source))
        port.report = False
        self.launch(task.id)
        task = self.wait_native(task.id)
        self.assertEqual(len(task.platforms[0].attempts), 2)
        self.assertTrue((Path(port.context['workspace_root']) / 'repair.txt').exists())
    def test_native_cancel_and_mutual_exclusion(self):
        task = self.wait(self.create(['win-x64']).id)
        port = self.service.native_agent = NativePort()
        port.hold = True
        self.launch(task.id)
        with self.assertRaisesRegex(ValueError, 'Agent'):
            self.service.continue_platform('p1', task.id, 'win-x64')
        with self.assertRaises(ValueError):
            self.launch(task.id)
        self.service.cancel_native('p1', task.id)
        task = self.wait_native(task.id)
        self.assertEqual(task.native_runs[-1].status, 'cancelled')
        self.assertTrue(task.native_runs[-1].cancel_requested)
        self.assertEqual(task.platforms[0].status, 'failed')
    def test_native_requires_explicit_authorization_and_rejects_escape(self):
        task = self.wait(self.create(['win-x64']).id)
        with self.assertRaises(ValueError):
            self.service.message('p1', task.id, ExportMessageRequest(content='go', execution_mode='native'))
        port = self.service.native_agent = NativePort()
        port.escape = True
        self.launch(task.id)
        task = self.wait_native(task.id)
        self.assertEqual(task.native_runs[-1].status, 'failed')
        self.assertFalse(task.platforms[0].attempts[-1].artifacts)

    def test_native_create_starts_agent_without_fixed_adapter(self):
        from build_release import CreateExportRequest
        self.service.native_agent = NativePort()
        task = self.service.create('p1', CreateExportRequest(platforms=['win-x64'], execution_mode='native', accept_full_access=True))
        task = self.wait_native(task.id)
        self.assertEqual(self.adapter.prepares, 0)
        self.assertEqual(task.platforms[0].status, 'succeeded')
        self.assertEqual(self.service.native_agent.context['platforms'], ['win-x64'])

    def test_restart_marks_native_interrupted_without_replay(self):
        from build_release.export_models import ExportNativeRun
        from build_release import ExportService
        task = self.wait(self.create(['win-x64']).id)
        task.native_runs.append(ExportNativeRun(id='unfinished', status='running', started_at=task.created_at))
        self.service._save(task)
        self.service.close()
        self.service = ExportService(self.root / 'exports', self.resolve, self.adapter)
        task = self.service.get('p1', task.id)
        self.assertEqual(task.native_runs[-1].status, 'interrupted')
        self.assertEqual(self.service.threads, [])
