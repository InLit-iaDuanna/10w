"""Native asset commands use existing task actions, sessions, and immutable catalog versions."""
from uuid import uuid4
from sceneops_harness import HarnessError
from asset_library import ProjectAssetVersion, ProjectAssetRegistration, RuntimeArtifactReference
from asset_factory import preserve_native_source
from world_composer import RebindAssetVersionRequest
from .blender_content_models import BlenderBeginInput, BlenderEditInput, BlenderPublishInput

CAPABILITIES = ['blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish']


def candidate(task, candidate_id, asset_id):
    result = task.observations.get('blender_candidates', {}).get(candidate_id)
    if result is None or result['asset_id'] != asset_id:
        raise HarnessError('TASK_SCOPE_DENIED', '此编辑候选不属于选中资产。')
    return result


def store(service, task_id, candidate_id, value):
    service.records.update(task_id,
        lambda task: task.observations.setdefault('blender_candidates', {}).update({candidate_id: value}),
        'agent.blender.source_updated', {'candidate_id': candidate_id, 'status': value['status']})


async def dispatch(tools, invocation, cancellation):
    service = tools.service
    task = service.check_grant(tools.task_id, invocation.capability_id)
    action = next(item for item in task.actions if invocation.run_id in item.run_ids)
    request_id = action.request_id
    manual_request = task.observations.get('manual_blender_requests', {}).get(
        action.action.action_id.removeprefix('manual_blender_'))
    is_manual = bool(manual_request and action.action.action_id.startswith('manual_blender_'))
    data = invocation.inputs
    asset = service.project_assets.get(task.project_id, data['asset_id'])
    if asset.workspace_id != task.grant.workspace_id:
        raise HarnessError('TASK_SCOPE_DENIED', '资产不属于当前登记工作区。')
    async def authorized_session():
        session = await tools.session('blender', headless=not is_manual)
        return session, tools.authorization(invocation, 'blender')
    if invocation.capability_id == 'blender.asset.begin':
        body = BlenderBeginInput.model_validate(data)
        if (body.owner == 'manual') != is_manual:
            raise HarnessError('TASK_SCOPE_DENIED', '编辑归属由实际手工入口决定。')
        existing = next(((key, value) for key, value in task.observations.get('blender_candidates', {}).items()
                         if value['request_id'] == request_id), None)
        if existing:
            if existing[1]['status'] == 'opening':
                raise HarnessError('ACTION_UNCERTAIN', '源打开结果尚未确认；先回读原请求，不能当作完成。')
            return {'tool': 'blender', 'mode': 'live', 'effect_state': 'COMMITTED',
                    'candidate_id': existing[0], **existing[1]}
        if asset.current_version != body.expected_version:
            raise HarnessError('DEMO_SOURCE_CONFLICT', '资产已有新源版本，请重读。')
        active = [v for v in task.observations.get('blender_candidates', {}).values()
                  if v['status'] in ('opening', 'editing')]
        if active:
            raise HarnessError('BLENDER_SOURCE_BUSY', '已有人工或 Agent 编辑候选，请先保存回流或取消。')
        source = next(v for v in asset.versions if v.source_version == body.expected_version)
        if source.source_kind not in ('procedural', 'blender'):
            raise HarnessError('BLENDER_SOURCE_UNSUPPORTED', '此资产尚无受支持的 Blender 编辑源。')
        session, auth = await authorized_session()
        cid = 'blend_' + uuid4().hex
        nodes = source.node_ids or {role: 'node_' + uuid4().hex for role in ('frame', 'leaf', 'hinge')}
        value = {'asset_id': asset.id, 'base_version': body.expected_version, 'owner': body.owner,
                 'status': 'opening', 'request_id': request_id, 'node_ids': nodes}
        store(service, task.id, cid, value)
        if source.source_kind == 'procedural':
            result = await tools.sync(session, 'bootstrap_door', request_id=request_id,
                asset_id=asset.id, candidate_id=cid, node_ids=nodes,
                recipe=source.recipe.model_dump(mode='json', exclude={'kind','seed'}), authorization=auth)
        else:
            await tools.sync(session, 'register_source', candidate_id=cid, source_path=source.blend_path)
            result = await tools.sync(session, 'open_source', request_id=request_id,
                asset_id=asset.id, candidate_id=cid, authorization=auth)
        tools.validate_readback(task, 'blender', result)
        value.update(status='editing', readback=result)
        store(service, task.id, cid, value)
        return {'tool': 'blender', 'mode': 'live', 'effect_state': 'COMMITTED', 'candidate_id': cid, **value}
    cid = data['candidate_id']
    value = candidate(task, cid, asset.id)
    if invocation.capability_id == 'blender.asset.edit':
        body = BlenderEditInput.model_validate(data)
        if value['owner'] != 'agent' or value['status'] != 'editing':
            raise HarnessError('BLENDER_SOURCE_BUSY', '人工或已完成源不能被 Agent 并发覆盖。')
        session, auth = await authorized_session()
        result = await tools.sync(session, 'edit_nodes', request_id=request_id,
            asset_id=asset.id, candidate_id=cid,
            edits=[e.model_dump(mode='json', exclude_none=True) for e in body.edits], authorization=auth)
        tools.validate_readback(task, 'blender', result)
        value.update(readback=result)
        store(service, task.id, cid, value)
        return {'tool': 'blender', 'mode': 'live', 'effect_state': 'COMMITTED', 'candidate_id': cid, **value}
    body = BlenderPublishInput.model_validate(data)
    if value['owner'] == 'manual' and not is_manual:
        raise HarnessError('BLENDER_SOURCE_BUSY', '人工候选只能由手工同步入口保存。')
    if value['status'] not in ('editing', 'exported', 'saved', 'applied'):
        raise HarnessError('ACTION_UNCERTAIN', '候选操作未确认，请先回读。')
    if value['status'] == 'editing':
        session, auth = await authorized_session()
        result = await tools.sync(session, 'export_source', request_id=request_id,
            asset_id=asset.id, candidate_id=cid, formats=['glb'], authorization=auth)
        tools.validate_readback(task, 'blender', result)
        value.update(status='exported', export=result)
        store(service, task.id, cid, value)
    cancellation.raise_if_cancelled()
    if value['status'] == 'exported':
        result = value['export']
        files = preserve_native_source(task.grant.workspace_root, cid, result['blend_path'], result['glb_path'])
        version = ProjectAssetVersion(source_version=value['base_version'] + 1,
            asset_version_id='aver_' + cid, source_kind='blender', operation='blender-edit',
            parent_source_version=value['base_version'], node_ids=value['node_ids'],
            dimensions_m=result['dimensions_m'], vertex_count=result['vertex_count'],
            triangle_count=result['triangle_count'], blend_path=files['blend_path'],
            preview_path=files['preview_path'], runtime_artifacts=[RuntimeArtifactReference(
                artifact_id='artifact_' + cid, artifact_type='render',
                project_relative_path=files['project_relative_path'])])
        registration = ProjectAssetRegistration(
            project_id=task.project_id, workspace_id=task.grant.workspace_id, card_id=asset.card_id,
            source_asset_id=asset.source_asset_id, title=asset.title, source_type=asset.source_type,
            expected_version=value['base_version'], version=version)
        try:
            service.project_assets.register_version(registration)
        except ValueError as error:
            return {'tool':'blender', 'mode':'live', 'effect_state':'COMMITTED',
                    'candidate_id':cid, **value, 'files':files, 'outcome':'source_conflict',
                    'notice':str(error)}
        value.update(status='saved', source_version=version.source_version, files=files)
        store(service, task.id, cid, value)
    scene = service.environment_scenes.get(task.project_id)
    refs = [o for o in scene.objects if o.asset_id == asset.id and
            (body.object_ids is None or o.id in body.object_ids)]
    if body.object_ids is not None and set(body.object_ids) - {o.id for o in refs}:
        raise HarnessError('TASK_SCOPE_DENIED', '指定实例不属于选中共享资产。')
    pending = [o for o in refs if o.asset_version != value['source_version']]
    if pending and scene.version != body.expected_scene_version:
        return {'tool':'blender', 'mode':'live', 'effect_state':'COMMITTED',
                'candidate_id':cid, **value, 'outcome':'references_pending',
                'notice':'新源已保存，场景引用已改变；重读后应用剩余引用。'}
    affected = []
    for number in sorted({o.asset_version for o in pending}):
        result = service.environment_scenes.rebind_asset_version(task.project_id, asset.id,
            RebindAssetVersionRequest(expected_version=scene.version, from_asset_version=number,
                to_asset_version=value['source_version'], object_ids=[o.id for o in pending if o.asset_version == number]))
        scene = result.scene
        affected.extend(result.affected_object_ids)
    value.update(status='applied')
    store(service, task.id, cid, value)
    if 'blender' in tools.sessions:
        await tools.sync(tools.sessions['blender'], 'stop')
        tools.sessions.pop('blender', None)
        tools.session_states.pop('blender', None)
    return {'tool': 'blender', 'mode': 'live', 'effect_state': 'COMMITTED',
            'candidate_id': cid, 'affected_instance_ids': affected, **value}
