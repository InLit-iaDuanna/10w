"""Real temporary Git workspace, deterministic harness actions; no model/tool execution."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from uuid import uuid4

from sceneops_harness import HarnessError
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask


class DemoTaskAuthorizationTests(IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repository = SqliteWorkspaceRepository(self.root / 'state.sqlite3')
        self.project = self.repository.create_folder_project(self.root, 'game')
        self.repository.commit_design_version(self.project.project_id, 1, {'title': 'fixture'})
        self.repository.initialize_game_project(self.project.project_id, {
            'target_platform': 'web', 'engine': 'threejs', 'code_architecture': 'object-component',
            'architecture_label': '对象／组件式', 'selection_method': 'manual',
            'rationale': 'fixture', 'tradeoffs': ['fixture'], 'ecs_library': None,
        }, 1)
        self.branch = self.repository.open_card_worktree(self.project.project_id, 'world-3d', '世界')
        self.assets = Path(self.branch['worktree_path']) / 'src/game/sceneops-demo-assets.ts'
        self.assets.unlink()
        self.context = {'technical_plan': {'code_architecture': 'object-component'},
                        'card_alignment_id': uuid4().hex, 'card': {'title': '世界'}}
        self.provider = SimpleNamespace(database_path=self.root / 'state.sqlite3',
            settings=lambda: SimpleNamespace(provider='codebuddycli', model='chosen-model'),
            generate=AsyncMock(side_effect=AssertionError('No model call')))
        self.service = AgentTaskService(self.root / 'state.sqlite3', self.repository, self.root / 'data',
            provider=self.provider, card_context=lambda project, card: self.context)
        self.addAsyncCleanup(self.service.close)

    def request(self, **updates):
        return PrepareAgentTask(**dict({
            'project_id': self.project.project_id, 'card_id': 'world-3d',
            'task_profile': 'card-development', 'goal': '实现已对齐世界 Demo',
            'allow_game_execution': True, 'allow_dependency_install': True,
            'allow_browser_observation': True, 'include_demo_assets': True,
            'alignment_id': self.context['card_alignment_id'],
        }, **updates))

    async def authorize_without_model(self, task):
        self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True), actions=[])
        await asyncio.gather(*list(self.service.jobs.values()))
        return self.service.get(task.id)

    async def test_prepare_is_read_only_and_authorization_records_asset_install(self):
        task = self.service.prepare(self.request())
        self.assertFalse(self.assets.exists())
        self.assertEqual(task.status, 'awaiting_authorization')
        self.assertIsNone(task.grant)
        self.assertEqual(task.provider_model, 'chosen-model')
        self.assertIn('code.demo_assets.install', task.authorization_card.capability_ids)
        self.assertIn('code.browser.observe', task.authorization_card.capability_ids)
        result = await self.authorize_without_model(task)
        self.assertTrue(self.assets.is_file())
        installed = result.actions[0]
        self.assertEqual(installed.action.capability_id, 'code.demo_assets.install')
        self.assertEqual(installed.state, 'succeeded')
        self.assertEqual(installed.effect_state, 'COMMITTED')
        self.assertIsNotNone(installed.change_set)
        self.assertTrue(installed.approval_id)
        self.assertTrue(installed.run_ids)
        self.assertEqual(result.observations['demo_assets']['workspace_root'], self.branch['worktree_path'])
        self.provider.generate.assert_not_awaited()

    async def test_existing_assets_are_preserved_and_no_op_is_success(self):
        self.assets.write_text('export const userAsset = true;\n')
        task = self.service.prepare(self.request())
        result = await self.authorize_without_model(task)
        self.assertEqual(self.assets.read_text(), 'export const userAsset = true;\n')
        installed = result.actions[0]
        self.assertEqual(installed.state, 'succeeded')
        self.assertEqual(installed.effect_state, 'NONE')
        self.assertEqual(installed.result['evidence']['outcome'], 'already_present')
        self.assertEqual(installed.result['evidence']['installed_files'], [])
        self.assertIn('src/game/sceneops-demo-assets.ts', installed.result['evidence']['preserved_files'])

    async def test_repeated_prepare_reuses_card_and_cancelled_result_without_retry(self):
        request = self.request()
        first = self.service.prepare(request)
        repeated = self.service.prepare(request)
        self.assertEqual(first.id, repeated.id)
        self.assertEqual(first.authorization_card.id, repeated.authorization_card.id)
        self.assertEqual(len(self.service.list(self.project.project_id)), 1)
        self.assertEqual(len(self.service.events(first.id).events), 1)
        self.service.cancel(first.id)
        cancelled = self.service.prepare(request)
        self.assertEqual(cancelled.id, first.id)
        self.assertEqual(cancelled.status, 'cancelled')
        self.assertFalse(self.assets.exists())

    async def test_concurrent_prepare_records_only_one_task_and_prepared_event(self):
        from concurrent.futures import ThreadPoolExecutor
        request = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = list(pool.map(lambda _: self.service.prepare(request), range(2)))
        self.assertEqual(tasks[0].id, tasks[1].id)
        self.assertEqual(tasks[0].authorization_card.id, tasks[1].authorization_card.id)
        self.assertEqual(len(self.service.list(self.project.project_id)), 1)
        self.assertEqual(len(self.service.events(tasks[0].id).events), 1)
        self.assertFalse(self.assets.exists())

    async def test_changed_request_or_alignment_cannot_authorize_old_summary(self):
        task = self.service.prepare(self.request())
        with self.assertRaises(HarnessError) as conflict:
            self.service.prepare(self.request(goal='Different goal'))
        self.assertEqual(conflict.exception.code, 'DEMO_PREPARE_CONFLICT')
        self.context = {**self.context, 'card_alignment_id': uuid4().hex}
        with self.assertRaises(HarnessError) as stale:
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        self.assertEqual(stale.exception.code, 'DEMO_ALIGNMENT_CHANGED')
        self.assertIsNone(self.service.get(task.id).grant)
        self.assertFalse(self.assets.exists())
        newer = self.service.prepare(self.request())
        self.assertNotEqual(newer.id, task.id)

    async def test_ordinary_card_has_no_demo_install_capability(self):
        request = self.request(include_demo_assets=False, alignment_id=None)
        task = self.service.prepare(request)
        self.assertNotIn('code.demo_assets.install', task.authorization_card.capability_ids)
        self.assertFalse(self.assets.exists())
