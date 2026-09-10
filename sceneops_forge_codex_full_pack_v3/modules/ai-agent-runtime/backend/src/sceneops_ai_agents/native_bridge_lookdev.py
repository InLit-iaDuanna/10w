"""Material tools carry task-bound project/workspace identity, never model authority."""
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import HarnessError
from vfx_shader import SaveLookdevRequest, LookdevProposalRequest, ApplyLookdevRequest, ExportLookdevRequest

class ReadLookdevInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_id: str = Field(min_length=1)
    document_id: str | None = None

class SaveNativeLookdevInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: SaveLookdevRequest

class ProposeNativeLookdevInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: LookdevProposalRequest

class ApplyNativeLookdevInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: ApplyLookdevRequest

class ExportNativeLookdevInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: ExportLookdevRequest

LOOKDEV_INPUT_MODELS = {
    'lookdev.material.export': ExportNativeLookdevInput,
    'lookdev.document.read': ReadLookdevInput,
    'lookdev.document.save': SaveNativeLookdevInput,
    'lookdev.material.propose': ProposeNativeLookdevInput,
    'lookdev.material.apply': ApplyNativeLookdevInput,
}

async def call_lookdev(service, task, name, inputs):
    lookdev = service.lookdev
    if lookdev is None:
        raise HarnessError('LOOKDEV_UNAVAILABLE', '材质服务未启用。')
    body = LOOKDEV_INPUT_MODELS[name].model_validate(inputs)
    if name == 'lookdev.document.read':
        asset_id = body.asset_id
        document = lookdev.get(task.project_id, body.document_id) if body.document_id else None
        if document and document.target.asset_id != asset_id:
            raise HarnessError('TASK_SCOPE_DENIED', '材质文档不属于指定资产。')
    elif name in ('lookdev.material.apply','lookdev.material.export'):
        document = lookdev.get(task.project_id, body.request.document_id, body.request.document_version)
        asset_id = document.target.asset_id
    else:
        document = body.request.document
        asset_id = document.target.asset_id
    asset = service.project_assets.get(task.project_id, asset_id)
    if asset.workspace_id != task.grant.workspace_id or (document and document.project_id != task.project_id):
        raise HarnessError('TASK_SCOPE_DENIED', '材质目标不属于当前授权工作区。')
    if name == 'lookdev.document.read':
        result = document.model_dump(mode='json') if document else [doc.model_dump(mode='json') for doc in lookdev.list(task.project_id,asset_id)]
    elif name == 'lookdev.document.save':
        result = (await lookdev.save(task.project_id,body.request)).model_dump(mode='json')
    elif name == 'lookdev.material.propose':
        result = (await lookdev.propose(task.project_id,body.request)).model_dump(mode='json')
    elif name == 'lookdev.material.export':
        result = (await lookdev.export(task.project_id,body.request)).model_dump(mode='json')
    else:
        result = lookdev.apply(task.project_id,body.request).model_dump(mode='json')
        service.game.invalidate_workspace(Path(task.grant.workspace_root))
    return {'tool':name,'mode':'live','effect_state':'COMMITTED' if name.endswith(('save','apply','export')) else 'READ_ONLY','result':result}
