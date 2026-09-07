"""Explicit finite renewal for an existing project Demo; cumulative history is retained."""
from sceneops_harness import HarnessError
from .task_models import identifier, now


def demo_window_usage(task):
    """Return usage charged to this grant, without changing lifetime counters."""
    window = task.observations.get('demo_authorization_window', {})
    offsets = window if task.grant and window.get('grant_id') == task.grant.id else {}
    return {
        'model_calls': task.model_calls_used - offsets.get('model_calls_start', 0),
        'actions': len(task.actions) - offsets.get('actions_start', 0),
        'repair_rounds': task.repair_rounds_used - offsets.get('repair_rounds_start', 0),
    }


def _require_renewable(task, *, extend_blender=False):
    if task.authorization_card.task_profile != 'project-demo-agent' or task.grant is None:
        raise HarnessError('PROJECT_DEMO_AGENT_REQUIRED', '仅已有真实制作任务可申请有限继续授权。')
    if any(v['status'] in ('opening', 'editing', 'exported', 'saved')
           for v in task.observations.get('blender_candidates', {}).values()):
        raise HarnessError('BLENDER_SOURCE_BUSY', '现有 Blender 候选尚未完成回流，请先核查保存结果。')
    if (task.owner_pid is not None or task.pending_action_id is not None
            or task.cancel_requested or task.observations.get('cleanup_uncertain')
            or task.status not in ('completed', 'review_required', 'needs_approval', 'failed')):
        raise HarnessError('TASK_BUSY', '请先确认执行已停止且没有待处理动作，再申请继续授权。')
    if any(action.state in ('running', 'uncertain') or
           (action.state != 'succeeded' and action.effect_state in ('APPLIED', 'COMMITTED', 'UNKNOWN'))
           for action in task.actions):
        raise HarnessError('ACTION_UNCERTAIN', '已有动作的执行结果尚未确认，不能续授后自动重放。')
    usage = demo_window_usage(task)
    expired = task.grant.expires_at is not None and task.grant.expires_at <= now()
    exhausted = (usage['model_calls'] >= task.grant.budget.max_metered_calls
                 or usage['actions'] >= task.grant.budget.max_steps)
    if not expired and not exhausted and not task.grant.revoked and not extend_blender:
        raise HarnessError('CONTINUATION_NOT_REQUIRED', '当前授权尚有可用预算，请沿现有任务继续。')


def prepare_demo_continuation(service, task_id, request_id, *, allow_blender_edit=False):
    """Prepare a reviewable replacement card; no model, source write, or execution."""
    def prepare(task):
        window = task.observations.get('demo_authorization_window', {})
        if window.get('request_id') == request_id or any(
                item.get('window', {}).get('request_id') == request_id
                for item in task.observations.get('demo_authorization_history', [])):
            return
        pending = task.observations.get('demo_pending_authorization')
        if pending and pending.get('request_id') == request_id:
            return
        if pending:
            raise HarnessError('AUTHORIZATION_CARD_CHANGED', '已有待确认的继续授权，请先审阅该授权卡。')
        _require_renewable(task, extend_blender=allow_blender_edit and not task.authorization_card.allow_blender_edit)
        from .demo_tasks import validate_project_demo_alignment
        context = service.project_demo_context(task.project_id) if service.project_demo_context else {}
        validate_project_demo_alignment(task.grant.alignment_id, context)
        service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                                       expected_root=task.grant.workspace_root)
        task.observations.setdefault('demo_authorization_history', []).append({
            'authorization_card': task.authorization_card.model_dump(mode='json'),
            'grant': task.grant.model_dump(mode='json'),
            'retired_at': now().isoformat(),
            'window': dict(window),
        })
        task.authorization_card = task.authorization_card.model_copy(update={
            'allow_blender_edit': task.authorization_card.allow_blender_edit or allow_blender_edit,
            'scope': task.authorization_card.scope + (' 另允许在隔离 Blender 会话编辑所选资产、保存原生源和 GLB、更新所选共享引用。'
                if allow_blender_edit and not task.authorization_card.allow_blender_edit else ''),
            'id': identifier('card'), 'max_model_calls': 28, 'max_duration_seconds': 1800,
            'cost_notice': '本次继续新增最多 28 次模型请求、32 个动作、30 分钟；历史用量保留，费用和 token 可能未知。',
        })
        from .task_models import project_demo_agent_capabilities
        task.authorization_card.capability_ids = project_demo_agent_capabilities(task.authorization_card)
        task.observations['demo_pending_authorization'] = {
            'request_id': request_id, 'authorization_card_id': task.authorization_card.id,
            'model_calls_start': task.model_calls_used, 'actions_start': len(task.actions),
            'repair_rounds_start': task.repair_rounds_used,
        }
        task.grant = None
        task.browser_authorization = None
        task.browser_interaction_authorization = None
        task.status, task.reason, task.finished_at = 'awaiting_authorization', None, None
    return service.records.update(task_id, prepare, 'agent.project_demo.continuation_prepared',
                                  {'request_id': request_id})


def apply_demo_continuation_window(task):
    """Call in the existing authorize transaction, after it creates the new grant."""
    pending = task.observations.get('demo_pending_authorization')
    if not pending:
        return
    if (task.grant is None or pending['authorization_card_id'] != task.authorization_card.id
            or pending['model_calls_start'] != task.model_calls_used
            or pending['actions_start'] != len(task.actions)
            or pending['repair_rounds_start'] != task.repair_rounds_used):
        raise HarnessError('AUTHORIZATION_CARD_CHANGED', '继续授权的源任务状态已改变，请重新审阅。')
    task.observations['demo_authorization_window'] = {**pending, 'grant_id': task.grant.id,
                                                    'authorized_at': task.grant.authorized_at.isoformat()}
    del task.observations['demo_pending_authorization']
