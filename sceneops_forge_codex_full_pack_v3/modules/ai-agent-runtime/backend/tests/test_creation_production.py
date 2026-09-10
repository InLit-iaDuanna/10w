"""Reviewed native handoff and durable session continuation on real domain services."""
import asyncio
import base64
from unittest.mock import AsyncMock, patch
from pathlib import Path
from test_project_native_authorization import ProjectNativeAuthorizationSmoke
from sceneops_ai_agents import AuthorizeAgentTask
from sceneops_ai_agents.task_models import ContinueProjectDemoRequest
from sceneops_ai_agents.creation_brief import read_brief, save_brief, SaveCreationBrief
from sceneops_ai_agents.native_inputs import save_native_input, NativeInputUpload
from sceneops_harness import HarnessError


class CreationProductionTests(ProjectNativeAuthorizationSmoke):
    async def test_openai_compatible_first_version_uses_native_codex_harness(self):
        self.provider.settings = lambda: type('Settings', (), {
            'provider':'openai-compatible', 'model':'fixture-compatible',
            'base_url':'https://fixture.invalid/v1', 'agent_timeout_minutes':None})()
        task = self.service.prepare(self.request().model_copy(update={'native_production': True}))
        self.assertTrue(task.observations['native_production'])
        self.assertEqual(task.provider_id, 'openai-compatible')
        self.assertEqual(task.observations['native_api_route']['wire_api'], 'responses')

    async def test_reviewed_native_round_and_exact_session_continuation(self):
        attached = save_native_input(self.service, self.project.project_id, NativeInputUpload(
            name='reference.png', media_type='image/png',
            content_base64=base64.b64encode(b'fixture-image').decode()))
        request = self.request().model_copy(update={'native_production': True,
            'permission_mode': 'scoped', 'input_paths': [attached.path]})
        task = self.service.prepare(request)
        with self.assertRaises(HarnessError):
            self.service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                accept_unknown_cost=True))
        original = read_brief(self.service, task.id)
        revised = save_brief(self.service, task.id, SaveCreationBrief(expected_version=original.version,
            content=original.content + '\n灯塔岛：移动并点灯。',
            selected_skills=['sceneops-threejs-ui']))
        with self.assertRaises(HarnessError):
            save_brief(self.service, task.id, SaveCreationBrief(expected_version=original.version, content='stale'))
        sessions, models = [], []
        async def execute(prompt, **kwargs):
            sessions.append(kwargs.get('session_id'))
            models.append(kwargs['model'])
            self.assertTrue(kwargs['native_production'])
            self.assertIn('canvas.getBoundingClientRect()', kwargs['execution_instructions'])
            self.assertIn('DPR 1 与 DPR 2', kwargs['execution_instructions'])
            self.assertEqual(kwargs['permission_mode'], 'scoped')
            self.assertIn('sceneops', kwargs['mcp_config']['mcpServers'])
            await kwargs['on_event']({'type': 'session_started', 'session_id': 'fixture-session'})
            root = kwargs['workspace_root']
            self.assertTrue((root / '.codebuddy/skills/sceneops-threejs-ui/SKILL.md').is_file())
            self.assertFalse((root / '.codebuddy/skills/sceneops-threejs-gameplay').exists())
            if len(sessions) == 1:
                self.assertIn('原生计划能力', prompt)
                self.assertEqual([path.name for path in kwargs['reference_images']], ['in_' + attached.id.removeprefix('in_') + '_reference.png'])
                self.assertIn(attached.path, prompt)
            else:
                self.assertEqual(kwargs['reference_images'], ())
            (root / 'src/native.ts').write_text('export const speed = 3;')
            return {'result': 'fixture', 'session_id': 'fixture-session', 'cli_version': 'fixture'}
        self.provider.execute_task = AsyncMock(side_effect=execute)
        self.service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
            accept_unknown_cost=True, creation_brief_version=revised.version))
        await asyncio.gather(*list(self.service.jobs.values()))
        finished = self.service.get(task.id)
        self.assertEqual(finished.status, 'review_required', finished.reason)
        self.assertEqual(finished.observations['native_session_id'], 'fixture-session')
        with self.service.records.manual_edit(finished):
            with self.assertRaises(HarnessError):
                with self.service.records.manual_edit(finished):
                    self.fail('Two manual saves acquired the same project')
            with self.service.records.connect() as connection:
                with self.assertRaises(HarnessError):
                    self.service.records._claim_project(connection, finished)
        self.provider.settings = lambda: type('Settings', (), {
            'provider':'codebuddycli', 'model':'fixture-next', 'reasoning_effort':'low'})()
        next_task = self.service.continue_project_demo(task.id, ContinueProjectDemoRequest(
            request_id='followup-fixture', goal='移动太慢，请加快'))
        await asyncio.gather(*list(self.service.jobs.values()))
        self.assertEqual(self.service.get(next_task.id).status, 'review_required', self.service.get(next_task.id).reason)
        self.assertIsNotNone(self.service.game_status(next_task.id).current_playable_candidate.scene_version)
        self.assertEqual(sessions, [None, 'fixture-session'])
        self.assertEqual(models, ['fixture', 'fixture-next'])
        rebuilt = self.service.update_project_demo(next_task.id)
        await asyncio.gather(*list(self.service.jobs.values()))
        self.assertEqual(self.service.get(rebuilt.id).status, 'review_required', self.service.get(rebuilt.id).reason)
        self.assertEqual(len(sessions), 2, 'Updating workbench content must not call a model')
        self.assertEqual(self.provider.generate.await_count, 0)

    async def test_cancelled_round_preserves_session_and_can_resume_exactly(self):
        task = self.service.prepare(self.request().model_copy(update={'native_production': True}))
        started = asyncio.Event()
        sessions = []
        async def execute(prompt, **kwargs):
            sessions.append(kwargs['session_id'])
            await kwargs['on_event']({'type': 'session_started', 'session_id': 'cancel-session'})
            if len(sessions) == 1:
                (kwargs['workspace_root'] / 'src/partial.ts').write_text('export const partial = true;')
                started.set()
                await asyncio.Event().wait()
            return {'result': 'resumed', 'session_id': 'cancel-session', 'cli_version': 'fixture'}
        self.provider.execute_task = AsyncMock(side_effect=execute)
        self.service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
            accept_unknown_cost=True, creation_brief_version=1))
        await asyncio.wait_for(started.wait(), 5)
        self.service.cancel(task.id)
        await asyncio.gather(*list(self.service.jobs.values()), return_exceptions=True)
        cancelled = self.service.get(task.id)
        self.assertEqual(cancelled.status, 'cancelled', cancelled.reason)
        self.assertIsNone(cancelled.owner_pid)
        self.assertEqual(cancelled.observations['native_session_id'], 'cancel-session')
        resumed = self.service.continue_project_demo(task.id, ContinueProjectDemoRequest(
            request_id='resume-cancelled', goal='保留已有文件，继续完成'))
        await asyncio.gather(*list(self.service.jobs.values()))
        self.assertEqual(self.service.get(resumed.id).status, 'review_required', self.service.get(resumed.id).reason)
        self.assertEqual(sessions, [None, 'cancel-session'])
