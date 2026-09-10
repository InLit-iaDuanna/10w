import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from asset_library import (BuiltinAssetCatalog, ProjectAssetCatalogService,
                           ProjectAssetRegistration, ProjectAssetVersion,
                           SqliteProjectAssetRepository)
from asset_factory import (
    BuiltinAssetSelection,
    BuiltinProjectAssets,
    CardAssetError,
    CardAssetService,
)
from sceneops_project_workspace import SqliteWorkspaceRepository


class BuiltinProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        database = self.root / 'state.sqlite3'
        self.workspace = SqliteWorkspaceRepository(database)
        self.project = self.workspace.create_folder_project(self.root, 'game')
        self.workspace.commit_design_version(self.project.project_id, 1, {'title':'fixture'})
        self.workspace.initialize_game_project(self.project.project_id, {
            'target_platform':'web','engine':'threejs','code_architecture':'object-component',
            'architecture_label':'对象／组件式','selection_method':'manual',
            'rationale':'fixture','tradeoffs':[],'ecs_library':None}, 1)
        self.card = SimpleNamespace(id='world-3d', title='世界', model_dump=lambda **kwargs: {'title':'世界'})
        self.binding = self.workspace.open_card_worktree(self.project.project_id, self.card.id, self.card.title)
        self.library = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
        self.assets = CardAssetService(database, self.root/'data', self.workspace, SimpleNamespace(), catalog=self.library)
        self.catalog = BuiltinAssetCatalog()
        self.builtin = BuiltinProjectAssets(self.catalog, self.assets, self.library, self.workspace,
                                           lambda project, card: self.card)

    def test_pack_installs_in_card_only_and_preserves_existing_files(self):
        report = self.builtin.install_pack(self.project.project_id, self.card.id)
        entries = self.catalog.public_catalog().entries
        expected_resources = (
            len(entries)
            + sum(bool(entry.sprite_url) for entry in entries)
            + len({entry.pack_id for entry in entries if entry.shared_motion_url})
            + sum(max(0, len(entry.lods) - 1) for entry in entries)
            + sum(bool(entry.physics_url) for entry in entries)
            + sum(bool(entry.scene_url) for entry in entries)
        )
        self.assertEqual(len(report['installed_files']), expected_resources + 1)
        card_root = Path(self.binding['worktree_path'])
        manifest = card_root / report['catalog_path']
        self.assertTrue(manifest.is_file())
        payload = json.loads(manifest.read_text())
        shared_urls={item['shared_motion_url'] for item in payload['entries'] if item['shared_motion_url']}
        self.assertEqual(len(shared_urls), 1)
        self.assertTrue((card_root / 'public' / next(iter(shared_urls)).lstrip('/')).is_file())
        for item in payload['entries']:
            if item['sprite_url']:
                self.assertTrue((card_root / 'public' / item['sprite_url'].lstrip('/')).is_file())
                self.assertIn('像素', item['style_prompts'])
        self.assertFalse((Path(self.project.root_path) / 'public/sceneops-assets').exists())
        asset = card_root / report['installed_files'][0]
        asset.write_bytes(b'user-modified-asset')
        repeated = self.builtin.install_pack(self.project.project_id, self.card.id)
        self.assertEqual(repeated['installed_files'], [])
        self.assertEqual(asset.read_bytes(), b'user-modified-asset')

    def test_selected_install_copies_only_requested_assets_and_dependencies(self):
        selected_ids = [
            'sceneops-haven-kit-cottage',
            'sceneops-haven-kit-character-player',
            'sceneops-haven-kit-character-enemy',
        ]
        selections = [
            BuiltinAssetSelection(asset_id=selected_ids[0], purpose='关卡入口'),
            {'asset_id': selected_ids[1], 'purpose': '玩家角色', 'reason': '需要行走动画'},
            selected_ids[2],
            selected_ids[1],
        ]
        report = self.builtin.install_selected(
            self.project.project_id, self.card.id, selections)

        self.assertEqual(len(report['installed_files']), 7)
        self.assertEqual([entry['asset_id'] for entry in report['catalog']['entries']], selected_ids)
        card_root = Path(self.binding['worktree_path'])
        asset_directory = card_root / 'public/sceneops-assets/sceneops-haven-kit/v5'
        self.assertFalse((asset_directory / 'sceneops-haven-kit-barrel.glb').exists())
        self.assertFalse((asset_directory / 'sceneops-haven-kit-character-npc-sprites.png').exists())
        self.assertTrue((asset_directory / 'shared-motions-v1.glb').is_file())

        runtime = json.loads((card_root / report['catalog_path']).read_text(encoding='utf-8'))
        self.assertEqual([entry['source_asset_id'] for entry in runtime['entries']], selected_ids)
        self.assertTrue(all(entry['source_pack_version'] == '5' for entry in runtime['entries']))
        self.assertTrue(all(entry['project_asset_id'] is None for entry in runtime['entries']))
        shared_urls = {entry['shared_motion_url'] for entry in runtime['entries']
                       if entry['shared_motion_url']}
        self.assertEqual(len(shared_urls), 1)
        self.assertEqual([item['copy_state'] for item in report['materialization']],
                         ['copied', 'copied', 'copied'])
        motion_resources = [resource for item in report['materialization']
                            for resource in item['resources'] if resource['kind'] == 'motion']
        self.assertEqual(len(motion_resources), 2)
        self.assertEqual(len({resource['path'] for resource in motion_resources}), 1)

        protected = asset_directory / f'{selected_ids[0]}.glb'
        protected.write_bytes(b'user-modified-selected-asset')
        repeated = self.builtin.install_selected(
            self.project.project_id, self.card.id, selections)
        self.assertEqual(repeated['installed_files'], [])
        self.assertEqual(protected.read_bytes(), b'user-modified-selected-asset')
        self.assertTrue(all(item['copy_state'] == 'preserved'
                            for item in repeated['materialization']))

    def test_atlas_selection_copies_runtime_lods_and_physics_with_source_identity(self):
        asset_id = 'atlas100-s001-a01'
        report = self.builtin.install_selected(
            self.project.project_id, self.card.id, [asset_id])

        card_root = Path(self.binding['worktree_path'])
        directory = card_root / 'public/sceneops-assets/atlas100/v2.0.0'
        self.assertTrue((directory / f'{asset_id}.glb').is_file())
        self.assertTrue((directory / f'{asset_id}.lod1.glb').is_file())
        self.assertTrue((directory / f'{asset_id}.lod2.glb').is_file())
        self.assertTrue((directory / f'{asset_id}.physics.json').is_file())
        entry = report['catalog']['entries'][0]
        self.assertEqual(entry['source_pack_id'], 'atlas100')
        self.assertEqual(entry['source_pack_version'], '2.0.0')
        self.assertEqual([lod['level'] for lod in entry['lods']], [0, 1, 2])
        self.assertTrue(entry['physics_url'].endswith(f'{asset_id}.physics.json'))

    def test_selected_install_rejects_unknown_catalog_id_before_writing(self):
        with self.assertRaises(CardAssetError) as captured:
            self.builtin.install_selected(
                self.project.project_id, self.card.id, ['sceneops-haven-kit-does-not-exist'])
        self.assertEqual(captured.exception.code, 'BUILTIN_ASSET_NOT_FOUND')
        card_root = Path(self.binding['worktree_path'])
        self.assertFalse((card_root / 'public/sceneops-assets').exists())

    def test_selected_project_install_uses_registered_demo_root(self):
        asset_id = 'sceneops-haven-kit-cottage'

        report = self.builtin.install_selected_in_project(
            self.project.project_id, [{'asset_id': asset_id, 'purpose': '出生点'}])

        demo = self.workspace.open_project_demo_workspace(self.project.project_id)
        demo_root = Path(demo['workspace_root'])
        self.assertTrue((demo_root / report['catalog_path']).is_file())
        self.assertTrue((demo_root / 'public/sceneops-assets/sceneops-haven-kit/v5'
                         / f'{asset_id}.glb').is_file())
        self.assertEqual([item['source_asset_id'] for item in report['catalog']['entries']],
                         [asset_id])
        self.assertFalse((demo_root / 'public/sceneops-assets/sceneops-haven-kit/v5'
                          / 'sceneops-haven-kit-barrel.glb').exists())

    def test_selected_registered_asset_version_is_copied_to_real_project_url(self):
        card_root = Path(self.binding['worktree_path'])
        preview = card_root / 'assets/tree/preview.glb'
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b'project-tree-glb')
        entry = self.library.register_version(ProjectAssetRegistration(
            project_id=self.project.project_id, card_id=self.card.id,
            source_asset_id='tree-source', title='大树', source_type='generated',
            version=ProjectAssetVersion(source_version=2, dimensions_m=(4, 4, 6),
                vertex_count=100, triangle_count=160,
                blend_path='assets/tree/model.blend', preview_path='assets/tree/preview.glb',
                fbx_path='assets/tree/model.fbx', operation='generate'))).entry

        report = self.builtin.install_selected_project_assets(self.project.project_id, [{
            'project_asset_id': entry.id, 'version': '2', 'purpose': '道路地标'}])

        demo_root = Path(self.workspace.open_project_demo_workspace(
            self.project.project_id)['workspace_root'])
        target = demo_root / f'public/sceneops-project-assets/{entry.id}/v2/model.glb'
        self.assertEqual(target.read_bytes(), b'project-tree-glb')
        self.assertEqual(report['catalog']['entries'][0]['url'],
                         f'/sceneops-project-assets/{entry.id}/v2/model.glb')
        self.assertEqual(report['materialization'][0]['project_asset_id'], entry.id)
        preview.write_bytes(b'user-updated-source')
        repeated = self.builtin.install_selected_project_assets(self.project.project_id, [{
            'project_asset_id': entry.id, 'version': '2'}])
        self.assertEqual(target.read_bytes(), b'project-tree-glb')
        self.assertEqual(repeated['materialization'][0]['copy_state'], 'preserved')

    def test_selected_registered_asset_can_be_provided_to_card_game(self):
        card_root = Path(self.binding['worktree_path'])
        preview = card_root / 'assets/rock/preview.glb'
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b'project-rock-glb')
        entry = self.library.register_version(ProjectAssetRegistration(
            project_id=self.project.project_id, card_id=self.card.id,
            source_asset_id='rock-source', title='岩石', source_type='generated',
            version=ProjectAssetVersion(source_version=1, dimensions_m=(2, 2, 1),
                vertex_count=40, triangle_count=60,
                blend_path='assets/rock/model.blend', preview_path='assets/rock/preview.glb',
                fbx_path='assets/rock/model.fbx', operation='generate'))).entry

        report = self.builtin.install_selected_project_assets(
            self.project.project_id,
            [{'project_asset_id': entry.id, 'version': '1', 'purpose': '障碍物'}],
            self.card.id)

        target = card_root / f'public/sceneops-project-assets/{entry.id}/v1/model.glb'
        self.assertEqual(target.read_bytes(), b'project-rock-glb')
        self.assertEqual(report['catalog']['entries'][0]['url'],
                         f'/sceneops-project-assets/{entry.id}/v1/model.glb')

    def test_selected_install_rejects_symlink_destination(self):
        asset_id = 'sceneops-haven-kit-cottage'
        card_root = Path(self.binding['worktree_path'])
        directory = card_root / 'public/sceneops-assets/sceneops-haven-kit/v5'
        directory.mkdir(parents=True)
        outside = self.root / 'outside.glb'
        outside.write_bytes(b'outside')
        (directory / f'{asset_id}.glb').symlink_to(outside)

        with self.assertRaises(CardAssetError) as captured:
            self.builtin.install_selected(self.project.project_id, self.card.id, [asset_id])
        self.assertEqual(captured.exception.code, 'BUILTIN_ASSET_PATH_UNSAFE')
        self.assertEqual(outside.read_bytes(), b'outside')

    @unittest.skipUnless(os.environ.get('SCENEOPS_BUILTIN_LIVE') == '1', 'explicit actual Blender import smoke')
    def test_actual_glb_adoption_creates_project_versions_and_is_idempotent(self):
        asset_id = 'sceneops-haven-kit-cottage'
        entry = self.catalog.entry(asset_id)
        request = SimpleNamespace(project_id=self.project.project_id, card_id=self.card.id)
        adopted = self.builtin.adopt(entry, self.catalog.file(asset_id,'glb'), request)
        self.assertTrue(adopted.version_created)
        self.assertEqual(adopted.entry.project_id, self.project.project_id)
        version = adopted.entry.versions[0]
        for relative in (version.blend_path, version.preview_path, version.fbx_path):
            self.assertTrue((Path(self.binding['worktree_path']) / relative).is_file())
        repeated = self.builtin.adopt(entry, self.catalog.file(asset_id,'glb'), request)
        self.assertFalse(repeated.version_created)
        self.assertEqual(repeated.entry.id, adopted.entry.id)


if __name__ == '__main__':
    unittest.main()
