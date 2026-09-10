"""Local demo-pack installation checks; no inference, downloads or rendering."""
import tempfile
import unittest
from pathlib import Path

from sceneops_project_workspace import GameProjectError, SqliteWorkspaceRepository, demo_asset_files
from sceneops_project_workspace.game_projects import template_files


class DemoAssetsSmoke(unittest.TestCase):
    def test_scaffold_pack_and_safe_worktree_installation(self):
        for architecture in ('object-component', 'ecs'):
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                repository = SqliteWorkspaceRepository(root / 'state.sqlite3')
                project = repository.create_folder_project(root, 'game')
                repository.commit_design_version(project.project_id, 1, {'title': '演示'})
                selection = {'code_architecture': architecture, 'architecture_label': architecture}
                scaffold = repository.initialize_game_project(project.project_id, selection, 1)
                branch = repository.open_card_worktree(project.project_id, 'demo', '演示')
                worktree = Path(branch['worktree_path'])
                pack_path, content = next(iter(demo_asset_files().items()))
                self.assertNotIn(pack_path, scaffold['generated_files'])
                installed = repository.install_demo_assets(project.project_id, 'demo')
                self.assertIn(pack_path, installed['installed_files'])
                self.assertEqual((worktree / pack_path).read_text(), content)
                self.assertNotIn('createDemoScenery()', (worktree / (
                    'src/main.ts' if architecture == 'ecs' else 'src/game/Game.ts')).read_text())
                # A user edit must survive both repeated initialization and asset installation.
                project_main = Path(project.root_path) / 'src/main.ts'
                project_main.write_text('// user project code\n')
                reopened = repository.initialize_game_project(project.project_id, selection, 1)
                self.assertEqual(reopened['baseline_commit'], scaffold['baseline_commit'])
                self.assertEqual(project_main.read_text(), '// user project code\n')
                (worktree / pack_path).write_text('// user customized asset pack\n')
                result = repository.install_demo_assets(project.project_id, 'demo')
                self.assertEqual(result['preserved_files'], [pack_path])
                self.assertEqual(result['installed_files'], [])
                self.assertEqual((worktree / pack_path).read_text(), '// user customized asset pack\n')
                (worktree / pack_path).unlink()
                result = repository.install_demo_assets(project.project_id, 'demo')
                self.assertEqual(result['installed_files'], [pack_path])
                self.assertEqual((worktree / pack_path).read_text(), content)
                self.assertEqual(result['workspace_root'], str(worktree))
                (worktree / pack_path).unlink()
                outside = root / 'outside.ts'; outside.write_text('// protected\n')
                (worktree / pack_path).symlink_to(outside)
                with self.assertRaises(GameProjectError):
                    repository.install_demo_assets(project.project_id, 'demo')
                self.assertEqual(outside.read_text(), '// protected\n')

    def test_both_templates_reference_the_same_asset_module(self):
        pack = demo_asset_files()
        for architecture in ('object-component', 'ecs'):
            files = template_files(architecture)
            for path, content in pack.items():
                self.assertEqual(files[path], content)
            player_path = 'src/game/world.ts' if architecture == 'ecs' else 'src/game/objects/Player.ts'
            self.assertIn("createCharacter('player')", files[player_path])
