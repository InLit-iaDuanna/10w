"""Small native asset dispatch smoke; no model or production project writes."""
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from pydantic import ValidationError
from asset_library import BuiltinAssetCatalog
from sceneops_harness import HarnessError
from sceneops_ai_agents.native_builtin_assets import InstallBuiltinAssetsInput, install_builtin_assets


class NativeBuiltinAssetsSmoke(IsolatedAsyncioTestCase):
    async def test_selection_is_bound_to_granted_workspace(self):
        asset_id = BuiltinAssetCatalog().public_catalog().entries[0].asset_id
        task = SimpleNamespace(project_id='project-one', grant=SimpleNamespace(
            include_demo_assets=True, workspace_id='workspace-one', workspace_root='/tmp/native-assets-smoke'))
        service = SimpleNamespace(project_demo_workspace=Mock(),
            builtin_project_install_selected=Mock(return_value={'installed_files': ['asset.glb']}),
            game=SimpleNamespace(invalidate_workspace=Mock()))
        inputs = InstallBuiltinAssetsInput(asset_ids=[asset_id]).model_dump()
        result = await install_builtin_assets(service, task, inputs)
        service.project_demo_workspace.assert_called_once_with('project-one', 'workspace-one',
            expected_root='/tmp/native-assets-smoke')
        service.builtin_project_install_selected.assert_called_once_with('project-one', [{'asset_id': asset_id}])
        service.game.invalidate_workspace.assert_called_once_with(Path('/tmp/native-assets-smoke'))
        self.assertEqual(result['workspace_id'], 'workspace-one')
        task.grant.include_demo_assets = False
        with self.assertRaises(HarnessError):
            await install_builtin_assets(service, task, inputs)
        self.assertEqual(service.builtin_project_install_selected.call_count, 1)
        with self.assertRaises(ValidationError):
            InstallBuiltinAssetsInput(asset_ids=[asset_id], project_id='other-project')
