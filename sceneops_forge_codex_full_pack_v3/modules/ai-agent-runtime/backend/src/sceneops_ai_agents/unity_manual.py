"""Manual and Agent edits share the same granted action executor."""
import asyncio
import os
from sceneops_harness import HarnessError,HarnessRuntime
from .task_models import AgentAction
from .unity_tasks import validate_unity_grant
from .unity_content_models import UnityEditInput, UnityPlayInput


async def execute_unity_manual(service,task_id,body):
    from .task_tools import TaskTools
    from .task_loop import record_action,execute_action
    if body.operation=='reconcile':
        from .unity_continuation import reconcile_unity
        return reconcile_unity(service,task_id)
    if body.operation=='renew':
        from .unity_continuation import prepare_unity_continuation
        return prepare_unity_continuation(service,task_id,body.request_id)
    task=service.get(task_id);validate_unity_grant(service,task)
    request=body.model_dump(mode='json',exclude_none=True)
    prior=task.observations.get('unity_manual_requests',{}).get(body.request_id)
    if prior is not None:
        if prior!=request:
            raise HarnessError('REQUEST_ID_CONFLICT','同一请求编号不能更换操作内容。')
        return task
    def claim(current):
        if current.owner_pid is not None or current.status not in ('review_required','completed','failed'):
            raise HarnessError('TASK_BUSY','Unity 任务正在执行或需要核查。')
        if any(a.state in ('running','uncertain') or a.effect_state=='UNKNOWN' for a in current.actions):
            raise HarnessError('ACTION_UNCERTAIN','已有操作结果未知，先检查原操作，不重放。')
        current.observations.setdefault('unity_manual_requests',{})[body.request_id]=request
        current.status='queued'
        if body.operation=='agent':
            current.goal=body.goal
            current.observations['active_goal_action_start']=len(current.actions)
    service.records.update(task_id,claim,'agent.task.authorized')
    service.check_grant(task_id)
    if task_id not in service.tools:
        service.tools[task_id]=TaskTools(service,task_id)
        service.runtimes[task_id]=HarnessRuntime(service.database_path,service.tools[task_id].registry())
    if body.operation=='agent':
        job=asyncio.create_task(service._run(task_id))
        service.jobs[task_id]=job
        job.add_done_callback(lambda _:service.jobs.pop(task_id,None))
        return service.get(task_id)
    service.records.update(task_id,lambda t:(setattr(t,'owner_pid',os.getpid()),setattr(t,'status','running')),
                           'agent.task.started')
    actions=[]
    if body.operation=='import':
        actions.append(('blender.asset.derive_unity',{'source_version':body.source_version}))
        actions.append(('unity.content.import',{'source_version':body.source_version,
            'expected_source_version':int(task.observations.get('unity_content',{}).get('source_version') or 0)}))
    elif body.operation=='edit':
        values={k:request[k] for k in ('instance_id','expected','position','interaction_distance','requires_key') if k in request}
        actions.append(('unity.content.edit',UnityEditInput.model_validate(values).model_dump(mode='json',exclude_none=True)))
    elif body.operation=='focus':
        actions.append(('unity.content.focus',{'instance_id':body.instance_id}))
    elif body.operation in ('save','reopen'):
        actions.append(('unity.content.save',{'reopen':body.operation=='reopen'}))
    elif body.operation in ('play','stop'):
        actions.append(('unity.content.play',{'operation':'enter' if body.operation=='play' else 'exit'}))
    elif body.operation=='act':
        actions.append(('unity.content.play',UnityPlayInput(operation='act',move_x=body.move_x,
            move_z=body.move_z,interact=body.interact,duration_frames=body.duration_frames).model_dump(mode='json')))
    else:
        actions.append(('unity.content.inspect',{}))
    try:
        for index,(cap,inputs) in enumerate(actions):
            action_id=f'unity_manual_{body.request_id}_{index}'
            record_action(service,task_id,AgentAction(action_id=action_id,capability_id=cap,
                rationale='按用户当前 Unity 编辑请求执行并回读实际结果。',inputs=inputs))
            await execute_action(service,task_id,action_id)
            completed=next(item for item in service.get(task_id).actions
                if item.action.action_id==action_id)
            if completed.state!='succeeded':
                break
    finally:
        def release(current):
            current.owner_pid=None
            if any(a.state=='uncertain' or a.effect_state=='UNKNOWN' for a in current.actions):
                current.status='needs_approval';current.reason='Unity 结果未知，保留工程与原操作记录，先核查。'
            elif current.status=='running':
                current.status='review_required'
        service.records.update(task_id,release,'agent.task.worker_released')
    return service.get(task_id)
