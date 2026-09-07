"""Fact projection and scoped source edits through existing public domain services."""
from sceneops_harness import HarnessError
from asset_library import UpdateProjectAssetRecipeRequest
from world_composer import (TransformObjectRequest, UpdateKeyDoorBehaviorRequest,
                            RebindAssetVersionRequest, EnvironmentSceneError)
from .demo_workbench_models import DemoContentIndex, DemoSourceEntry, DemoContentSaved
from .code_workspace import read_source, task_source_path


def project_task(service, task_id):
    task = service.get(task_id)
    if task.authorization_card.task_profile not in ('project-demo', 'project-demo-agent'):
        raise HarnessError('TASK_SCOPE_DENIED', '这不是当前作品的初版制作记录。')
    card = task.authorization_card
    service.project_demo_workspace(task.project_id, card.workspace_id, expected_root=card.workspace_root)
    if service.project_assets is None or service.environment_scenes is None:
        raise HarnessError('PROJECT_DEMO_NOT_CONNECTED', '作品内容服务尚未连接。')
    return task


def content_index(service, task_id):
    task = project_task(service, task_id)
    card = task.authorization_card
    scene = service.environment_scenes.get(task.project_id)
    assets = [entry for entry in service.project_assets.list(task.project_id)
              if entry.workspace_id == card.workspace_id]
    sources = {}
    # Only actual successful writes establish source navigation, never file-name guessing.
    for number, entry in enumerate(task.actions, 1):
        if (entry.action.capability_id == 'code.file.write' and entry.state == 'succeeded'
                and entry.effect_state == 'COMMITTED'):
            path = entry.action.inputs['path']
            task_source_path(task, path)
            content = read_source(card.workspace_root, path)
            if content is not None:
                sources[path] = DemoSourceEntry(id=sources[path].id if path in sources else entry.request_id,
                    latest_write_request_id=entry.request_id, path=path,
                    content=content, source_version=number)
    _, _, candidate, _ = service.game._candidate_snapshot(task.project_id, card.workspace_id)
    asset_refs = {(item.asset_id, item.asset_version) for item in scene.objects}
    built_refs = ({(item['asset_id'], item['asset_version']) for item in candidate.asset_versions}
                  if candidate else set())
    changed = (candidate is None or scene.version != candidate.scene_version or asset_refs != built_refs)
    if candidate:
        from .code_workspace import source_file_versions
        built_files = candidate.source_version.get('source_file_versions')
        if built_files is not None:
            changed |= source_file_versions(card.workspace_root) != built_files
        recorded = set(candidate.source_version.get('code_write_requests', []))
        changed |= any(item.latest_write_request_id not in recorded for item in sources.values())
        # A user's unsent ordinary source edit must also make the source state dirty.
        for entry in task.actions:
            if entry.request_id in recorded and entry.action.capability_id == 'code.file.write':
                latest = sources.get(entry.action.inputs['path'])
                if latest and latest.latest_write_request_id == entry.request_id:
                    changed |= latest.content != entry.action.inputs['content']
    changed |= any(entry.current_version != item.asset_version for entry in assets
                   for item in scene.objects if item.asset_id == entry.id)
    notice = '源内容有未运行修改' if changed else '源内容与当前可玩版本一致'
    if not changed and candidate and 'source_file_versions' not in candidate.source_version:
        notice = '已登记内容与可玩候选一致；历史候选未记录完整源码版本'
    return DemoContentIndex(project_id=task.project_id, workspace_id=card.workspace_id,
        scene_version=scene.version, assets=assets, instances=scene.objects,
        sources=list(sources.values()), unbuilt_changes=bool(changed),
        source_notice=notice)


def resolve_target(service, task, target, *, check_version=True):
    card = task.authorization_card
    if (target.project_id, target.workspace_id) != (task.project_id, card.workspace_id):
        raise HarnessError('TASK_SCOPE_DENIED', '所选内容不属于当前项目与工作区，请重新选择。')
    index = content_index(service, task.id)
    if target.viewed_candidate_id is not None:
        candidates, _, _, _ = service.game._candidate_snapshot(task.project_id, card.workspace_id)
        if not any(c.id == target.viewed_candidate_id for c in candidates):
            raise HarnessError('TASK_SCOPE_DENIED', '试玩版本不属于当前作品。')
    if (check_version and target.kind == 'asset'
            and target.expected_scene_version != index.scene_version):
        raise HarnessError('DEMO_SOURCE_CONFLICT', '共享资产的引用范围已改变，请重读当前影响实例。')
    if target.kind == 'asset':
        value = next((item for item in index.assets if item.id == target.id), None)
        version = value.current_version if value else None
    elif target.kind == 'source':
        value = next((item for item in index.sources if item.id == target.id), None)
        version = value.source_version if value else None
    else:
        if target.kind == 'behavior':
            value = next((item for item in index.instances if item.behavior is not None
                and item.behavior.behavior_instance_id == target.id), None)
        else:
            value = next((item for item in index.instances if item.id == target.id), None)
        if value and not any(asset.id == value.asset_id for asset in index.assets):
            value = None
        if value and target.kind == 'behavior' and value.behavior is None:
            value = None
        version = index.scene_version
    if value is None:
        raise HarnessError('DEMO_TARGET_MISSING', '所选真实内容已不存在，请刷新内容列表。')
    if check_version and version != target.source_version:
        raise HarnessError('DEMO_SOURCE_CONFLICT', '编辑源已有较新版本，请重新读取；旧试玩参数不会覆盖新源。')
    if (check_version and target.kind == 'source'
            and target.expected_source_content != value.content):
        raise HarnessError('DEMO_SOURCE_CONFLICT', '源码已改变，请重新读取真实来源后发送要求。')
    return index, value


def save_content(service, task_id, body):
    task = project_task(service, task_id)
    if task.owner_pid is not None or task.status in ('queued', 'running', 'blocked'):
        raise HarnessError('TASK_BUSY', 'Agent 正在修改此作品，请稍后保存。')
    with service.records.connect() as connection:
        claim = connection.execute('SELECT task_id FROM agent_project_claims WHERE project_id=?', (task.project_id,)).fetchone()
    if claim:
        raise HarnessError('PROJECT_EXECUTION_BUSY', '作品有正在执行或待核查的修改，请先查看制作记录。')
    index, selected = resolve_target(service, task, body.target)
    project_id = task.project_id
    affected = []
    if body.target.kind == 'asset' and body.recipe is not None:
        current_recipe = next(v.recipe for v in selected.versions if v.source_version == selected.current_version)
        saved_version = selected.current_version
        if current_recipe != body.recipe:
            saved = service.project_assets.update_recipe(project_id, selected.id,
                UpdateProjectAssetRecipeRequest(expected_version=body.target.source_version, recipe=body.recipe))
            saved_version = saved.entry.current_version
        versions = sorted({item.asset_version for item in index.instances if item.asset_id == selected.id
                           and item.asset_version != saved_version})
        scene_version = index.scene_version
        try:
            for version in versions:
                result = service.environment_scenes.rebind_asset_version(project_id, selected.id,
                    RebindAssetVersionRequest(expected_version=scene_version,
                        from_asset_version=version, to_asset_version=saved_version))
                affected.extend(result.affected_object_ids)
                scene_version = result.scene.version
        except (ValueError, LookupError, EnvironmentSceneError) as error:
            raise HarnessError('DEMO_REBIND_CONFLICT',
                f'配方 v{saved_version} 已保存，但引用更新未全部完成。重读当前源后再次保存可应用剩余引用。{error}') from error
    elif body.target.kind == 'instance' and body.transform is not None:
        service.environment_scenes.transform_object(project_id, selected.id,
            TransformObjectRequest(expected_version=index.scene_version, transform=body.transform))
        affected = [selected.id]
    elif body.target.kind == 'behavior' and body.interaction_distance_m is not None:
        behavior = selected.behavior
        key = body.required_key_asset_id or behavior.required_key_asset_id
        if not any(asset.id == key for asset in index.assets):
            raise HarnessError('TASK_SCOPE_DENIED', '钥匙来源不属于当前作品。')
        service.environment_scenes.update_key_door_behavior(project_id, selected.id,
            UpdateKeyDoorBehaviorRequest(expected_version=index.scene_version,
                required_key_asset_id=key, interaction_distance_m=body.interaction_distance_m,
                open_angle_deg=body.open_angle_deg if body.open_angle_deg is not None else behavior.open_angle_deg))
        affected = [selected.id]
    else:
        raise HarnessError('DEMO_EDIT_UNSUPPORTED', '这个入口不支持所提交的编辑，请使用对应属性或 Agent 源码编辑。')
    service.records.update(task_id, lambda current: None, 'agent.demo.source_saved',
        {'target': body.target.model_dump(mode='json'), 'affected_instance_ids': affected})
    return DemoContentSaved(content=content_index(service, task_id), affected_instance_ids=affected,
        notice='源已保存；更新作品后可试玩新版。')


def validate_target_action(task, action):
    target = task.observations.get('active_demo_target')
    if not isinstance(target, dict):
        return
    cap, inputs = action.capability_id, action.inputs
    source_caps = {'code.demo_runtime.upgrade', 'blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish', 'blender.asset.create', 'blender.asset.export', 'code.file.write', 'project.asset.door.create', 'project.asset.door.update',
        'environment.object.place', 'environment.demo_object.transform',
        'environment.key_door.configure', 'environment.object.remove', 'environment.asset.rebind'}
    if cap not in source_caps:
        return
    allowed = False
    kind = target['kind']
    if kind == 'source':
        allowed = cap == 'code.file.write' and inputs.get('path') == target.get('resolved_path')
    elif kind == 'instance':
        allowed = cap == 'environment.demo_object.transform' and inputs.get('object_id') == target['id']
    elif kind == 'behavior':
        allowed = cap == 'environment.key_door.configure' and inputs.get('object_id') == target.get('resolved_object_id')
    elif kind == 'asset':
        allowed = cap == 'code.demo_runtime.upgrade' or cap in ('blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish', 'project.asset.door.update', 'environment.asset.rebind') and inputs.get('asset_id') == target['id']
    if not allowed:
        raise HarnessError('TASK_SCOPE_DENIED', '本次只允许修改选中内容；不能因选中一个对象而修改其他源。')


async def play_candidate(service, task_id, candidate_id):
    from pathlib import Path
    from .demo_workbench_models import DemoPlaySession
    task = project_task(service, task_id)
    if task.grant is None and task.observations.get('demo_pending_authorization'):
        from .task_models import TaskGrant
        task = task.model_copy(update={'grant': TaskGrant.model_validate(
            task.observations['demo_authorization_history'][-1]['grant'])})
    else:
        task = service._game_task(task_id, manual_operation=True)
    runtime = service.game
    workspace_id = task.authorization_card.workspace_id
    candidates, _, _, _ = runtime._candidate_snapshot(task.project_id, workspace_id)
    candidate = next((item for item in candidates if item.id == candidate_id), None)
    if candidate is None or candidate.status not in ('succeeded', 'superseded'):
        raise HarnessError('DEMO_CANDIDATE_INVALID', '此版本不属于当前作品或没有成功构建。')
    run = runtime._run_by_id(task.project_id, workspace_id, candidate.build_run_id)
    expected = runtime.data_dir / 'builds' / candidate.build_run_id / 'dist'
    if run is None or run.artifact_path != str(expected) or not run.passed:
        raise HarnessError('DEMO_CANDIDATE_INVALID', '版本产物无法核对，请查看构建记录。')
    async with runtime._lock(task.project_id, workspace_id):
        preview = await runtime._start_preview(task, Path(task.grant.workspace_root),
            key=(*runtime.key(task.project_id, workspace_id), 'play', candidate_id), retained_build=run)
    if not preview.preview_url or preview.status != 'running':
        raise HarnessError('PREVIEW_START_FAILED', '试玩未启动，请查看本次运行日志。')
    return DemoPlaySession(candidate_id=candidate.id, sequence=candidate.sequence,
        preview_url=preview.preview_url)
