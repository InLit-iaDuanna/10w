"""Explicit receipt reconciliation and finite renewal; never replay an unknown write."""
import json
from pathlib import Path
from sceneops_harness import HarnessError
from engine_unity import content_receipt, content_dispatch_absent, confirm_content_editor_closed
from .unity_tasks import unity_target
from .task_models import now,identifier


def reconcile_unity(service,task_id):
    task=service.get(task_id);target=unity_target(service,task)
    recovered={}
    for action in task.actions:
        if action.state=='uncertain' and action.action.capability_id.startswith('unity.content.') and task.grant:
            receipt=content_receipt(target['workspace_root'],request_id=action.request_id,
                task_id=task.id,grant_id=task.grant.id,action_id=action.action.action_id)
            if receipt is None and content_dispatch_absent(target['workspace_root'],request_id=action.request_id):
                receipt={'tool':'unity_content_operation','mode':'cached','effect_state':'NONE',
                    'outcome':'not_dispatched','request_id':action.request_id,
                    'code':'UNITY_REQUEST_NOT_DISPATCHED','reason':'该动作未写入 Unity Editor 请求，场景没有收到这次操作。',
                    'evidence_basis':'no request, result, or write-start marker for this server-issued identity in the task-owned Unity mailbox'}
            if receipt:recovered[action.action.action_id]=receipt
    def apply(current):
        for action in current.actions:
            if action.action.action_id in recovered:
                receipt=recovered[action.action.action_id]
                action.state='succeeded' if receipt['effect_state']=='COMMITTED' else 'failed'
                action.effect_state=receipt['effect_state'];action.reason=receipt['reason'];action.result={'evidence':receipt}
        if recovered and not any(a.effect_state=='UNKNOWN' or a.state=='uncertain' for a in current.actions):
            current.status='review_required';current.reason='已核查 Editor 持久回执，原结果与已保存场景保留；未重放原操作。'
            current.pending_action_id=None
    result=service.records.update(task_id,apply,'agent.unity.receipts_reconciled',{'action_ids':list(recovered)})
    from .task_loop import project_action
    for action in result.actions:
        if action.action.action_id in recovered:project_action(service,result,action)
    return result


def prepare_unity_continuation(service,task_id,request_id):
    task=service.get(task_id);target=unity_target(service,task)
    if not confirm_content_editor_closed(target['workspace_root']):
        raise HarnessError('UNITY_EDITOR_OPEN','请先保存并关闭此任务的 Unity 工程，再申请下一段有限授权。')
    def prepare(current):
        pending=current.observations.get('demo_pending_authorization')
        if pending and pending['request_id']==request_id:return
        if (current.owner_pid is not None or current.pending_action_id is not None
                or any(a.state in ('running','uncertain') or a.effect_state=='UNKNOWN' for a in current.actions)):
            raise HarnessError('ACTION_UNCERTAIN','请先核查原操作结果；续授不会重放未知写入。')
        if pending:raise HarnessError('AUTHORIZATION_CARD_CHANGED','已有待确认的 Unity 授权卡。')
        if current.grant is None:raise HarnessError('TASK_GRANT_INVALID','没有可继续的 Unity 任务。')
        from .demo_continuation import demo_window_usage
        usage=demo_window_usage(current)
        exhausted=usage['model_calls']>=current.grant.budget.max_metered_calls or usage['actions']>=current.grant.budget.max_steps
        if current.grant.expires_at and current.grant.expires_at>now() and not current.grant.revoked and not exhausted:
            raise HarnessError('CONTINUATION_NOT_REQUIRED','当前授权仍有效，请继续使用。')
        window=current.observations.get('demo_authorization_window',{})
        current.observations.setdefault('demo_authorization_history',[]).append({
            'authorization_card':current.authorization_card.model_dump(mode='json'),
            'grant':current.grant.model_dump(mode='json'),'retired_at':now().isoformat(),'window':window})
        current.authorization_card=current.authorization_card.model_copy(update={'id':identifier('card')})
        current.observations['demo_pending_authorization']={'request_id':request_id,
            'authorization_card_id':current.authorization_card.id,'model_calls_start':current.model_calls_used,
            'actions_start':len(current.actions),'repair_rounds_start':current.repair_rounds_used}
        current.grant=None;current.status='awaiting_authorization';current.reason=None;current.cancel_requested=False
    return service.records.update(task_id,prepare,'agent.unity.continuation_prepared',{'request_id':request_id})
