"""S3 bounded inputs: deterministic authorization checks and opt-in real Chromium."""
import asyncio
import json
from datetime import timedelta
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sceneops_ai_agents import AgentTaskService, AuthorizeAgentTask, PrepareAgentTask, create_agent_task_router
from sceneops_ai_agents import create_production_router
from sceneops_ai_agents.task_models import BrowserInteractionRequest, GameOperationRequest, now
from sceneops_ai_agents.task_tools import INPUT_MODELS
from sceneops_harness import HarnessError
from sceneops_project_workspace import SqliteWorkspaceRepository
import test_game_project_runtime_smoke as fixture
from test_browser_observation import BrowserObservationTests

SEQUENCE = {'check':'movement-collection', 'state_id':'start', 'steps':[
    {'keys':['ArrowDown'],'duration_ms':400}, {'keys':[],'duration_ms':160},
    {'keys':['ArrowUp'],'duration_ms':400}, {'keys':['ArrowDown'],'duration_ms':400}]}


class InteractionAuthorizationTests(BrowserObservationTests):
    async def ready_interaction(self):
        task = self.service.prepare(PrepareAgentTask(project_id='prj_fixture0001',card_id='card_one',
            task_profile='card-development',goal='有限输入检查',allow_game_execution=True,
            allow_dependency_install=True,allow_browser_observation=True,allow_browser_interaction=True))
        await self.authorize_empty(task)
        await self.service.game_operation(task.id,GameOperationRequest(operation='build_test'))
        return self.service.get(task.id)

    async def test_interaction_old_observation_is_not_interaction(self):
        task = await self.ready()
        self.assertNotIn('code.browser.interact', task.authorization_card.capability_ids)
        with self.assertRaises(HarnessError) as denied:
            await self.service.observe_game(task.id, interaction=BrowserInteractionRequest(**SEQUENCE))
        self.assertEqual(denied.exception.code, 'BROWSER_NOT_AUTHORIZED')
        with self.assertRaises(HarnessError):
            await self.service.game_operation(task.id, GameOperationRequest(operation='build_test'))

    async def test_interaction_contract_bounds(self):
        self.assertIs(INPUT_MODELS['code.browser.interact'], BrowserInteractionRequest)
        for extra in ({'url':'http://localhost:1'}, {'script':'alert(1)'}, {'output_path':'/tmp/x'}):
            with self.assertRaises(ValidationError): BrowserInteractionRequest(**SEQUENCE, **extra)
        for steps in ([{'keys':['Escape'],'duration_ms':100}], [{'keys':[],'duration_ms':9000}]):
            with self.assertRaises(ValidationError): BrowserInteractionRequest(check='input-readback', steps=steps)

    async def test_interaction_expired_and_cross_project(self):
        task = await self.ready_interaction()
        self.service.records.update(task.id,lambda current:setattr(current.browser_interaction_authorization,'project_id','other-project'),'fixture.wrong-project')
        with self.assertRaises(HarnessError) as wrong: self.service.browser_task(task.id,interaction=True)
        self.assertEqual(wrong.exception.code,'BROWSER_NOT_AUTHORIZED')
        self.service.records.update(task.id,lambda current:setattr(current.browser_interaction_authorization,'expires_at',now()-timedelta(seconds=1)),'fixture.expired')
        with self.assertRaises(HarnessError) as expired: self.service.browser_task(task.id,interaction=True)
        self.assertEqual(expired.exception.code,'BROWSER_AUTHORIZATION_EXPIRED')

    async def test_interaction_timeout_and_cancel_private_preview_cleanup(self):
        task = await self.ready_interaction()
        preview = self.service.game_status(task.id).preview
        async def timeout(*args,**kwargs): return {'status':'failed','failure_code':'BROWSER_TIMEOUT'}
        with patch('sceneops_ai_agents.browser_observation.capture',timeout):
            result = await self.service.observe_game(task.id,interaction=BrowserInteractionRequest(**SEQUENCE))
        self.assertEqual(result['run']['failure_code'],'BROWSER_TIMEOUT')
        started = asyncio.Event()
        async def pending(*args,**kwargs):
            started.set()
            await asyncio.Future()
        with patch('sceneops_ai_agents.browser_observation.capture',pending):
            job = asyncio.create_task(self.service.observe_game(task.id,interaction=BrowserInteractionRequest(**SEQUENCE)))
            await asyncio.wait_for(started.wait(),5)
            self.service.cancel_browser_observation(task.id)
            result = await job
        self.assertEqual(result['run']['failure_code'],'BROWSER_CANCELLED')
        self.assertEqual(self.service.game_status(task.id).preview.id,preview.id)
        self.assertEqual(len(self.service.game.previews),1)
        own_run = self.service.game_status(task.id).interaction
        other_run = own_run.model_copy(update={'id':'game_run_other_task','task_id':'other_task'})
        self.service.game._save(other_run)
        self.assertEqual(self.service.game_status(task.id).interaction.id,own_run.id)

    @unittest.skipUnless(os.environ.get('SCENEOPS_S3_GAME_DEPENDENCIES'),'explicit real browser acceptance')
    async def test_interaction_live_missing_hooks_and_cancel(self):
        task = await self.ready_interaction()
        result = await self.service.observe_game(task.id,interaction=BrowserInteractionRequest(**SEQUENCE))
        self.assertEqual(result['run']['failure_code'],'BROWSER_TEST_HOOKS_UNAVAILABLE')
        job = asyncio.create_task(self.service.observe_game(task.id,interaction=BrowserInteractionRequest(**SEQUENCE)))
        async with asyncio.timeout(5):
            while not self.service.game.processes: await asyncio.sleep(.01)
        process = next(iter(self.service.game.processes.values()))
        self.service.cancel_browser_observation(task.id)
        result = await job
        self.assertEqual(result['run']['failure_code'],'BROWSER_CANCELLED')
        self.assertIsNotNone(process.returncode)
        self.assertEqual(len(self.service.game.previews),1)


class ArchitectureInteractionTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.environ.get('SCENEOPS_S3_GAME_DEPENDENCIES'), 'existing dependencies and explicit live acceptance required')
    async def test_real_keyboard_both_architectures(self):
        for architecture in ('object-component', 'ecs'):
            if os.environ.get('SCENEOPS_S3_ARCHITECTURE') not in (None,architecture):
                continue
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory(prefix='sceneops-s3-') as directory:
                root = Path(directory).resolve()
                repository = SqliteWorkspaceRepository(root / 'state.sqlite3')
                project = repository.create_folder_project(root, 'game')
                repository.commit_design_version(project.project_id, 1, {'version':1})
                repository.initialize_game_project(project.project_id, {
                    'target_platform':'web','engine':'threejs','code_architecture':architecture,
                    'architecture_label':architecture,'selection_method':'manual','rationale':'S3 isolated acceptance',
                    'tradeoffs':[],'ecs_library':'miniplex' if architecture == 'ecs' else None}, 1)
                card = repository.open_card_worktree(project.project_id, 'card_test', 'S3')
                worktree = Path(card['worktree_path'])
                (worktree / 'node_modules').symlink_to(Path(os.environ['SCENEOPS_S3_GAME_DEPENDENCIES']).resolve(), target_is_directory=True)
                provider = SimpleNamespace(database_path=root / 'state.sqlite3',settings=lambda:SimpleNamespace(provider='fixture',model='fixture'))
                service = AgentTaskService(root / 'state.sqlite3', repository, root, provider=provider)
                try:
                    task = service.prepare(PrepareAgentTask(project_id=project.project_id,card_id='card_test',
                        goal='受控移动与收集检查',task_profile='card-development',allow_game_execution=True,
                        allow_browser_observation=True,allow_browser_interaction=True))
                    source = (worktree / 'src/main.ts').read_text()
                    service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                        accept_unknown_cost=True), actions=[
                        fixture.action('write','code.file.write',path='src/main.ts',expected_content=source,content=source+'\n// S3 acceptance\n'),
                        fixture.action('check','code.project.check'), fixture.action('build','code.project.build'),
                        fixture.action('test-build','code.project.build_test'), fixture.action('preview','code.preview.start'),
                        fixture.action('inputs','code.browser.interact',**SEQUENCE),
                        fixture.action('finish','agent.finish',summary='bounded input evidence recorded')])
                    await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())),timeout=110)
                    completed = service.get(task.id)
                    self.assertEqual(completed.status,'review_required',service.game_status(task.id).model_dump())
                    first = service.game_status(task.id).interaction
                    self.assertEqual(first.status,'succeeded',first.model_dump())
                    preview = service.game_status(task.id).preview
                    app = FastAPI(); app.include_router(create_agent_task_router(service))
                    app.include_router(create_production_router(service))
                    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                        response = await client.post(f'/api/agent/tasks/{task.id}/game/interaction',json=SEQUENCE)
                        self.assertEqual(response.status_code,200,response.text)
                        second = response.json()['interaction']
                        self.assertEqual(second['status'],'succeeded',second)
                        for field in ('initial_state','input_trace','final_state'):
                            self.assertEqual(first.observation[field],second['observation'][field],field)
                        delivery = await client.post(f'/api/agent/tasks/{task.id}/game/interaction',json={
                            'check':'current-input','steps':SEQUENCE['steps'][:2]})
                        ordinary = delivery.json()['interaction']
                        self.assertEqual(ordinary['status'],'succeeded',ordinary)
                        self.assertEqual(ordinary['build_kind'],'delivery')
                        unknown = await client.post(f'/api/agent/tasks/{task.id}/game/interaction',json={**SEQUENCE,'state_id':'missing'})
                        self.assertEqual(unknown.json()['interaction']['failure_code'],'BROWSER_TEST_STATE_UNKNOWN')
                    if os.environ.get('SCENEOPS_S3_UI') == '1':
                        import socket
                        import uvicorn
                        sock = socket.socket(); sock.bind(('127.0.0.1',0)); sock.listen(128)
                        port = sock.getsockname()[1]
                        server = uvicorn.Server(uvicorn.Config(app,log_level='error'))
                        server_job = asyncio.create_task(server.serve(sockets=[sock]))
                        try:
                            while not server.started: await asyncio.sleep(.01)
                            driver = Path(__file__).with_name('browser_interaction_ui.mjs')
                            evidence_dir = Path(os.environ.get('SCENEOPS_S3_EVIDENCE_DIRECTORY',str(root)))
                            evidence_dir.mkdir(parents=True,exist_ok=True)
                            (evidence_dir/f'{architecture}.json').write_text(json.dumps({
                                'first':first.model_dump(mode='json'),'repeat':second,'delivery':ordinary},indent=2))
                            ui = await asyncio.create_subprocess_exec('node',str(driver),str(port),str(evidence_dir/f'{architecture}-workbench.png'),
                                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                            try:
                                output,error = await asyncio.wait_for(ui.communicate(),timeout=60)
                            finally:
                                if ui.returncode is None:
                                    ui.terminate()
                                    await ui.wait()
                            self.assertEqual(ui.returncode,0,error.decode())
                            print(architecture,output.decode(),flush=True)
                        finally:
                            server.should_exit=True
                            await server_job
                    self.assertEqual(service.game_status(task.id).preview.id,preview.id)
                    self.assertEqual(len(service.game.previews),1)
                    self.assertFalse(first.observation['gameplay_verified'])
                    self.assertTrue(first.observation['screenshot_collected'])
                    self.assertEqual(first.observation['page_errors'],[])
                    print(architecture, first.id, first.observation['assertions'], flush=True)
                    service.revoke_browser_authorization(task.id,interaction=True)
                    with self.assertRaises(HarnessError): service.browser_task(task.id,interaction=True)
                    # Observation remains independently authorized after interaction revocation.
                    service.browser_task(task.id)
                finally:
                    await service.close()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([*(InteractionAuthorizationTests(name) for name in
        loader.getTestCaseNames(InteractionAuthorizationTests) if name.startswith('test_interaction_')),
        loader.loadTestsFromTestCase(ArchitectureInteractionTests)])
