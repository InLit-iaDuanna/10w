"""Read the owned DCC receipt; never replay an uncertain geometry edit."""
from sceneops_harness import HarnessError
from .task_tools import TaskTools


async def reconcile_edits(service, task):
    if task.owner_pid is not None:
        raise HarnessError('TASK_BUSY', '当前操作仍在执行，稍后核查回执。')
    pending = [a for a in task.actions if (a.state == 'uncertain' or (a.state == 'running' and not a.run_ids))
               and a.action.capability_id in ('blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish')]
    if not pending:
        return task
    tools = service.tools.setdefault(task.id, TaskTools(service, task.id))
    session = await tools.session('blender', read_only=True)
    recovered = {}
    for action in pending:
        receipt = await tools.sync(session, 'request_status', request_id=action.request_id)
        if receipt['status'] in ('not_found', 'cancelled'):
            recovered[action.action.action_id] = dict(receipt, effect_state='NONE',
                reason='Blender 队列及持久回执确认该请求未执行。')
        elif receipt['status'] == 'import_not_saved' and action.action.capability_id == 'blender.asset.begin':
            value = task.observations.get('blender_candidates',{}).get(receipt['result']['candidate_id'])
            if value and value['status']=='opening' and value['request_id']==action.request_id:
                recovered[action.action.action_id] = dict(receipt,effect_state='COMMITTED',
                    reason='导入未生成可编辑源；保留原 GLB 和原资产版本，结束此导入候选。')
        elif receipt['status'] == 'completed':
            if action.action.capability_id == 'blender.asset.begin':
                continue
            tools.validate_readback(task, 'blender', dict(receipt,
                workspace_root=receipt['result'].get('workspace_root')))
            if action.action.capability_id == 'blender.asset.publish':
                candidate = task.observations['blender_candidates'].get(action.action.inputs['candidate_id'])
                # The persisted candidate separates a completed DCC export from
                # catalog publication. Recover only an export recorded before failure.
                if not candidate or candidate['status'] != 'exported':
                    continue
            recovered[action.action.action_id] = dict(receipt, effect_state='COMMITTED',
                reason='已核查 Blender 保存／导出结果；资产是否采用以候选状态为准。')
    def apply(current):
        for action in current.actions:
            receipt = recovered.get(action.action.action_id)
            if receipt is None:
                continue
            action.effect_state = receipt['effect_state']
            action.state = 'succeeded' if action.effect_state == 'COMMITTED' and receipt['status']!='import_not_saved' else 'failed'
            action.reason = receipt['reason']
            action.result = {'evidence': receipt}
            if (action.effect_state == 'NONE' or receipt['status']=='import_not_saved') and action.action.capability_id == 'blender.asset.begin':
                for candidate in current.observations.get('blender_candidates', {}).values():
                    if candidate['request_id'] == action.request_id:
                        candidate['status'] = 'closed'
            if action.effect_state == 'COMMITTED' and action.action.capability_id == 'blender.asset.edit':
                candidate = current.observations['blender_candidates'][action.action.inputs['candidate_id']]
                candidate['readback'] = receipt['result']
        if recovered and not any(a.state == 'uncertain' or a.effect_state == 'UNKNOWN' for a in current.actions):
            current.status = 'review_required'
            current.pending_action_id = None
            current.reason = '已核查 Blender 原请求，未重放操作。'
    return service.records.update(task.id, apply, 'agent.blender.receipts_reconciled',
        {'action_ids': list(recovered)})
