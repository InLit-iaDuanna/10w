"""Public observation port for planning from a real native production workspace."""
from sceneops_harness import HarnessError
from .demo_workbench import content_index


def production_snapshot(service, project_id):
    tasks = sorted((task for task in service.list(project_id)
                    if task.observations.get('native_production')
                    and task.authorization_card.task_profile == 'project-demo-agent'),
                   key=lambda task: task.created_at, reverse=True)
    if not tasks:
        raise HarnessError('PROJECT_DEMO_NOT_READY', '还没有原生制作初版，请先完成一次制作。')
    task = tasks[0]
    if task.status in ('awaiting_authorization', 'queued', 'running', 'blocked', 'cancel_pending') or task.owner_pid:
        raise HarnessError('TASK_BUSY', '请等待当前制作停止后再整理策划或开始卡片续改。')
    if not task.observations.get('native_session_id'):
        raise HarnessError('NATIVE_SESSION_MISSING', '初版没有可恢复的制作会话，请检查制作记录。')
    index = content_index(service, task.id)
    if not index.sources:
        raise HarnessError('PROJECT_DEMO_NOT_READY', '当前工程还没有可关联的源码。')
    # Reject incomplete evidence instead of generating cards from a silently partial project.
    sources = [source.model_dump(mode='json') for source in index.sources]
    if index.sources_truncated or sum(len(source['content']) for source in sources) > 240000:
        raise HarnessError('PRODUCTION_CONTEXT_TOO_LARGE', '当前工程超出整项目策划读取范围，请先缩小制作范围。')
    return {'task_id': task.id, 'workspace_id': index.workspace_id,
            'sources': sources, 'asset_count': len(index.assets), 'instance_count': len(index.instances),
            'unbuilt_changes': index.unbuilt_changes,
            'rounds': [{'task_id': item.id, 'goal': item.goal, 'status': item.status,
                        'reason': item.reason} for item in tasks[:12]]}
