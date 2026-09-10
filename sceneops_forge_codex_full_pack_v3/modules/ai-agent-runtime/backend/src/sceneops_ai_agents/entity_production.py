"""Project-owned production definitions and explicit source adoption."""
from pathlib import Path
from contextlib import nullcontext
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import HarnessError
from sceneops_project_workspace import EntityStore, ProductionEntity
from asset_factory import inspect_native_glb
from .demo_workbench import project_task, content_index
from .native_bridge_assets import RegisterNativeAssetInput, register_native_asset


class OrganizeEntity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')
    title: str = Field(min_length=1, max_length=120)
    feature_id: str
    path: str
    assign_missing_identities: bool = False
    source_versions: dict[str, int] = Field(min_length=1)


class EntityProposal(BaseModel):
    request: OrganizeEntity
    node_ids: list[str]
    missing_identity_count: int = 0
    existing: ProductionEntity | None = None
    mode: str = 'live'


class AdoptEntity(BaseModel):
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')
    expected_revision: int = Field(ge=1)
    asset_version: int = Field(ge=1)


def store(service):
    return EntityStore(service.workspace)


def list_entities(service, task_id):
    task = project_task(service, task_id)
    return store(service).list(task.project_id, task.authorization_card.workspace_id)


def material_interfaces(document):
    result = {}
    for node in document.get('nodes', []):
        if 'mesh' not in node:
            continue
        slots = []
        for primitive in document['meshes'][node['mesh']]['primitives']:
            material = document.get('materials', [])[primitive['material']] if 'material' in primitive else {}
            identity = material.get('extras', {}).get('lookdevSourceMaterialId')
            if not identity:
                raise HarnessError('MATERIAL_IDENTITY_MISSING', '材质槽缺少稳定身份：'+node['extras']['sceneops_id'])
            slots.append(identity)
        result[node['extras']['sceneops_id']] = sorted(set(slots))
    return result


def proposal(service, task_id, body):
    task = project_task(service, task_id)
    index = content_index(service, task_id)
    known = {s.id: s.source_version for s in index.sources}
    if any(known.get(key) != value for key, value in body.source_versions.items()):
        raise HarnessError('SOURCE_VERSION_CONFLICT', '关联源码已变化，请重新读取规整提案。')
    root = Path(task.grant.workspace_root)
    path = root / body.path
    if Path(body.path).is_absolute() or path.resolve() != path or not path.is_relative_to(root) or path.suffix != '.glb':
        raise HarnessError('TASK_SCOPE_DENIED', '只接受当前工程中的 GLB 草模。')
    try:
        document = inspect_native_glb(path)
    except (ValueError, OSError) as error:
        raise HarnessError('GLB_IMPORT_INVALID', '草模无法导入：'+str(error)) from error
    original_nodes = [node.get('extras', {}).get('sceneops_id') for node in document.get('nodes', [])]
    missing_count = sum(not value for value in original_nodes)
    if body.assign_missing_identities:
        from asset_library import assign_glb_identities
        try:
            document = assign_glb_identities(document)
        except ValueError as error:
            raise HarnessError('ASSET_IDENTITY_MISSING', str(error)) from error
    nodes = [node.get('extras', {}).get('sceneops_id') for node in document.get('nodes', [])]
    if not nodes or any(not isinstance(n, str) or not n for n in nodes) or len(nodes) != len(set(nodes)):
        raise HarnessError('ASSET_IDENTITY_MISSING', '草模每个节点必须带有唯一稳定身份。')
    existing = next((e for e in list_entities(service, task_id)
        if set(e.source_ids) == set(body.source_versions) and e.feature_id == body.feature_id), None)
    material_interfaces(document)
    return EntityProposal(request=body, node_ids=[n for n in original_nodes if n], missing_identity_count=missing_count, existing=existing)


def organize(service, task_id, body, *, native=False):
    task = project_task(service, task_id)
    if native:
        service.check_grant(task_id, 'production.entity.organize')
    with nullcontext() if native else service.records.manual_edit(task):
        prior = service.get(task_id).observations.get('entity_organize_requests', {}).get(body.request_id)
        if prior and prior['request'] != body.model_dump(mode='json'):
            raise HarnessError('REQUEST_ID_CONFLICT', '同一规整请求不能更换内容。')
        plan = proposal(service, task_id, body)
        if plan.existing:
            return plan.existing
        if prior:
            asset_id = prior['asset_id']
        else:
            result = register_native_asset(service, task, RegisterNativeAssetInput(path=body.path, title=body.title, assign_missing_identities=body.assign_missing_identities))
            asset_id = result['asset']['id']
            service.records.update(task_id, lambda current: current.observations.setdefault('entity_organize_requests', {}).update({
                body.request_id: {'request': body.model_dump(mode='json'), 'asset_id': asset_id}}), 'agent.entity.asset_registered')
        registered = service.project_assets.get(task.project_id, asset_id)
        document = inspect_native_glb(Path(registered.versions[0].preview_path))
        entity = store(service).register(task.project_id, task.grant.workspace_id,
            body.feature_id+':'+','.join(sorted(body.source_versions)), title=body.title,
            source_ids=sorted(body.source_versions), feature_id=body.feature_id,
            asset_id=asset_id, adopted_asset_version=1, required_node_ids=[node['extras']['sceneops_id'] for node in document['nodes']],
            material_interfaces=material_interfaces(document))
        service.game.invalidate_project_workspace(task.project_id, task.grant.workspace_id)
        return entity


def adopt(service, task_id, entity_id, body, *, native=False):
    task = project_task(service, task_id)
    if native:
        service.check_grant(task_id, 'production.entity.adopt')
    with nullcontext() if native else service.records.manual_edit(task):
        try:
            entity = store(service).get(task.project_id, task.grant.workspace_id, entity_id)
        except ValueError as error:
            raise HarnessError('ENTITY_NOT_FOUND', str(error)) from error
        asset = service.project_assets.get(task.project_id, entity.asset_id)
        if asset.workspace_id != task.grant.workspace_id:
            raise HarnessError('TASK_SCOPE_DENIED', '资产不属于当前工程。')
        version = next((v for v in asset.versions if v.source_version == body.asset_version), None)
        if version is None:
            raise HarnessError('ASSET_VERSION_NOT_FOUND', '目标版本不存在。')
        document = inspect_native_glb(Path(version.preview_path))
        nodes = {n.get('extras', {}).get('sceneops_id') for n in document.get('nodes', [])}
        missing = set(entity.required_node_ids) - nodes
        if missing:
            raise HarnessError('ENTITY_INTERFACE_CHANGED', '模型缺少原有部件：'+', '.join(sorted(missing)))
        interfaces = entity.material_interfaces or material_interfaces(inspect_native_glb(Path(asset.versions[0].preview_path)))
        actual = material_interfaces(document)
        incompatible = [node+':'+slot for node, slots in interfaces.items() for slot in slots if slot not in actual.get(node, [])]
        if incompatible:
            raise HarnessError('ENTITY_INTERFACE_CHANGED', '模型缺少原有材质接口：'+', '.join(incompatible))
        adopted = next(v for v in asset.versions if v.source_version == entity.adopted_asset_version)
        previous = inspect_native_glb(Path(adopted.preview_path))
        required_clips = {clip.get('extras', {}).get('sceneops_id') for clip in previous.get('animations', [])} - {None}
        actual_clips = [clip.get('extras', {}).get('sceneops_id') for clip in document.get('animations', [])]
        missing_clips = required_clips - set(actual_clips)
        if missing_clips:
            raise HarnessError('ENTITY_INTERFACE_CHANGED', '模型缺少原有动画接口：'+', '.join(sorted(missing_clips)))
        if len([clip for clip in actual_clips if clip]) != len({clip for clip in actual_clips if clip}):
            raise HarnessError('ENTITY_INTERFACE_CHANGED', '模型包含重复的动画身份。')
        candidate = service.game.snapshot(task).current_playable_candidate
        try:
            result = store(service).adopt(task.project_id, task.grant.workspace_id, entity.id,
                body.asset_version, body.expected_revision, body.request_id, candidate.id if candidate else None, material_interfaces=interfaces)
        except ValueError as error:
            raise HarnessError('ENTITY_VERSION_CONFLICT', str(error)) from error
        service.game.invalidate_project_workspace(task.project_id, task.grant.workspace_id)
        return result
