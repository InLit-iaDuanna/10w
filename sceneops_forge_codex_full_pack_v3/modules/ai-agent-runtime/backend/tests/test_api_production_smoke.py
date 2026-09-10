"""API decisions use the existing authorized file tools; no external model or build."""
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from sceneops_ai_agents import AgentRuntime, AuthorizeAgentTask
from sceneops_ai_provider import ProviderService
import test_project_native_authorization as fixture


class APIProductionSmoke(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.ProjectNativeAuthorizationSmoke.asyncSetUp
    asyncTearDown = fixture.ProjectNativeAuthorizationSmoke.asyncTearDown
    request = fixture.ProjectNativeAuthorizationSmoke.request

    async def test_api_decision_writes_and_reads_registered_source(self):
        provider = ProviderService(self.database)
        provider.update_settings(provider='openai-compatible', model='fixture-api-model',
            base_url='https://fixture.invalid/v1', api_key='fixture-only', streaming=False)
        self.service.provider = provider
        self.service.agents = AgentRuntime(provider)
        self.service.agents.image_resolver = self.service.resolve_model_image
        path = 'src/game/ApiSmoke.ts'
        source = 'export const waveReward = 10;\n'
        actions = [
            ('write', 'code.file.write', {'path': path, 'expected_content': None, 'content': source}),
            ('read', 'code.file.read', {'path': path}),
            ('stop', 'agent.report_blocked', {'reason': 'Smoke ends before game execution.'}),
        ]
        requests = []
        def response(request):
            data = json.loads(request.content)
            requests.append(data)
            action_id, capability_id, inputs = actions[len(requests) - 1]
            value = {'action_id': action_id, 'capability_id': capability_id,
                     'rationale': 'API tool smoke', 'inputs': inputs}
            self.assertEqual(str(request.url), 'https://fixture.invalid/v1/chat/completions')
            self.assertEqual(data['model'], 'fixture-api-model')
            self.assertIn('response_format', data)
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(value)}}],
                                           'usage': {'total_tokens': 10}})
        client = httpx.AsyncClient
        with patch('httpx.AsyncClient', side_effect=lambda **kwargs:
                   client(**kwargs, transport=httpx.MockTransport(response))):
            task = self.service.prepare(self.request('typed-tools'))
            self.assertEqual(task.authorization_card.max_model_calls, 28)
            self.assertNotIn('agent.task.execute', task.authorization_card.capability_ids)
            self.assertEqual(requests, [])
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
            await asyncio.wait_for(asyncio.gather(*list(self.service.jobs.values())), 10)
        final = self.service.get(task.id)
        self.assertEqual(final.status, 'needs_approval', final.reason)
        self.assertIn('BLOCKED_CAPABILITY_GAP', final.reason)
        self.assertEqual(len(requests), 3)
        write = next(item for item in final.actions if item.action.action_id == 'write')
        self.assertEqual(write.state, 'succeeded', write.reason)
        self.assertEqual((Path(task.authorization_card.workspace_root) / path).read_text(), source)
        read = next(item for item in final.actions if item.action.action_id == 'read')
        self.assertEqual(read.result['evidence']['content'], source)
        self.assertEqual(final.model_calls_used, 3)
        native = self.service.prepare(self.request())
        self.assertIsNone(native.authorization_card.max_model_calls)
        self.assertIsNone(native.authorization_card.max_duration_seconds)
        self.assertEqual(native.observations['native_api_route']['base_url'], 'https://fixture.invalid/v1')
        with patch.object(self.service, '_run', new=AsyncMock()):
            self.service.authorize(native.id, AuthorizeAgentTask(
                authorization_card_id=native.authorization_card.id,
                accept_unknown_cost=True, accept_full_access=True))
            await asyncio.gather(*list(self.service.jobs.values()))
        continued = self.service.get(native.id)
        self.assertIsNone(continued.grant.expires_at)
        self.assertEqual(continued.observations['project_claim_continuation']['from_task_id'], task.id)
        old = self.service.get(task.id)
        self.assertEqual(old.status, 'needs_approval')
        self.assertEqual(old.model_calls_used, 3)
        self.assertTrue(old.grant.revoked)
        self.assertEqual((Path(task.authorization_card.workspace_root) / path).read_text(), source)
