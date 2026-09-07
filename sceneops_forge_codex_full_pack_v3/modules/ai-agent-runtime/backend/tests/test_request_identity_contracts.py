"""Request identity and verification contract tests; intentionally not run in this change."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase

from pydantic import ValidationError
from sceneops_ai_agents.production_models import ProductionStep
from sceneops_ai_agents.task_loop import record_action
from sceneops_ai_agents.task_models import (ActionRecord, AgentAction, AgentTaskRecord,
    AuthorizationCard, TaskGrant, VerificationRecord, now)
from sceneops_harness import HarnessError


class RecordFixture:
    def __init__(self, task):
        self.task = task

    def update(self, task_id, mutate, event_type, payload=None):
        assert task_id == self.task.id
        mutate(self.task)
        return self.task


class ProductionFixture:
    def __init__(self):
        self.steps = []

    def snapshot(self, project_id):
        return SimpleNamespace(steps=list(self.steps))

    def upsert_step(self, step):
        self.steps = [item for item in self.steps if item.id != step.id] + [step]


class RequestIdentityContractTests(TestCase):
    def task(self):
        card = AuthorizationCard(workspace_root='/fixture')
        grant = TaskGrant(task_id='task_fixture', project_id='project_fixture',
            workspace_root='/fixture', capability_ids=list(card.capability_ids),
            expires_at=now() + timedelta(minutes=5))
        return AgentTaskRecord(id='task_fixture', project_id='project_fixture', goal='fixture',
            authorization_card=card, grant=grant)

    @staticmethod
    def action(action_id):
        return AgentAction(action_id=action_id, capability_id='blender.scene.inspect',
            rationale='Inspect independently', inputs={})

    def test_new_action_id_with_same_inputs_is_a_new_request(self):
        task = self.task()
        service = SimpleNamespace(records=RecordFixture(task), production=ProductionFixture())
        record_action(service, task.id, self.action('inspect_one'))
        record_action(service, task.id, self.action('inspect_two'))
        self.assertEqual(len(task.actions), 2)
        self.assertNotEqual(task.actions[0].request_id, task.actions[1].request_id)

    def test_same_action_id_cannot_change_immutable_request(self):
        task = self.task()
        service = SimpleNamespace(records=RecordFixture(task), production=ProductionFixture())
        record_action(service, task.id, self.action('inspect'))
        changed = AgentAction(action_id='inspect', capability_id='unity.scene.inspect',
            rationale='Changed request', inputs={})
        with self.assertRaises(HarnessError) as caught:
            record_action(service, task.id, changed)
        self.assertEqual(caught.exception.code, 'REQUEST_ID_CONFLICT')

    def test_same_action_id_can_retry_identical_inputs_without_replacing_audit_rationale(self):
        task = self.task()
        service = SimpleNamespace(records=RecordFixture(task), production=ProductionFixture())
        original = self.action('inspect')
        record_action(service, task.id, original)
        task.actions[0].state = 'failed'
        retry = original.model_copy(update={'rationale': 'Retry after required context became available'})

        record_action(service, task.id, retry)

        self.assertEqual(len(task.actions), 1)
        self.assertEqual(task.actions[0].action.rationale, 'Inspect independently')

    def test_legacy_mutation_effect_is_unknown_and_step_default_is_conservative(self):
        record = ActionRecord.model_validate({'action': {'action_id': 'compose',
            'capability_id': 'unity.prototype.compose', 'rationale': 'legacy', 'inputs': {}},
            'state': 'succeeded', 'attempts': 1})
        self.assertEqual(record.effect_state, 'UNKNOWN')
        step = ProductionStep(id='step', project_id='project_fixture', task_id='task_fixture',
            module_id='world-logic', title='legacy', capability_id='unity.prototype.compose',
            state='completed', updated_at=now().isoformat())
        self.assertEqual(step.effect_state, 'UNKNOWN')
        self.assertEqual(step.verification, 'unverified')
        legacy_pass = step.model_copy(update={'verification': 'passed'})
        legacy_pass = ProductionStep.model_validate(legacy_pass.model_dump())
        self.assertEqual(legacy_pass.verification, 'inconclusive')

    def test_verdict_is_distinct_from_checker_execution(self):
        fields = dict(project_revision='chg_fixture', run_id='request_play', suite_id='suite',
            run_ids=['request_play', 'request_defeat'], suite_version=1,
            checker_version='checker-1', artifact_refs=[])
        result = VerificationRecord(**fields, execution_status='COMPLETED', verdict='FAIL')
        self.assertEqual(result.verdict, 'FAIL')
        with self.assertRaises(ValidationError):
            VerificationRecord(**fields, execution_status='INTERRUPTED', verdict='PASS')


if __name__ == '__main__':
    import unittest
    unittest.main()
