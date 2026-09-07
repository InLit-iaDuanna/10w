"""Versioned runtime upgrades run through the existing scoped task executor."""
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import HarnessError

class DemoRuntimeUpgradeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_id: str = Field(pattern=r'^upgrade_[a-f0-9]{32}$')


def require_runtime_upgrade_scope(task):
    if (task.authorization_card.task_profile != 'project-demo-agent'
            or 'code.file.write' not in task.grant.capability_ids):
        raise HarnessError('TASK_SCOPE_DENIED', '运行代码升级需要当前项目明确的源码写入范围。')


def preview_runtime_upgrade(service, task):
    require_runtime_upgrade_scope(task)
    preview = service.workspace.preview_demo_runtime_upgrade(task.project_id, task.grant.workspace_id)
    preview_id = 'upgrade_' + uuid4().hex
    service.records.update(task.id, lambda t: t.observations.setdefault('runtime_upgrade_previews', {}).update({preview_id:preview}),
        'agent.demo.runtime_upgrade_previewed', {'preview_id':preview_id,'status':preview['status']})
    return {'tool':'demo_runtime_upgrade','mode':'live','effect_state':'NONE','preview_id':preview_id,**preview}


def apply_runtime_upgrade(service, task, preview_id):
    require_runtime_upgrade_scope(task)
    preview = task.observations.get('runtime_upgrade_previews', {}).get(preview_id)
    if preview is None:
        raise HarnessError('TASK_SCOPE_DENIED', '此升级提案不属于当前任务。')
    current = service.workspace.preview_demo_runtime_upgrade(task.project_id, task.grant.workspace_id)
    if preview['status'] == 'conflict' or current != preview:
        return {'tool':'demo_runtime_upgrade','mode':'live','effect_state':'NONE',
                'status':'conflict' if preview['status'] == 'conflict' else 'stale',
                'notice':'运行源码存在冲突或已改变，原文件保留，请重新读取。', 'conflicts':current['conflicts']}
    result = service.workspace.apply_demo_runtime_upgrade(task.project_id, task.grant.workspace_id, preview)
    service.game.invalidate_workspace(task.grant.workspace_root)
    return {'tool':'demo_runtime_upgrade','mode':'live','effect_state':'COMMITTED' if result['status']=='applied' else 'NONE',
            'preview_id':preview_id,**result}
