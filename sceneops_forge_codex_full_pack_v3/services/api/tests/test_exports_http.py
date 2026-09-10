"""Check export routes through the actual local security middleware."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from services.api.app import create_app


class PackagingFixture:
    mode = 'mock'

    def prepare(self, source, work, settings, emit, cancel):
        work.mkdir(parents=True)
        (work / 'index.html').write_text('fixture', encoding='utf-8')
        return work

    def build(self, platform, web, work, settings, emit, cancel):
        if platform == 'win-x64':
            raise RuntimeError('fixture failure')
        result = work / 'fixture.zip'
        result.write_bytes(b'fixture, not a real playable package')
        return [result]


class ExportHttpTests(unittest.TestCase):
    def test_real_composition_and_project_isolation(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'SCENEOPS_DATA_DIR': str(Path(directory) / 'state'),
            'SCENEOPS_LOCAL_TOKEN': 'export-http-fixture',
        }):
            app = create_app()
            app.state.exports.adapter = PackagingFixture()
            with TestClient(app, base_url='http://127.0.0.1', headers={
                'x-sceneops-token': 'export-http-fixture',
                'origin': 'http://127.0.0.1:4300',
            }) as client:
                project = app.state.workspace_repository.create_folder_project(str(Path(directory).resolve()), '中文 游戏')
                url = f'/api/projects/{project.project_id}/exports'
                response = client.post(url, json={'platforms': ['mac-arm64', 'win-x64']})
                self.assertEqual(response.status_code, 200, response.text)
                task = response.json()
                detail = f"{url}/{task['id']}"
                for _ in range(100):
                    task = client.get(detail).json()
                    if all(run['status'] not in ('queued', 'running') for run in task['platforms']):
                        break
                    time.sleep(.01)
                self.assertEqual(task['mode'], 'mock')
                artifact = task['platforms'][0]['attempts'][0]['artifacts'][0]
                self.assertEqual(client.get(artifact['download_url']).status_code, 200)
                self.assertEqual(client.post(detail + '/platforms/win-x64/continue', json={}).status_code, 200)
                other = app.state.workspace_repository.create_folder_project(str(Path(directory).resolve()), 'Other')
                self.assertEqual(client.get(f'/api/projects/{other.project_id}/exports/{task["id"]}').status_code, 404)
                self.assertEqual(client.get(detail, headers={'x-sceneops-token': 'wrong'}).status_code, 401)


if __name__ == '__main__':
    unittest.main()
