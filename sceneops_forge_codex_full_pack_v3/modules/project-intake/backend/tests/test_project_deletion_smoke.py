"""Only temporary, explicitly created fixture projects are deleted."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sceneops_project_workspace import SqliteWorkspaceRepository, create_folder_router


class ProjectDeletionSmoke(unittest.TestCase):
    def test_delete_files_and_refuse_unconfirmed_or_changed_identity(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / 'data/db.sqlite3')
            project = repository.create_folder_project(parent, 'delete-fixture')
            root = Path(project.root_path)
            outside = parent / 'keep.txt'
            outside.write_text('keep')
            (root / 'outside-link').symlink_to(outside)
            app = FastAPI()
            app.include_router(create_folder_router(repository))
            client = TestClient(app)
            url = f'/api/workspace/folder-projects/{project.project_id}/delete-files'
            body = {'confirmed_root_path': str(root), 'confirm_permanent_delete': True}
            self.assertEqual(client.post(url, json={**body, 'confirm_permanent_delete': False}).status_code, 422)
            self.assertEqual(client.post(url, json={**body, 'confirmed_root_path': str(parent)}).status_code, 409)
            marker = root / '.sceneops/project.json'
            original = marker.read_text()
            identity = json.loads(original)
            identity['project_id'] = 'different-project'
            marker.write_text(json.dumps(identity))
            self.assertEqual(client.post(url, json=body).status_code, 409)
            marker.write_text(original)
            with patch('sceneops_project_workspace.project_deletion.shutil.rmtree', side_effect=PermissionError):
                self.assertEqual(client.post(url, json=body).status_code, 409)
            self.assertEqual(len(repository.list_folder_projects()), 1)
            self.assertTrue(root.exists())
            self.assertEqual(client.post(url, json=body).status_code, 204)
            self.assertFalse(root.exists())
            self.assertEqual(outside.read_text(), 'keep')
            self.assertEqual(repository.list_folder_projects(), [])

    def test_forget_missing_directory(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / 'data/db.sqlite3')
            project = repository.create_folder_project(parent, 'move-fixture')
            moved = parent / 'moved'
            Path(project.root_path).rename(moved)
            app = FastAPI()
            app.include_router(create_folder_router(repository))
            self.assertEqual(TestClient(app).delete(f'/api/workspace/folder-projects/{project.project_id}').status_code, 204)
            self.assertTrue((moved / '.git').is_dir())
            self.assertEqual(repository.list_folder_projects(), [])
