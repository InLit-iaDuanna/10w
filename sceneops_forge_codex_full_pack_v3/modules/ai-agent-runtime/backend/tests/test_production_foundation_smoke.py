"""One deterministic local fixture: no model, DCC, network or production data.

Root alone runs the authorized smoke, per the module AGENTS.md.
"""
import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sceneops_harness import HarnessError
from sceneops_ai_agents.production_models import ProductionStep
from sceneops_ai_agents.production_store import ProductionStore
from sceneops_ai_agents.task_models import ActionRecord, AgentAction, AgentTaskRecord, AuthorizationCard, TaskGrant, now
from sceneops_ai_agents.task_repository import AgentTaskRepository
from sceneops_ai_agents.task_router import create_production_router


def fixture_task(project_id, root):
    return AgentTaskRecord(project_id=project_id, goal='本地确定性夹具',
        authorization_card=AuthorizationCard(workspace_root=str(root), execution_mode='codex-full-access',
                                            capability_ids=['codex.task.execute']))


def authorize_fixture(task):
    task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
        workspace_root=task.authorization_card.workspace_root, execution_mode='codex-full-access',
        capability_ids=['codex.task.execute'], expires_at=now() + timedelta(minutes=5))
    task.status = 'queued'


def native_card_task(project_id, root, conversation_id):
    branch = 'codex/card-core-gameplay'
    return AgentTaskRecord(project_id=project_id, goal='继续当前对话',
        authorization_card=AuthorizationCard(workspace_root=str(root), card_id='core-gameplay',
            branch=branch, task_profile='card-development', execution_mode='agent-full-access',
            capability_ids=['agent.task.execute']),
        observations={'card_context': {'conversation_id': conversation_id}})


def authorize_native_fixture(task):
    task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
        workspace_root=task.authorization_card.workspace_root,
        card_id=task.authorization_card.card_id, branch=task.authorization_card.branch,
        execution_mode='agent-full-access', capability_ids=['agent.task.execute'],
        expires_at=now() + timedelta(minutes=5))
    task.status = 'queued'


def stop_native_fixture_uncertain(task):
    task.status = 'needs_approval'
    task.grant.revoked = True
    task.actions.append(ActionRecord(action=AgentAction(action_id='native_execution',
        capability_id='agent.task.execute', rationale='夹具：原生执行超时', inputs={'goal': task.goal}),
        state='uncertain', effect_state='UNKNOWN', attempts=1))
    task.observations['native_workspace_changes'] = {
        'available': True, 'source': 'git-status',
        'files': [{'path': 'src/main.ts', 'change': 'modified', 'git_status': ' M'}],
        'totals': {'added': 0, 'modified': 1, 'deleted': 0},
    }


class ProductionFoundationSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_stopped_native_claim_continues_only_in_same_conversation_and_scope(self):
        with tempfile.TemporaryDirectory(prefix='sceneops-native-continuation-') as directory:
            root = Path(directory).resolve()
            records = AgentTaskRepository(root / 'fixture.sqlite3')
            project_id = 'prj_same_conversation'
            workspace = root / 'core-gameplay'
            previous = records.create(native_card_task(project_id, workspace, 'conversation-one'))
            records.update(previous.id, authorize_native_fixture, 'agent.task.authorized')
            records.update(previous.id, stop_native_fixture_uncertain, 'agent.task.worker_released')
            self.assertFalse(records.safe_to_release(records.get(previous.id)))

            continuation = records.create(native_card_task(project_id, workspace, 'conversation-one'))
            continuation = records.update(continuation.id, authorize_native_fixture, 'agent.task.authorized')
            self.assertTrue(records.owns_claim(continuation))
            self.assertEqual(continuation.observations['project_claim_continuation']['from_task_id'], previous.id)
            released = records.get(previous.id)
            self.assertEqual(released.status, 'review_required')
            self.assertEqual(released.actions[-1].effect_state, 'UNKNOWN')
            self.assertEqual(released.observations['project_claim_handoff']['to_task_id'], continuation.id)
            self.assertTrue(records.safe_to_release(released))

            other_project = 'prj_other_conversation'
            blocked_workspace = root / 'other-card'
            blocked = records.create(native_card_task(other_project, blocked_workspace, 'conversation-one'))
            records.update(blocked.id, authorize_native_fixture, 'agent.task.authorized')
            records.update(blocked.id, stop_native_fixture_uncertain, 'agent.task.worker_released')
            different_conversation = records.create(native_card_task(
                other_project, blocked_workspace, 'conversation-two'))
            with self.assertRaises(HarnessError) as busy:
                records.update(different_conversation.id, authorize_native_fixture, 'agent.task.authorized')
            self.assertEqual(busy.exception.code, 'PROJECT_EXECUTION_BUSY')
            self.assertIsNone(records.get(different_conversation.id).grant)

    async def test_project_migration_claims_versions_and_resumable_events(self):
        with tempfile.TemporaryDirectory(prefix='sceneops-production-fixture-') as directory:
            data_dir = Path(directory).resolve()
            database = data_dir / 'fixture.sqlite3'
            workspace_base = data_dir / 'agent-workspaces'
            root = workspace_base / 'prj_fixture'
            root.mkdir(parents=True)
            first = fixture_task('prj_fixture', root)
            with sqlite3.connect(database) as connection:
                connection.execute('CREATE TABLE agent_tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL)')
                connection.execute('INSERT INTO agent_tasks VALUES(?,?,?)', (first.id, first.project_id, first.model_dump_json()))
            records = AgentTaskRepository(database)
            self.assertEqual(records.get(first.id).goal, first.goal)
            second = records.create(fixture_task(first.project_id, root))
            self.assertEqual(len(records.list(first.project_id)), 2)
            self.assertFalse(records.owns_workspace(first.project_id, root))
            first = records.update(first.id, authorize_fixture, 'agent.task.authorized')
            self.assertTrue(records.owns_claim(first))
            self.assertTrue(records.owns_workspace(first.project_id, root))
            with self.assertRaises(HarnessError) as busy:
                records.update(second.id, authorize_fixture, 'agent.task.authorized')
            self.assertEqual(busy.exception.code, 'PROJECT_EXECUTION_BUSY')
            self.assertIsNone(records.get(second.id).grant)
            records.update(first.id, lambda task: setattr(task, 'status', 'review_required'), 'agent.task.worker_released')
            second = records.update(second.id, authorize_fixture, 'agent.task.authorized')
            self.assertTrue(records.owns_claim(second))
            self.assertFalse(records.owns_claim(first))

            def unknown_write(task):
                task.status = 'failed'
                task.actions.append(ActionRecord(action=AgentAction(action_id='uncertain_write',
                    capability_id='codex.task.execute', rationale='夹具：未知写入', inputs={'goal': task.goal}),
                    state='uncertain', attempts=1))
            records.update(second.id, unknown_write, 'agent.task.worker_released')
            third = records.create(fixture_task(first.project_id, root))
            with self.assertRaises(HarnessError):
                records.update(third.id, authorize_fixture, 'agent.task.authorized')

            proven_root = workspace_base / 'prj_historical'
            proven_root.mkdir()
            historical = fixture_task('prj_historical', proven_root)
            authorize_fixture(historical)
            historical.status = 'review_required'
            historical.observations = {'codex_prechange': {'workspace_root': str(proven_root), 'entries': []},
                                       'codex': {'workspace_root': str(proven_root)}}
            records.create(historical)
            foreign_root = workspace_base / 'prj_foreign'
            foreign_root.mkdir()
            records.recover_workspace_ownership(workspace_base)
            self.assertTrue(records.owns_workspace(historical.project_id, proven_root))
            self.assertFalse(records.owns_workspace('prj_foreign', foreign_root))

            store = ProductionStore(database, data_dir, records)
            step = ProductionStep(id='step_fixture', project_id=first.project_id, task_id=first.id,
                module_id='integration-ops', title='文件版本夹具', capability_id='codex.task.execute',
                state='review_required', verification='reported', mode='live', updated_at=now().isoformat())
            store.upsert_step(step)
            source = root / 'note.txt'
            source.write_text('version one', encoding='utf-8')
            artifact_one = store.record_artifact(first, step.id, step.module_id, source)
            before = store.snapshot(first.project_id)
            source.write_text('version two', encoding='utf-8')
            artifact_two = store.record_artifact(first, step.id, step.module_id, source)
            self.assertEqual(artifact_one.id, artifact_two.id)
            self.assertEqual((artifact_one.version, artifact_two.version), (1, 2))
            stored, _ = store.artifact_content(first.project_id, artifact_one.id, 1)
            with stored:
                self.assertEqual(stored.read(), b'version one')
            with self.assertRaises(HarnessError):
                store.artifact_content('prj_foreign', artifact_one.id)
            link = root / 'linked.txt'
            link.symlink_to(source)
            with self.assertRaises(HarnessError):
                store.record_artifact(first, step.id, step.module_id, link)
            after = store.snapshot(first.project_id)
            self.assertGreater(after.cursor, before.cursor)
            self.assertEqual([artifact.version for artifact in after.artifacts], [1, 2])
            self.assertIn(artifact_one.id, after.steps[0].artifact_ids)
            self.assertTrue(all(event.sequence > before.cursor for event in store.events(first.project_id, before.cursor).events))

            service = SimpleNamespace(production=store, workspace=SimpleNamespace(get_project=lambda project_id: project_id))
            router = create_production_router(service)
            endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/events/stream'))
            request = SimpleNamespace(headers={'last-event-id': str(before.cursor)}, is_disconnected=AsyncMock(return_value=False))
            response = await endpoint(first.project_id, request, after=0)
            event_text = await anext(response.body_iterator)
            await response.body_iterator.aclose()
            self.assertIn(f'id: {after.cursor}\n', event_text)
            self.assertIn('event: production\n', event_text)
            event_data = json.loads(event_text.split('data: ', 1)[1])
            self.assertEqual(event_data['payload']['artifact']['version'], 2)
            self.assertEqual(event_data['project_id'], first.project_id)
            store.upsert_step(step.model_copy(update={'state': 'completed'}))
            self.assertIn(artifact_one.id, store.snapshot(first.project_id).steps[0].artifact_ids)


if __name__ == '__main__':
    unittest.main()
