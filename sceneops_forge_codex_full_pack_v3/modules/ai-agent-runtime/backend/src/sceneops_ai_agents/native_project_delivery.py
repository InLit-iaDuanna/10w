"""Fixed, observed game delivery inside a still-authorized native project action."""
import asyncio
from pathlib import Path

from .task_models import now


async def deliver_native_project(service, task_id):
    task = service.check_grant(task_id, 'agent.task.execute')
    if task.authorization_card.task_profile != 'project-demo-agent' or not task.grant.allow_game_execution:
        return None
    service.game.invalidate_workspace(task.grant.workspace_root)
    operations = ['check', 'build', 'preview_start']
    if task.grant.allow_dependency_install and not service.game.dependencies_ready(Path(task.grant.workspace_root)):
        operations.insert(0, 'prepare')
    evidence = None
    for operation in operations:
        task = service.check_grant(task_id, 'agent.task.execute')
        remaining = (None if task.grant.expires_at is None
                     else max(0.01, (task.grant.expires_at - now()).total_seconds()))
        evidence = await asyncio.wait_for(service.game.execute(task, operation), timeout=remaining)
        service.records.update(task_id,
            lambda current: current.observations.update({'game_project': evidence}),
            'agent.game_project.native_delivery', {'operation': operation, 'run_id': evidence['run']['id']})
        if not evidence['run']['passed']:
            break
    return evidence
