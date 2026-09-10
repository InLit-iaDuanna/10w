"""Native access to shipped assets, scoped to the authorized project workspace."""
import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from asset_library import BuiltinAssetCatalog
from sceneops_harness import HarnessError


class InstallBuiltinAssetsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_ids: list[str] = Field(min_length=1, max_length=64,
                                description='Exact asset_id values from builtin.assets.list')


async def install_builtin_assets(service, task, inputs):
    if not task.grant.include_demo_assets:
        raise HarnessError('TASK_SCOPE_DENIED', '本次未授权内置资产安装。')
    if service.builtin_project_install_selected is None:
        raise HarnessError('BUILTIN_ASSETS_UNAVAILABLE', '内置资产安装服务尚未连接。')
    catalog = BuiltinAssetCatalog()
    for asset_id in inputs['asset_ids']:
        catalog.entry(asset_id)
    service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                                   expected_root=task.grant.workspace_root)
    report = await asyncio.to_thread(service.builtin_project_install_selected, task.project_id,
        [{'asset_id': asset_id} for asset_id in dict.fromkeys(inputs['asset_ids'])])
    service.game.invalidate_workspace(Path(task.grant.workspace_root))
    return {'tool': 'code.demo_assets.install', 'mode': 'live', 'effect_state': 'COMMITTED',
            'workspace_id': task.grant.workspace_id, 'report': report}
