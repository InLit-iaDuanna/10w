import subprocess
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from version_collaboration.tree_router import create_tree_router


class VersionTreeSmoke(unittest.TestCase):
    def create_repository(self, folder):
        root = Path(folder)
        def git(*args):
            return subprocess.check_output(['git', '-C', folder, *args], text=True).strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'Tree Test')
        git('config', 'user.email', 'tree@example.test')
        (root / 'main.txt').write_text('initial')
        git('add', '.')
        git('commit', '-m', 'initial')
        return root, git

    def test_branch_merge_and_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.check_output(['git', '-C', folder, *args], text=True).strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Tree Test')
            git('config', 'user.email', 'tree@example.test')
            (root / 'main.txt').write_text('initial')
            git('add', '.'); git('commit', '-m', 'initial')
            git('checkout', '-b', 'feature')
            (root / 'feature.txt').write_text('feature')
            git('add', '.'); git('commit', '-m', 'feature')
            git('checkout', 'main')
            git('merge', '--no-ff', 'feature', '-m', 'merge')
            app = FastAPI(); app.include_router(create_tree_router('project.tree', lambda: root))
            client = TestClient(app)
            response = client.get('/api/version-collaboration/tree')
            self.assertEqual(response.status_code, 200, response.text)
            state = response.json()
            self.assertEqual(state['mode'], 'live')
            self.assertEqual(len(state['commits'][0]['parent_ids']), 2)
            self.assertEqual(len(state['branches']), 2)
            files = client.get('/api/version-collaboration/tree/commits/' + state['version']['commit_id'] + '/files')
            self.assertEqual(files.json()[0]['path'], 'feature.txt')

    def test_missing_folder_returns_visible_failure(self):
        def missing(): raise KeyError('missing')
        app = FastAPI(); app.include_router(create_tree_router('project.tree', missing))
        response = TestClient(app).get('/api/version-collaboration/tree')
        self.assertEqual(response.status_code, 409)
        self.assertIn('文件夹', response.json()['detail'])

    def test_branch_preview_create_and_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            root, git = self.create_repository(folder)
            app = FastAPI()
            app.include_router(create_tree_router('project.tree', lambda: root))
            client = TestClient(app)
            preview = client.post('/api/version-collaboration/tree/branches/preview', json={
                'operation': 'create', 'branch_name': 'feature/tree', 'source_commit': None,
            })
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertEqual(preview.json()['blocked_reasons'], [])
            applied = client.post('/api/version-collaboration/tree/branches/apply', json={
                'change_set': preview.json(), 'confirmed': True,
            })
            self.assertEqual(applied.status_code, 200, applied.text)
            self.assertEqual(applied.json()['current_branch'], 'feature/tree')
            self.assertEqual(git('branch', '--show-current'), 'feature/tree')

    def test_dirty_worktree_blocks_branch_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            root, git = self.create_repository(folder)
            git('branch', 'other')
            (root / 'main.txt').write_text('changed')
            app = FastAPI()
            app.include_router(create_tree_router('project.tree', lambda: root))
            preview = TestClient(app).post('/api/version-collaboration/tree/branches/preview', json={
                'operation': 'switch', 'branch_name': 'other', 'source_commit': None,
            })
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertIn('dirty_worktree', preview.json()['blocked_reasons'])
