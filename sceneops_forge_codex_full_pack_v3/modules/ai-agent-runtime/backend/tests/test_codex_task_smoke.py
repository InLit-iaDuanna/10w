"""One explicit-grant Codex task smoke with an injected CLI (no model calls)."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask
from sceneops_harness import HarnessError


class Workspace:
    def create_project(self, name):
        return SimpleNamespace(project_id='prj_codexfixture', name=name)

    def get_project(self, identifier):
        return SimpleNamespace(project_id=identifier)


class CodexTaskSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_only_explicit_full_grant_executes_once_and_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            provider = SimpleNamespace(database_path=root / 'state.sqlite3',
                settings=lambda: SimpleNamespace(provider='codexcli', model='gpt-5.6-sol'),
                execute_task=AsyncMock(return_value={'result': 'fixture completed', 'events': [], 'usage': None}))
            service = AgentTaskService(provider.database_path, Workspace(), root, provider=provider)
            async def execute_fixture(goal, *, workspace_root, on_event, **kwargs):
                (workspace_root / 'fixture.txt').write_text('deterministic fixture', encoding='utf-8')
                await on_event({'type': 'file_change', 'phase': 'completed', 'verification': 'reported',
                    'files': [{'path': 'fixture.txt', 'kind': 'add', 'verification': 'exists'}]})
                snapshot = service.production.snapshot('prj_codexfixture')
                self.assertEqual(snapshot.steps[-1].state, 'running')
                self.assertEqual(snapshot.tasks[-1].observations['codex_activity']['type'], 'file_change')
                return {'result': 'fixture completed', 'events': [], 'usage': None}
            provider.execute_task.side_effect = execute_fixture
            task = service.prepare(PrepareAgentTask(goal='fixture task', execution_mode='codex-full-access'))
            self.assertIsNone(task.authorization_card.max_model_calls)
            self.assertEqual(provider.execute_task.await_count, 0)
            with self.assertRaises(HarnessError):
                service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                    accept_unknown_cost=True))
            service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                accept_unknown_cost=True, accept_full_access=True))
            await asyncio.gather(*list(service.jobs.values()))
            result = service.get(task.id)
            self.assertEqual(result.status, 'review_required', result.reason)
            self.assertEqual(result.cli_invocations_used, 1)
            self.assertEqual(result.model_calls_used, 0)
            self.assertFalse(result.observations['codex']['verified'])
            self.assertEqual(result.actions[0].change_set.risk, 'high')
            self.assertIsNotNone(result.actions[0].approval_id)
            self.assertTrue(result.grant.revoked)
            snapshot = service.production.snapshot(task.project_id)
            self.assertEqual(snapshot.steps[-1].state, 'review_required')
            self.assertEqual(snapshot.steps[-1].verification, 'reported')
            self.assertEqual(snapshot.artifacts[0].name, 'fixture.txt')
            self.assertEqual(snapshot.steps[-1].artifact_ids, [snapshot.artifacts[0].id])
            with self.assertRaises(HarnessError):
                await service.resume(task.id)
            self.assertEqual(provider.execute_task.await_count, 1)
            await service.close()
