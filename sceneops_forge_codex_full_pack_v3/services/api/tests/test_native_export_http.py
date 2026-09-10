"""Export HTTP -> grant -> native provider -> persisted output, with a fake provider."""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from services.api.app import create_app


class NativeExportHttpTests(unittest.TestCase):
    def test_export_page_executes_native_task_and_registers_real_output_file(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'SCENEOPS_DATA_DIR': str(Path(directory) / 'state'),
            'SCENEOPS_LOCAL_TOKEN': 'native-export-fixture',
        }):
            app = create_app()
            calls = []
            async def execute(goal, **options):
                calls.append(options)
                self.assertIs(asyncio.get_running_loop(), app.state.exports.native_agent.loop)
                root = options['workspace_root']
                self.assertTrue(options['allow_environment_setup'])
                self.assertIn('sceneops-export-desktop', options['execution_instructions'])
                await options['on_event']({'type': 'command_execution', 'phase': 'started',
                    'item_id': 'fixture-command', 'input': {'command': 'fixture command'}})
                artifact = root / 'fixture.zip'
                with zipfile.ZipFile(artifact, 'w') as archive:
                    archive.writestr('Fixture.app/Contents/MacOS/Fixture', b'fixture executable, not runnable')
                (root / 'sceneops-export-result.json').write_text(json.dumps({
                    'artifacts': [{'platform': 'mac-arm64', 'path': artifact.name}],
                    'platforms': [{'platform': 'mac-arm64', 'status': 'succeeded'}]}))
                await options['on_event']({'type': 'assistant_message', 'text': 'fixture native completion'})
                return {'result': 'fixture native completion'}
            app.state.agent_tasks.provider.execute_task = execute
            with patch.object(app.state.agent_tasks.provider, 'settings', return_value=SimpleNamespace(
                provider='codebuddycli', model='cli-default', reasoning_effort='low')):
                with TestClient(app, base_url='http://127.0.0.1', headers={
                    'x-sceneops-token': 'native-export-fixture', 'origin': 'http://127.0.0.1:4300',
                }) as client:
                    project = app.state.workspace_repository.create_folder_project(str(Path(directory).resolve()), 'Native fixture')
                    url = f'/api/projects/{project.project_id}/exports'
                    denied = client.post(url, json={'platforms': ['mac-arm64'], 'execution_mode': 'native'})
                    self.assertEqual(denied.status_code, 422, denied.text)
                    self.assertEqual(calls, [])
                    response = client.post(url, json={'platforms': ['mac-arm64'],
                        'execution_mode': 'native', 'accept_full_access': True})
                    self.assertEqual(response.status_code, 200, response.text)
                    task_id = response.json()['id']
                    for _ in range(300):
                        task = client.get(f'{url}/{task_id}').json()
                        if task['native_runs'] and task['native_runs'][-1]['status'] not in ('queued', 'running'):
                            break
                        time.sleep(.02)
                    native = task['native_runs'][-1]
                    self.assertEqual(native['status'], 'succeeded', native)
                    self.assertEqual(len(calls), 1)
                    self.assertTrue(native['agent_task_id'])
                    self.assertTrue(native['logs'])
                    self.assertEqual(task['messages'][-1]['content'], 'fixture native completion')
                    platform = task['platforms'][0]
                    self.assertEqual(platform['verification'], 'pending')
                    self.assertEqual(platform['status'], 'succeeded')
                    artifact = platform['attempts'][-1]['artifacts'][0]
                    self.assertEqual(client.get(artifact['download_url']).status_code, 200)
                    record = app.state.agent_tasks.get(native['agent_task_id'])
                    self.assertEqual(record.authorization_card.task_profile, 'project-export-agent')
                    self.assertTrue(record.grant.revoked)
                    self.assertNotIn('game_project', record.observations)
                    self.assertNotIn('allow_dependency_install', record.observations['export_context']['settings'])
                    self.assertFalse(record.observations['export_context']['fixed_build_dependency_download_allowed'])

    def test_native_cancel_settles_worker_on_application_loop(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'SCENEOPS_DATA_DIR': str(Path(directory) / 'state'),
            'SCENEOPS_LOCAL_TOKEN': 'native-cancel-fixture',
        }):
            app = create_app()
            entered, stopped = threading.Event(), threading.Event()
            async def execute(goal, **options):
                entered.set()
                try:
                    await asyncio.Future()
                finally:
                    stopped.set()
            app.state.agent_tasks.provider.execute_task = execute
            with patch.object(app.state.agent_tasks.provider, 'settings', return_value=SimpleNamespace(
                provider='codebuddycli', model='cli-default', reasoning_effort='low')):
                with TestClient(app, base_url='http://127.0.0.1', headers={
                    'x-sceneops-token': 'native-cancel-fixture', 'origin': 'http://127.0.0.1:4300',
                }) as client:
                    project = app.state.workspace_repository.create_folder_project(str(Path(directory).resolve()), 'Cancel fixture')
                    url = f'/api/projects/{project.project_id}/exports'
                    response = client.post(url, json={'platforms': ['mac-arm64'],
                        'execution_mode': 'native', 'accept_full_access': True})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertTrue(entered.wait(5))
                    detail = url + '/' + response.json()['id']
                    response = client.post(detail + '/agent/cancel', json={})
                    self.assertEqual(response.status_code, 200)
                    for _ in range(200):
                        task = client.get(detail).json()
                        if task['native_runs'][-1]['status'] not in ('queued', 'running'):
                            break
                        time.sleep(.02)
                    self.assertTrue(stopped.is_set())
                    self.assertEqual(task['native_runs'][-1]['status'], 'cancelled', task['native_runs'])


if __name__ == '__main__':
    unittest.main()
