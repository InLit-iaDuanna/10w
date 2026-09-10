"""Selected catalog source -> real FBX -> authoritative Unity Editor state."""
import shutil
from pathlib import Path
from uuid import uuid4
from sceneops_harness import HarnessError
from .unity_tasks import unity_target, unity_source
from .unity_content_models import UnityContentSnapshot, UnityContentInstance


def record_content(service, task_id, readback):
    service.records.update(task_id,lambda task:task.observations.update({'unity_content':readback}),
        'agent.unity.content_observed')


async def dispatch_content(tools, invocation, cancellation):
    try:
        return await _dispatch_content(tools, invocation, cancellation)
    except Exception as error:
        if invocation.capability_id.startswith('unity.content.'):
            from engine_unity import content_rejection
            task=tools.service.get(tools.task_id)
            entry=next(a for a in task.actions if invocation.run_id in a.run_ids)
            receipt=content_rejection(task.grant.workspace_root,request_id=entry.request_id,
                task_id=task.id,grant_id=task.grant.id,action_id=entry.action.action_id)
            if receipt:return receipt
            if isinstance(error,HarnessError) and error.code in ('UNITY_SOURCE_REQUIRED','UNITY_EXPORT_REQUIRED'):
                tools.safe_failures[invocation.run_id]={
                    'tool':'unity_content_operation','mode':'live','effect_state':'NONE',
                    'outcome':'rejected_before_editor_dispatch','request_id':entry.request_id,
                    'code':error.code,'reason':str(error),
                    'evidence_basis':'registered source/export precondition failed before a Unity mailbox request was created'}
        raise


async def _dispatch_content(tools, invocation, cancellation):
    service=tools.service
    task=service.check_grant(tools.task_id,invocation.capability_id)
    target=unity_target(service,task)
    entry=next(a for a in task.actions if invocation.run_id in a.run_ids)
    data=invocation.inputs
    if invocation.capability_id=='blender.asset.derive_unity':
        asset,version,source=unity_source(service,task,data['source_version'])
        session=await tools.session('blender',headless=True)
        # Explicit same-project transfer into this task's source staging, never model paths.
        staged=Path(task.grant.workspace_root)/'sources'/f'{version.asset_version_id}.blend'
        staged.parent.mkdir(parents=True,exist_ok=True)
        from .task_tools import contained
        contained(staged,Path(task.grant.workspace_root))
        if staged.exists():
            if staged.read_bytes()!=source.read_bytes():
                raise HarnessError('UNITY_SOURCE_CONFLICT','任务内登记源副本已改变。')
        else:
            with staged.open('xb') as output,source.open('rb') as original:
                shutil.copyfileobj(original,output)
        candidate='unity_'+uuid4().hex
        await tools.sync(session,'register_source',candidate_id=candidate,source_path=str(staged))
        result=await tools.sync(session,'derive_unity',request_id=entry.request_id,
            asset_id=asset.id,candidate_id=candidate,authorization=tools.authorization(invocation,'blender'))
        tools.validate_readback(task,'blender',result)
        exported={'source_version':version.source_version,'source_asset_version_id':version.asset_version_id,
            'asset_id':asset.id,'fbx_path':result['fbx_path'],'node_ids':version.node_ids,'readback':result}
        service.records.update(task.id,lambda t:t.observations.setdefault('unity_exports',{}).update({str(version.source_version):exported}),
            'agent.unity.source_derived')
        return {'tool':'unity_derivation','mode':'live','effect_state':'COMMITTED',**exported}
    cap=invocation.capability_id
    import_source=None
    if cap=='unity.content.import':
        asset,version,_=unity_source(service,task,data['source_version'])
        exported=task.observations.get('unity_exports',{}).get(str(version.source_version))
        if exported is None or exported['source_asset_version_id']!=version.asset_version_id:
            raise HarnessError('UNITY_EXPORT_REQUIRED','请先从所选登记源版本派生 Unity FBX。')
        import_source=(asset,version,exported)
    session=await tools.session('unity')
    if cap=='unity.content.inspect':
        result=await tools.sync(session,'inspect_content')
    else:
        args={'request_id':entry.request_id,'authorization':tools.authorization(invocation,'unity')}
        if cap=='unity.content.import':
            asset,version,exported=import_source
            result=await tools.sync(session,'import_content',**args,asset_id=asset.id,
                source_version=str(version.source_version),expected_source_version=str(data['expected_source_version']) if data['expected_source_version'] else '',
                fbx_path=exported['fbx_path'],node_ids=version.node_ids,instance_ids=target['instance_ids'])
        elif cap=='unity.content.edit':
            if data['instance_id'] not in target['instance_ids']:
                raise HarnessError('TASK_SCOPE_DENIED','此实例不属于当前 Unity 目标。')
            result=await tools.sync(session,'edit_content',**args,**data)
        elif cap=='unity.content.focus':
            if data['instance_id'] not in target['instance_ids']:
                raise HarnessError('TASK_SCOPE_DENIED','此实例不属于当前 Unity 目标。')
            result=await tools.sync(session,'focus_content',**args,**data)
        elif cap=='unity.content.save':
            result=await tools.sync(session,'save_content',**args,**data)
        elif cap=='unity.content.play':
            result=await tools.sync(session,'play_content',**args,operation=data['operation'],
                input={k:v for k,v in data.items() if k!='operation'})
        else:
            raise HarnessError('TASK_SCOPE_DENIED','Unity 操作不在当前能力内。')
    cancellation.raise_if_cancelled()
    observed=result['readback'] if result.get('mode')=='cached' else result
    tools.validate_readback(task,'unity',observed)
    record_content(service,task.id,observed)
    return {'tool':'unity_content_operation','mode':result['mode'],'effect_state':'NONE' if cap=='unity.content.inspect' else 'COMMITTED',
            'readback_mode':'live','readback':observed}


async def content_snapshot(service,task_id):
    task=service.get(task_id); target=unity_target(service,task)
    asset=service.project_assets.get(task.project_id,target['asset_id'])
    result=task.observations.get('unity_content',{}); mode='cached' if result else 'planned'
    tools=service.tools.get(task_id)
    from .task_models import now
    live_grant=(task.grant is not None and not task.grant.revoked and not task.cancel_requested
                and task.grant.expires_at is not None and task.grant.expires_at>now())
    if tools and 'unity' in tools.sessions and task.owner_pid is None and live_grant:
        from .unity_tasks import validate_unity_grant
        validate_unity_grant(service,task)
        result=await tools.sync(tools.sessions['unity'],'inspect_content')
        tools.validate_readback(task,'unity',result)
        record_content(service,task_id,result);mode='live'
    return UnityContentSnapshot(task_id=task.id,project_id=task.project_id,workspace_id=target['workspace_id'],
        source_asset_id=asset.id,available_source_version=asset.current_version,
        imported_source_version=int(result.get('source_version') or 0),
        project_root=str(Path(target['workspace_root'])/'unity'),scene_path=result.get('scene_path'),
        mode=mode,status='running' if task.owner_pid else 'ready' if result else 'not_started',
        dirty=result.get('dirty',False),playing=result.get('playing',False),compiling=result.get('compiling',False),
        instances=[UnityContentInstance(**{k:v[k] for k in ('instance_id','position','interaction_distance','requires_key')})
                   for v in result.get('instances',[])],readback=result,notice=task.reason)


async def finish_content(tools,task):
    session=await tools.session('unity')
    result=await tools.sync(session,'inspect_content');tools.validate_readback(task,'unity',result)
    if not result.get('instances') or result.get('compiling') or result.get('errors') or result.get('dirty'):
        raise HarnessError('VERIFICATION_INCOMPLETE','Unity 尚未保存有效实例或编译／控制台检查未通过。')
    record_content(tools.service,task.id,result)
    return {'tool':'unity_content_operation','mode':'live','effect_state':'NONE','delivery_status':'production_ready',
        'readback':result,'summary':'Unity 当前实例已保存并回读；玩法结果以单独的实际运行记录为准。'}
