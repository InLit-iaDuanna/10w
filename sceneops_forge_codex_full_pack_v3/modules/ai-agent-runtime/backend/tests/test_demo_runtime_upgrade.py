"""Migration authority and exact source proposals belong to the current task."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sceneops_harness import HarnessError
from sceneops_ai_agents.demo_runtime_upgrade import preview_runtime_upgrade, apply_runtime_upgrade
from sceneops_ai_agents.task_loop import changeset
from sceneops_ai_agents.task_models import AgentAction, ActionRecord, AgentTaskRecord, AuthorizationCard, TaskGrant, now


def fixture():
    card = AuthorizationCard(task_profile='project-demo-agent', workspace_root='/tmp/demo', workspace_id='workspace')
    grant = TaskGrant(task_id='task', project_id='prj_12345678', workspace_root='/tmp/demo', workspace_id='workspace',
                      capability_ids=['code.file.write','code.demo_runtime.preview','code.demo_runtime.upgrade'], expires_at=now())
    task = AgentTaskRecord(id='task', project_id='prj_12345678', goal='升级', authorization_card=card, grant=grant)
    preview = {'project_id':'prj_12345678','workspace_id':'workspace','status':'ready','conflicts':[],
               'files':[{'path':'src/main.ts','previous':'old source','proposed':'new source'}]}
    def update(_, callback, *args):
        callback(task)
    workspace = SimpleNamespace(preview_demo_runtime_upgrade=Mock(return_value=preview),
        apply_demo_runtime_upgrade=Mock(return_value={**preview,'status':'applied'}))
    service = SimpleNamespace(records=SimpleNamespace(update=update), workspace=workspace,
                              game=SimpleNamespace(invalidate_workspace=Mock()))
    return service, task, preview


def test_upgrade_changeset_records_exact_task_owned_source():
    service,task,preview=fixture()
    proposal=preview_runtime_upgrade(service,task)
    entry=ActionRecord(action=AgentAction(action_id='upgrade',capability_id='code.demo_runtime.upgrade',
        rationale='升级现有加载器',inputs={'preview_id':proposal['preview_id']}))
    change=changeset(task,entry)
    assert change.previous_values == {'src/main.ts':'old source'}
    assert change.proposed_values == {'src/main.ts':'new source'}
    assert apply_runtime_upgrade(service,task,proposal['preview_id'])['status']=='applied'
    service.workspace.apply_demo_runtime_upgrade.assert_called_once_with('prj_12345678','workspace',preview)


def test_foreign_stale_and_readonly_proposals_do_not_write():
    service,task,preview=fixture()
    with pytest.raises(HarnessError):
        apply_runtime_upgrade(service,task,'upgrade_'+'0'*32)
    proposal=preview_runtime_upgrade(service,task)
    service.workspace.preview_demo_runtime_upgrade.return_value={**preview,'files':[],'status':'current'}
    assert apply_runtime_upgrade(service,task,proposal['preview_id'])['status']=='stale'
    service.workspace.apply_demo_runtime_upgrade.assert_not_called()
    service.game.invalidate_workspace.assert_not_called()
    task.grant.capability_ids=[]
    with pytest.raises(HarnessError):
        preview_runtime_upgrade(service,task)
