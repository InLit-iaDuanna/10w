"""Deterministic export lifecycle/HTTP tests; no external build tools."""
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import shutil
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from build_release import (ExportService, CreateExportRequest, ExportMessageRequest,
    ExportVerificationRequest, ExportConsentRequest, create_export_router)


class FixtureAdapter:
    mode = 'mock'
    def __init__(self):
        self.fail = {'win-x64'}
        self.prepares = 0
        self.hold = False
    def prepare(self, source, work, settings, emit, cancel):
        self.prepares += 1
        target = work / 'web'
        target.mkdir(parents=True)
        (target / 'index.html').write_text((source / 'index.html').read_text())
        return target
    def build(self, platform, web, work, settings, emit, cancel):
        emit('packaging', 'fixture packaging')
        while self.hold and not cancel.wait(.01):
            pass
        if platform in self.fail:
            raise RuntimeError('fixture build failed')
        target = work / ('可玩 游戏.apk' if platform == 'android' else '可玩 游戏.zip')
        target.write_text((web / 'index.html').read_text())
        return [target]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / '中文 工程'
        self.source.mkdir()
        (self.source / 'index.html').write_text('<html>play</html>')
        (self.source / '.env').write_text('SECRET=never-copy')
        self.adapter = FixtureAdapter()
        self.service = ExportService(self.root / 'exports', self.resolve, self.adapter)
    def tearDown(self):
        self.service.close()
        self.temp.cleanup()
    def resolve(self, project_id):
        if project_id not in ('p1', 'p2'):
            raise KeyError(project_id)
        return {'root_path': str(self.source), 'name': '可玩游戏'}
    def wait(self, task_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            task = self.service.get('p1', task_id)
            if all(run.status not in ('queued', 'running') for run in task.platforms):
                return task
            time.sleep(.01)
        self.fail('fixture task did not finish')
    def create(self, platforms=None):
        return self.service.create('p1', CreateExportRequest(platforms=platforms or ['android', 'win-x64']))

    def test_partial_failure_retry_shared_source_and_download(self):
        task = self.create()
        (self.source / 'index.html').write_text('later source')
        task = self.wait(task.id)
        self.assertEqual([r.status for r in task.platforms], ['succeeded', 'failed'])
        self.assertEqual(self.adapter.prepares, 1)
        self.assertEqual(task.mode, 'mock')
        self.assertFalse((self.root / 'exports' / task.id / 'source' / '.env').exists())
        artifact = task.platforms[0].attempts[-1].artifacts[0]
        self.assertEqual(self.service.artifact('p1', task.id, artifact.id).read_text(), '<html>play</html>')
        with self.assertRaises(KeyError):
            self.service.artifact('p2', task.id, artifact.id)
        self.adapter.fail.clear()
        self.service.continue_platform('p1', task.id, 'win-x64')
        task = self.wait(task.id)
        self.assertEqual(task.platforms[1].status, 'succeeded')
        self.assertEqual(len(task.platforms[1].attempts), 2)
        self.assertEqual(task.platforms[1].verification, 'pending')
        self.assertEqual(self.adapter.prepares, 1)

    def test_cancel_persistence_and_manual_verification(self):
        self.adapter.hold = True
        task = self.create(['android'])
        self.service.cancel('p1', task.id, 'android')
        task = self.wait(task.id)
        self.assertEqual(task.platforms[0].status, 'cancelled')
        self.assertTrue(task.platforms[0].attempts[0].cancel_requested)
        self.adapter.hold = False
        self.service.continue_platform('p1', task.id, 'android')
        task = self.wait(task.id)
        attempt = task.platforms[0].attempts[-1]
        request = ExportVerificationRequest(status='passed', device='Pixel fixture', notes='manual test record', attempt_id=attempt.id)
        self.service.verify('p1', task.id, 'android', request)
        self.service.close()
        self.service = ExportService(self.root / 'exports', self.resolve, self.adapter)
        restored = self.service.get('p1', task.id)
        self.assertEqual(restored.platforms[0].verification_attempt_id, attempt.id)
        self.assertEqual(restored.platforms[0].verification, 'passed')
        request.attempt_id = 'other-attempt'
        with self.assertRaises(ValueError):
            self.service.verify('p1', task.id, 'android', request)

    def test_discussion_does_not_execute_structured_actions(self):
        task = self.wait(self.create(['win-x64']).id)
        self.service.agent_callback = lambda *args: {'content': '调整名称并重试', 'provider_id': 'fixture', 'model': 'fixture', 'usage': {'tokens': 1}, 'actions': [
            {'action': 'configure', 'settings': {'app_name': '新版'}}, {'action': 'continue', 'platform': 'win-x64'}]}
        task = self.service.message('p1', task.id, ExportMessageRequest(content='讨论'))
        self.assertEqual(len(task.platforms[0].attempts), 1)
        self.assertEqual(task.settings.app_name, '可玩游戏')
        self.assertEqual(task.messages[-1].model, 'fixture')
        self.assertEqual((self.source / 'index.html').read_text(), '<html>play</html>')

    def test_http_contract_download_and_unknown_project(self):
        app = FastAPI()
        app.include_router(create_export_router(self.service))
        client = TestClient(app)
        response = client.post('/api/projects/p1/exports', json={'platforms': ['android']})
        self.assertEqual(response.status_code, 200)
        task = self.wait(response.json()['id'])
        url = task.platforms[0].attempts[0].artifacts[0].download_url
        self.assertEqual(client.get(url).content, b'<html>play</html>')
        self.assertEqual(client.get('/api/projects/p2/exports/' + task.id).status_code, 404)
        self.assertEqual(client.post('/api/projects/p1/exports', json={'platforms': ['shell']}).status_code, 422)
        schemas = app.openapi()['components']['schemas']
        self.assertIn('ExportVerificationRequest', schemas)

    def test_restart_interrupts_unknown_inflight_work(self):
        task = self.wait(self.create(['android']).id)
        with self.service.lock:
            task.platforms[0].status = task.platforms[0].attempts[0].status = 'running'
            self.service._save(task)
        self.service.close()
        self.service = ExportService(self.root / 'exports', self.resolve, self.adapter)
        self.assertEqual(self.service.get('p1', task.id).platforms[0].status, 'interrupted')

    def test_blocked_preparation_can_retry_in_fresh_directory(self):
        from build_release.export_packaging import ExportBlocked
        original = self.adapter.prepare
        directories = []
        def prepare(source, work, settings, emit, cancel):
            directories.append(work)
            if len(directories) == 1:
                work.mkdir(parents=True)
                raise ExportBlocked('missing tool')
            return original(source, work, settings, emit, cancel)
        self.adapter.prepare = prepare
        task = self.wait(self.create(['android']).id)
        self.assertEqual(task.platforms[0].status, 'blocked')
        self.service.continue_platform('p1', task.id, 'android')
        task = self.wait(task.id)
        self.assertEqual(task.platforms[0].status, 'succeeded')
        self.assertNotEqual(directories[0], directories[1])

    def test_artifact_escape_rejected_and_logs_redacted(self):
        self.service.redact_text = lambda text: text.replace('secret', '[redacted]')
        def build(platform, web, work, settings, emit, cancel):
            emit('packaging', 'secret')
            return [self.source / 'index.html']
        self.adapter.build = build
        task = self.wait(self.create(['android']).id)
        self.assertEqual(task.platforms[0].status, 'failed')
        self.assertIn('[redacted]', [entry.message for entry in task.platforms[0].attempts[0].logs])
        self.assertFalse(task.platforms[0].attempts[0].artifacts)

    def test_snapshot_rejects_concurrent_save_and_removes_partial_copy(self):
        copy = shutil.copytree
        def changing_copy(source, target, **kwargs):
            result = copy(source, target, **kwargs)
            (self.source / 'index.html').write_text('saved during snapshot')
            return result
        with patch('build_release.export_service.shutil.copytree', side_effect=changing_copy):
            with self.assertRaisesRegex(ValueError, '源码发生变化'):
                self.create(['android'])
        self.assertEqual(self.service.list('p1'), [])
        self.assertFalse(any(path.is_dir() for path in (self.root / 'exports').iterdir()))

    def test_explicit_consent_changes_only_future_attempt_settings(self):
        task = self.wait(self.create(['win-x64']).id)
        self.service.consent('p1', task.id, ExportConsentRequest(allow_dependency_install=True))
        task = self.service.get('p1', task.id)
        self.assertTrue(task.settings.allow_dependency_install)
        self.assertFalse(task.platforms[0].attempts[0].settings.allow_dependency_install)
        self.service.continue_platform('p1', task.id, 'win-x64')
        task = self.wait(task.id)
        self.assertTrue(task.platforms[0].attempts[-1].settings.allow_dependency_install)

    def test_refresh_source_links_new_task_and_preserves_old_evidence(self):
        previous = self.wait(self.create(['android']).id)
        previous_artifact = previous.platforms[0].attempts[0].artifacts[0]
        self.service.message('p1', previous.id, ExportMessageRequest(content='修复游戏后重新导出'))
        (self.source / 'index.html').write_text('repaired game')
        refreshed = self.wait(self.service.refresh_source('p1', previous.id).id)
        self.assertEqual(refreshed.previous_task_id, previous.id)
        self.assertNotEqual(refreshed.source_version, previous.source_version)
        self.assertIn('修复游戏后重新导出', [message.content for message in refreshed.messages])
        self.assertEqual(refreshed.platforms[0].verification, 'pending')
        artifact = refreshed.platforms[0].attempts[0].artifacts[0]
        self.assertEqual(self.service.artifact('p1', refreshed.id, artifact.id).read_text(), 'repaired game')
        self.assertEqual(self.service.artifact('p1', previous.id, previous_artifact.id).read_text(), '<html>play</html>')
        with self.assertRaises(KeyError):
            self.service.refresh_source('p2', previous.id)

    def test_source_symlink_is_rejected(self):
        (self.source / 'outside').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, '符号链接'):
            self.create(['android'])


if __name__ == '__main__':
    unittest.main()
