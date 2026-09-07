"""S2 product route, authorization and isolated browser regression checks."""
import asyncio
from datetime import timedelta
import importlib
import os
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sceneops_ai_agents import PrepareAgentTask, create_agent_task_router
from sceneops_ai_agents import AgentTaskService, AuthorizeAgentTask
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_agents.task_models import GameOperationRequest, now
from sceneops_harness import HarnessError

fixture = importlib.import_module('modules.ai-agent-runtime.backend.tests.test_game_project_runtime_smoke')


class BrowserObservationTests(fixture.GameProjectRuntimeSmoke):
    async def authorize_empty(self, task):
        # Complete a freshly authorized fixture task; an empty failed task revokes
        # its grant and must not be revived just to make observation tests pass.
        return await self.run_actions(task, [
            fixture.action('write', 'code.file.write', path='src/main.ts',
                expected_content='export const value: number = 1;\n', content='export const value: number = 2;\n'),
            fixture.action('prepare', 'code.dependencies.prepare'),
            fixture.action('check', 'code.project.check'),
            fixture.action('build', 'code.project.build'),
            fixture.action('preview', 'code.preview.start'),
            fixture.action('finish', 'agent.finish', summary='fixture build ready'),
        ])
    def prepare(self, card='card_one', *, browser=True):
        return self.service.prepare(PrepareAgentTask(project_id='prj_fixture0001', card_id=card,
            task_profile='card-development', goal='观察当前登记构建', allow_game_execution=True,
            allow_dependency_install=True, allow_browser_observation=browser))

    async def ready(self, *, browser=True):
        task = self.prepare(browser=browser)
        await self.authorize_empty(task)
        for operation in ('prepare', 'build', 'preview_start'):
            await self.service.game_operation(task.id, GameOperationRequest(operation=operation))
        return self.service.get(task.id)

    async def test_browser_route_and_retained_build(self):
        task = await self.ready()
        preview = self.service.game.snapshot(task).preview
        (self.worktrees / 'card_one/dist/index.html').write_text('unregistered replacement')
        async def capture(runtime, url, screenshot):
            self.assertEqual(url, preview.preview_url)
            return {'status':'succeeded', 'loaded':True, 'screenshot_collected':False,
                    'diagnostics_status':'missing', 'gameplay_verified':False, 'visual_reviewed':False}
        app = FastAPI()
        app.include_router(create_agent_task_router(self.service))
        with patch('sceneops_ai_agents.browser_observation.capture', capture):
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                response = await client.post(f'/api/agent/tasks/{task.id}/game', json={'operation':'observe'})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()['observation']
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['preview_run_id'], preview.id)
        self.assertEqual(result['build_run_id'], preview.build_run_id)
        self.assertEqual(self.service.game.snapshot(task).preview.id, preview.id)
        self.assertIn('Fixture game', Path(self.service.game.snapshot(task).build.artifact_path).joinpath('index.html').read_text())

    async def test_browser_no_authorization_or_expired_grant(self):
        task = await self.ready(browser=False)
        with self.assertRaises(HarnessError) as missing:
            await self.service.observe_game(task.id)
        self.assertEqual(missing.exception.code, 'BROWSER_NOT_AUTHORIZED')
        task = await self.ready()
        self.service.records.update(task.id,
            lambda current: setattr(current.browser_authorization, 'expires_at', now() - timedelta(seconds=1)), 'fixture.expired')
        with self.assertRaises(HarnessError) as expired:
            await self.service.observe_game(task.id)
        self.assertEqual(expired.exception.code, 'BROWSER_AUTHORIZATION_EXPIRED')

    async def test_browser_mismatched_task_and_changed_build(self):
        task = await self.ready()
        active = self.service.game.previews[(task.project_id, task.grant.card_id)]
        active['run'].task_id = 'task_other'
        result = await self.service.observe_game(task.id)
        self.assertEqual(result['run']['failure_code'], 'BROWSER_TARGET_MISMATCH')
        active['run'].task_id = task.id
        async def changed(runtime, url, screenshot):
            Path(runtime._current_build(task).artifact_path).joinpath('index.html').write_text('changed during capture')
            return {'status':'succeeded', 'screenshot_collected':False}
        with patch('sceneops_ai_agents.browser_observation.capture', changed):
            result = await self.service.observe_game(task.id)
        self.assertEqual(result['run']['failure_code'], 'BUILD_CHANGED_DURING_OBSERVATION')
        self.assertTrue(result['run']['source_stale'])

    async def test_browser_revoke_and_capability_contract(self):
        task = await self.ready()
        self.assertTrue(task.grant.revoked)
        self.assertFalse(task.browser_authorization.revoked)
        self.assertEqual(task.browser_authorization.expires_at, task.grant.expires_at)
        from sceneops_ai_agents.task_tools import TaskTools
        registry = TaskTools(self.service, task.id).registry()
        self.assertIn('code.browser.observe', [item.id for item in registry.list()])
        from sceneops_ai_agents.task_models import EmptyActionInput
        with self.assertRaises(ValueError):
            EmptyActionInput.model_validate({'url':'http://arbitrary/'})
        preview = self.service.game.snapshot(task).preview
        self.service.revoke_browser_authorization(task.id)
        with self.assertRaises(HarnessError) as revoked:
            await self.service.observe_game(task.id)
        self.assertEqual(revoked.exception.code, 'BROWSER_AUTHORIZATION_EXPIRED')
        self.assertEqual(self.service.game.snapshot(task).preview.id, preview.id)
        self.assertEqual(self.service.get(task.id).status, 'review_required')

    async def test_browser_missing_runtime_is_explicit(self):
        task = await self.ready()
        with patch.dict(os.environ, {'SCENEOPS_PLAYWRIGHT_MODULE':'/not-installed/playwright'}):
            result = await self.service.observe_game(task.id)
        self.assertEqual(result['run']['failure_code'], 'BROWSER_UNAVAILABLE')
        self.assertEqual(result['run']['artifact_ids'], [])

    async def test_browser_cancel_only_own_session_and_timeout(self):
        task = await self.ready()
        preview = self.service.game.previews[(task.project_id, task.grant.card_id)]
        started = asyncio.Event()
        async def wait(*args):
            started.set()
            await asyncio.Event().wait()
        with patch('sceneops_ai_agents.browser_observation.capture', wait):
            job = asyncio.create_task(self.service.observe_game(task.id))
            await asyncio.wait_for(started.wait(), 2)
            self.service.cancel_browser_observation(task.id)
            result = await job
        self.assertEqual(result['run']['failure_code'], 'BROWSER_CANCELLED')
        self.assertIsNone(preview['process'].returncode)
        async def timeout(*args):
            raise TimeoutError()
        with patch('sceneops_ai_agents.browser_observation.capture', timeout):
            result = await self.service.observe_game(task.id)
        self.assertEqual(result['run']['failure_code'], 'BROWSER_TIMEOUT')

    @unittest.skipUnless(os.environ.get('SCENEOPS_S2_LIVE') == '1', 'explicit live browser acceptance only')
    async def test_browser_live_no_hooks_errors_and_screenshot(self):
        task = self.prepare()
        await self.authorize_empty(task)
        await self.service.game_operation(task.id, GameOperationRequest(operation='prepare'))
        original = self.service.game._command
        async def build_with_errors(run, args, **kwargs):
            result = await original(run, args, **kwargs)
            if 'vite' in args:
                (self.worktrees / 'card_one/dist/index.html').write_text('''<!doctype html>
                <title>S2 real browser</title><h1>Actual build</h1>
                <script>console.error('S2_CONSOLE_ERROR');setTimeout(()=>{throw Error('S2_PAGE_ERROR')},10);
                fetch('http://127.0.0.1:1/private');window.open('https://example.com');</script>
                <img src="missing.png">''')
            return result
        with patch.object(self.service.game, '_command', build_with_errors):
            await self.service.game_operation(task.id, GameOperationRequest(operation='build'))
        await self.service.game_operation(task.id, GameOperationRequest(operation='preview_start'))
        result = await self.service.observe_game(task.id)
        run = result['run']
        self.assertEqual(run['status'], 'succeeded', run)
        evidence = run['observation']
        self.assertTrue(evidence['screenshot_collected'])
        self.assertIn('S2_CONSOLE_ERROR', evidence['console_errors'])
        self.assertIn('S2_PAGE_ERROR', evidence['page_errors'])
        self.assertTrue(evidence['network_errors'])
        self.assertFalse(evidence['visual_reviewed'])
        self.assertEqual(len(run['artifact_ids']), 1)
        stream, artifact = self.service.production.artifact_content(task.project_id, run['artifact_ids'][0])
        with stream:
            self.assertEqual(stream.read(8), b'\x89PNG\r\n\x1a\n')

    @unittest.skipUnless(os.environ.get('SCENEOPS_S2_LIVE') == '1', 'explicit live browser cancellation only')
    async def test_browser_live_cancellation_reaps_worker(self):
        task = await self.ready()
        job = asyncio.create_task(self.service.observe_game(task.id))
        async with asyncio.timeout(5):
            while not self.service.game.processes:
                await asyncio.sleep(.01)
        process = next(iter(self.service.game.processes.values()))
        await asyncio.sleep(.3)
        self.service.cancel_browser_observation(task.id)
        self.service.cancel_browser_observation(task.id)
        result = await job
        self.assertEqual(result['run']['failure_code'], 'BROWSER_CANCELLED')
        self.assertIsNotNone(process.returncode)
        self.assertEqual(self.service.game.processes, {})
        self.assertEqual(self.service.game.snapshot(task).preview.status, 'running')


class ArchitectureBrowserTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.environ.get('SCENEOPS_S2_GAME_DEPENDENCIES'), 'existing game dependencies required')
    async def test_both_architectures_via_product_http(self):
        for architecture in ('object-component', 'ecs'):
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory(prefix='sceneops-s2-architecture-') as directory:
                root = Path(directory).resolve()
                repository = SqliteWorkspaceRepository(root / 'state.sqlite3')
                project = repository.create_folder_project(root, 'game')
                repository.commit_design_version(project.project_id, 1, {'version':1})
                repository.initialize_game_project(project.project_id, {
                    'target_platform':'web', 'engine':'threejs', 'code_architecture':architecture,
                    'architecture_label':architecture, 'selection_method':'manual',
                    'rationale':'S2 browser acceptance', 'tradeoffs':[],
                    'ecs_library':'miniplex' if architecture == 'ecs' else None}, 1)
                card = repository.open_card_worktree(project.project_id, 'card_test', 'S2')
                worktree = Path(card['worktree_path'])
                (worktree / 'node_modules').symlink_to(Path(os.environ['SCENEOPS_S2_GAME_DEPENDENCIES']).resolve(), target_is_directory=True)
                provider = SimpleNamespace(database_path=root / 'state.sqlite3',
                    settings=lambda:SimpleNamespace(provider='fixture', model='fixture'))
                service = AgentTaskService(root / 'state.sqlite3', repository, root, provider=provider)
                try:
                    task = service.prepare(PrepareAgentTask(project_id=project.project_id,
                        card_id='card_test', goal='观察当前构建', task_profile='card-development',
                        allow_game_execution=True, allow_browser_observation=True))
                    source = (worktree / 'src/main.ts').read_text()
                    service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                        accept_unknown_cost=True), actions=[
                        fixture.action('write', 'code.file.write', path='src/main.ts', expected_content=source,
                            content=source+'\n// S2 isolated acceptance\n'),
                        fixture.action('check', 'code.project.check'),
                        fixture.action('build', 'code.project.build'),
                        fixture.action('preview', 'code.preview.start'),
                        fixture.action('finish', 'agent.finish', summary='current build ready')])
                    await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())), timeout=60)
                    completed = service.get(task.id)
                    self.assertEqual(completed.status, 'review_required', completed.model_dump())
                    app = FastAPI()
                    app.include_router(create_agent_task_router(service))
                    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                        response = await client.post(f'/api/agent/tasks/{task.id}/game', json={'operation':'observe'})
                    self.assertEqual(response.status_code, 200)
                    observation = response.json()['observation']
                    self.assertEqual(observation['status'], 'succeeded', observation)
                    self.assertTrue(observation['observation']['screenshot_collected'])
                    self.assertEqual(observation['observation']['diagnostics']['canvas_count'], 1)
                    self.assertEqual(observation['observation']['page_errors'], [])
                    self.assertEqual(observation['task_id'], task.id)
                    print(architecture, observation['id'], observation['build_run_id'], observation['preview_run_id'],
                          observation['observation']['diagnostics'], flush=True)
                finally:
                    await service.close()


def load_tests(loader, tests, pattern):
    # Only S2-specific checks; inherited helpers do not broaden this test suite.
    return unittest.TestSuite([*(BrowserObservationTests(name) for name in
        loader.getTestCaseNames(BrowserObservationTests) if name.startswith('test_browser_')),
        loader.loadTestsFromTestCase(ArchitectureBrowserTests)])
