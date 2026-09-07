"""Finite authorization windows preserve the same task and lifetime usage."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sceneops_harness import HarnessError, RuntimeBudget
from sceneops_ai_agents.task_models import AgentTaskRecord, AuthorizationCard, TaskGrant, now
from sceneops_ai_agents.demo_continuation import (
    prepare_demo_continuation, apply_demo_continuation_window, demo_window_usage,
)


def fixture():
    card = AuthorizationCard(workspace_root='/tmp/demo', workspace_id='workspace',
                             task_profile='project-demo-agent', max_model_calls=28)
    grant = TaskGrant(task_id='task', project_id='project', workspace_root='/tmp/demo',
                      workspace_id='workspace', capability_ids=[], expires_at=now() + timedelta(minutes=10),
                      budget=RuntimeBudget(max_metered_calls=28, max_steps=32))
    task = AgentTaskRecord(id='task', project_id='project', goal='继续修改选中门',
                           authorization_card=card, grant=grant, status='needs_approval',
                           model_calls_used=28, observations={'demo_edit_target': {'instance_id':'door'}})
    def update(task_id, callback, *args):
        assert task_id == task.id
        callback(task)
        return task
    service = SimpleNamespace(records=SimpleNamespace(update=update), project_demo_context=lambda _: {},
                              project_demo_workspace=lambda *args, **kwargs: {})
    return service, task


def prepare(service, request_id='request-one'):
    with patch('sceneops_ai_agents.demo_tasks.validate_project_demo_alignment'):
        return prepare_demo_continuation(service, 'task', request_id)


def test_explicit_card_replacement_keeps_identity_target_and_lifetime_usage():
    service, task = fixture()
    original_grant = task.grant.id
    task.current_run_id = 'historical-finished-run'
    prepare(service)
    card_id = task.authorization_card.id
    assert task.status == 'awaiting_authorization' and task.grant is None
    assert task.goal == '继续修改选中门'
    assert task.observations['demo_edit_target'] == {'instance_id':'door'}
    assert task.model_calls_used == 28
    assert task.observations['demo_authorization_history'][0]['grant']['id'] == original_grant
    prepare(service)
    assert task.authorization_card.id == card_id
    task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
                           workspace_root='/tmp/demo', workspace_id='workspace', capability_ids=[],
                           expires_at=now()+timedelta(minutes=30), budget=RuntimeBudget(max_metered_calls=28, max_steps=32))
    apply_demo_continuation_window(task)
    assert demo_window_usage(task) == {'model_calls':0, 'actions':0, 'repair_rounds':0}
    task.model_calls_used += 1
    assert demo_window_usage(task)['model_calls'] == 1
    assert task.model_calls_used == 29
    prepare(service)
    assert task.authorization_card.id == card_id


def test_live_remaining_authorization_cannot_be_renewed():
    service, task = fixture()
    task.model_calls_used = 2
    with pytest.raises(HarnessError, match='当前授权尚有可用预算'):
        prepare(service)
    assert task.model_calls_used == 2 and task.grant is not None
    task.grant.expires_at = now() - timedelta(seconds=1)
    prepare(service)
    assert task.status == 'awaiting_authorization'


def test_safely_stopped_revoked_authorization_can_be_explicitly_replaced():
    service, task = fixture()
    task.model_calls_used = 2
    task.grant.revoked = True
    prepare(service)
    assert task.status == 'awaiting_authorization' and task.model_calls_used == 2


def test_uncertain_cleanup_cannot_be_bypassed_and_changed_counts_reject_consent():
    service, task = fixture()
    task.observations['cleanup_uncertain'] = True
    with pytest.raises(HarnessError, match='没有待处理动作'):
        prepare(service)
    task.observations['cleanup_uncertain'] = False
    prepare(service)
    task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
                           workspace_root='/tmp/demo', capability_ids=[], expires_at=now()+timedelta(minutes=30))
    task.model_calls_used += 1
    with pytest.raises(HarnessError, match='状态已改变'):
        apply_demo_continuation_window(task)
