"""Native export lifecycle fixture; no real model, tool installation or game build."""
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from sceneops_ai_agents import AuthorizeAgentTask, PrepareAgentTask
from sceneops_harness import HarnessError
import test_project_demo_task as fixture


class NativeExportTaskTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.ProjectDemoTaskSmoke.asyncSetUp
    asyncTearDown = fixture.ProjectDemoTaskSmoke.asyncTearDown

    def prepare(self):
        root = self.root / '导出 workspace'
        root.mkdir(exist_ok=True)
        (root / 'package.json').write_text('{}')
        self.service.export_context = lambda project, export: {
            'workspace_root': str(root), 'platforms': ['mac-arm64'],
            'source_version': {'sequence': 1}, 'history': [], 'settings': {}}
        return self.service.prepare_export_task(self.project.project_id, 'export_fixture', '补齐工具并导出')

    async def test_native_export_success_uses_real_lifecycle_and_skill_channel(self):
        task = self.prepare()
        async def execute(prompt, **kwargs):
            self.assertTrue(kwargs['allow_environment_setup'])
            self.assertIn('sceneops-export-environment', kwargs['execution_instructions'])
            self.assertIn('sceneops-export-result.json', kwargs['execution_instructions'])
            await kwargs['on_event']({'type': 'assistant_message', 'text': 'fixture result'})
            return {'result': 'fixture only'}
        self.provider.execute_task = AsyncMock(side_effect=execute)
        result = await self.service.run_export_task(task.id)
        self.assertEqual(result.status, 'review_required', result.reason)
        self.assertEqual(result.cli_invocations_used, 1)
        self.assertTrue(result.grant.revoked)
        self.assertEqual(result.observations['native_conversation'][0]['text'], 'fixture result')
        self.assertNotIn('project_demo_context', result.observations)
        self.assertNotIn('game_project', result.observations)
        with self.assertRaises(HarnessError):
            await self.service.run_export_task(task.id)

    async def test_missing_resolver_and_changed_scope_fail_before_execution(self):
        with self.assertRaises(HarnessError):
            self.service.prepare_export_task(self.project.project_id, 'export_fixture', '导出')
        task = self.prepare()
        with patch.object(self.service, '_run', new=AsyncMock()):
            self.service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                accept_unknown_cost=True, accept_full_access=True))
            await asyncio.gather(*list(self.service.jobs.values()))
        self.service.records.update(task.id, lambda current: setattr(current.grant, 'export_id', 'wrong'), 'test.scope')
        with self.assertRaises(HarnessError):
            self.service.check_grant(task.id, 'agent.task.execute')
        with self.assertRaises(ValueError):
            PrepareAgentTask(goal='导出', project_id=self.project.project_id,
                task_profile='project-export-agent', execution_mode='agent-full-access')

    async def test_failed_native_can_continue_new_explicit_turn_without_replay(self):
        task = self.prepare()
        self.provider.execute_task = AsyncMock(side_effect=RuntimeError('fixture interrupted tool'))
        failed = await self.service.run_export_task(task.id)
        self.assertNotEqual(failed.status, 'review_required')
        self.assertEqual(failed.cli_invocations_used, 1)
        followup = self.prepare()
        self.provider.execute_task = AsyncMock(return_value={'result': 'rechecked current files'})
        result = await self.service.run_export_task(followup.id)
        self.assertEqual(result.status, 'review_required', result.reason)
        self.assertEqual(self.provider.execute_task.await_count, 1)
        prior = self.service.get(task.id)
        self.assertEqual(prior.actions[0].effect_state, 'UNKNOWN')
        self.assertEqual(result.observations['project_claim_continuation']['from_task_id'], prior.id)

    async def test_cancel_running_native_waits_for_owned_worker_and_never_replays(self):
        from threading import Event
        task = self.prepare()
        started = asyncio.Event()
        stopped = asyncio.Event()
        cancel = Event()
        async def execute(prompt, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        self.provider.execute_task = AsyncMock(side_effect=execute)
        execution = asyncio.create_task(self.service.run_export_task(task.id, cancel_event=cancel))
        await asyncio.wait_for(started.wait(), timeout=5)
        cancel.set()
        result = await asyncio.wait_for(execution, timeout=5)
        self.assertTrue(stopped.is_set())
        self.assertEqual(result.status, 'cancelled', result.reason)
        self.assertIsNone(result.owner_pid)
        self.assertTrue(result.grant.revoked)
        self.assertEqual(self.provider.execute_task.await_count, 1)
        with self.assertRaises(HarnessError):
            await self.service.run_export_task(task.id)

    async def test_cancel_after_cli_completion_waits_for_cleanup(self):
        from threading import Event
        from sceneops_ai_agents.task_tools import TaskTools
        task = self.prepare()
        self.provider.execute_task = AsyncMock(return_value={'result': 'fixture complete'})
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cancel = Event()
        async def stop(tools):
            cleanup_started.set()
            await cleanup_release.wait()
            return []
        with patch.object(TaskTools, 'stop', new=stop):
            execution = asyncio.create_task(self.service.run_export_task(task.id, cancel_event=cancel))
            await asyncio.wait_for(cleanup_started.wait(), timeout=5)
            self.assertEqual(self.service.get(task.id).status, 'review_required')
            cancel.set()
            await asyncio.sleep(0.15)
            self.assertFalse(execution.done())
            cleanup_release.set()
            result = await asyncio.wait_for(execution, timeout=5)
        self.assertEqual(result.status, 'review_required')
        self.assertIsNone(result.owner_pid)
        self.assertFalse(result.cancel_requested)
