"""Explicit manual editor entry through the existing approved task action executor."""
import os
from sceneops_harness import HarnessError, HarnessRuntime
from .task_models import AgentAction, now
from .task_tools import TaskTools
from .task_loop import record_action, execute_action
from .demo_workbench import project_task, resolve_target

async def execute_manual(service, task_id, body):
    task = project_task(service, task_id)
    if body.operation == 'reconcile':
        from .blender_reconciliation import reconcile_edits
        return await reconcile_edits(service, task)
    if body.operation == 'close_candidate':
        from .blender_content import candidate
        def close(current):
            if current.owner_pid is not None or any(a.state in ('running','uncertain') for a in current.actions):
                raise HarnessError('TASK_BUSY', '先核查并结束当前操作。')
            value = candidate(current, body.candidate_id, body.target.id)
            if value['status'] != 'exported':
                raise HarnessError('BLENDER_SOURCE_BUSY', '只能结束已保存导出的候选，未保存源须先保存。')
            value['status'] = 'closed'
        return service.records.update(task_id, close, 'agent.task.worker_released')
    cap = {'begin':'blender.asset.begin','edit':'blender.asset.edit','publish':'blender.asset.publish'}[body.operation]
    if task.observations.get('native_production') and body.operation == 'begin':
        task = enable_native_blender(service, task)
    if (task.grant is None or task.grant.revoked or task.cancel_requested
            or (task.grant.expires_at is not None and task.grant.expires_at <= now())):
        raise HarnessError('TASK_GRANT_INVALID', '本次 Blender 授权不存在或已到期。')
    if cap not in task.grant.capability_ids:
        raise HarnessError('TASK_SCOPE_DENIED', '本次授权未包含 Blender 编辑，请先审阅扩展授权。')
    action_id = 'manual_blender_' + body.request_id
    old = next((a for a in task.actions if a.action.action_id == action_id), None)
    request = body.model_dump(mode='json')
    prior = task.observations.get('manual_blender_requests', {}).get(body.request_id)
    if prior is not None and prior != request:
        raise HarnessError('REQUEST_ID_CONFLICT', '同一手工请求编号不能更换内容。')
    if old is not None:
        if old.state == 'succeeded':
            return task
        raise HarnessError('ACTION_UNCERTAIN', '此前操作尚未成功确认，请查看原动作及保存源，不自动重放。')
    if body.target.kind != 'asset':
        raise HarnessError('TASK_SCOPE_DENIED', '请选择实际资产。')
    _, asset = resolve_target(service, task, body.target, check_version=body.operation == 'begin')
    inputs = {'asset_id': asset.id, 'expected_version': body.target.source_version, 'owner': 'manual'}
    if body.operation == 'publish':
        inputs = {'asset_id': asset.id, 'candidate_id': body.candidate_id,
                  'expected_scene_version': body.target.expected_scene_version, 'apply_to_scene':body.apply_to_scene}
    elif body.operation == 'edit':
        inputs = {'asset_id':asset.id, 'candidate_id':body.candidate_id,
                  'edits':[e.model_dump(mode='json',exclude_none=True) for e in body.edits]}
    def claim(current):
        if any(a.state in ('running', 'uncertain') or a.effect_state == 'UNKNOWN' for a in current.actions):
            raise HarnessError('ACTION_UNCERTAIN', '已有动作结果未知；先核查原操作，不能另起写入。')
        if current.owner_pid is not None or current.status not in ('completed', 'review_required'):
            raise HarnessError('TASK_BUSY', '作品有正在执行或待核查的操作。')
        current.observations.setdefault('manual_blender_requests', {})[body.request_id] = request
        current.observations['active_demo_target'] = body.target.model_dump(mode='json')
        current.status = 'queued'
    service.records.update(task_id, claim, 'agent.task.authorized')
    service.records.update(task_id, lambda t: (setattr(t, 'owner_pid', os.getpid()), setattr(t, 'status', 'running')),
                           'agent.task.started')
    if task_id not in service.tools:
        service.tools[task_id] = TaskTools(service, task_id)
    if task_id not in service.runtimes:
        service.runtimes[task_id] = HarnessRuntime(service.database_path, service.tools[task_id].registry())
    try:
        record_action(service, task_id, AgentAction(action_id=action_id, capability_id=cap,
            rationale='用户显式打开 Blender 编辑源。' if body.operation == 'begin' else '用户显式保存并导出 Blender 源，更新所选共享引用。',
            inputs=inputs))
        await execute_action(service, task_id, action_id)
    finally:
        def release(current):
            current.owner_pid = None
            if any(a.state == 'uncertain' or a.effect_state == 'UNKNOWN' for a in current.actions):
                current.status = 'needs_approval'
                current.reason = 'Blender 操作结果未确认，保留源与执行占用；请先核查。'
            elif current.status == 'running':
                current.status = 'review_required'
        service.records.update(task_id, release, 'agent.task.worker_released')
    return service.get(task_id)


def enable_native_blender(service, task):
    """An explicit editor click renews the existing authorization, not the CLI session."""
    from datetime import timedelta
    from uuid import uuid4
    from .demo_continuation import prepare_demo_continuation
    from .task_models import AuthorizeAgentTask
    expires = task.observations.get('native_blender_expires_at')
    if task.grant and not task.grant.revoked and task.authorization_card.allow_blender_edit and expires:
        from datetime import datetime
        if datetime.fromisoformat(expires) > now():
            return task
    prepare_demo_continuation(service, task.id, 'blender_editor_'+uuid4().hex, allow_blender_edit=True)
    pending=service.get(task.id)
    task=service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=pending.authorization_card.id,
        accept_unknown_cost=True,accept_full_access=pending.authorization_card.permission_mode=='full'))
    return service.records.update(task.id, lambda current: current.observations.update(
        native_blender_expires_at=(now()+timedelta(minutes=30)).isoformat()),
        'agent.blender.editor_authorized', {'duration_minutes':30})
