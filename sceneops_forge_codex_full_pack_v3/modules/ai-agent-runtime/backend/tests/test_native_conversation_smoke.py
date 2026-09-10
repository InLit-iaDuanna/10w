"""One native session with a fake CLI, a real temp branch and explicit consent."""
import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from test_demo_task_authorization import DemoTaskAuthorizationTests
from sceneops_ai_agents import AuthorizeAgentTask
from sceneops_harness import HarnessError


class NativeConversationSmoke(IsolatedAsyncioTestCase):
    setUp = DemoTaskAuthorizationTests.setUp
    request = DemoTaskAuthorizationTests.request

    async def test_native_prose_and_tools_preserve_grant_boundary(self):
        async def execute(goal, *, workspace_root, on_event, expected_provider, **kwargs):
            self.assertEqual(expected_provider, 'codebuddycli')
            self.assertIsNone(kwargs['timeout'])
            self.assertTrue(self.assets.exists())
            await on_event({'type': 'message_start'})
            await on_event({'type': 'text_delta', 'text': '我正在读取工程。'})
            self.assertEqual(self.service.get(task.id).observations['native_conversation'][-1]['text'], '我正在读取工程。')
            await on_event({'type': 'message_completed', 'text': '我正在读取工程。'})
            await on_event({'type': 'tool_start', 'name': 'Read'})
            await on_event({'type': 'tool_completed'})
            (workspace_root / 'native-fixture.txt').write_text('fixture')
            await on_event({'type': 'message_start'})
            await on_event({'type': 'text_delta', 'text': '修改完成，这是普通文字。'})
            return {'result': '修改完成，这是普通文字。', 'usage': None}
        self.provider.execute_task = AsyncMock(side_effect=execute)
        task = self.service.prepare(self.request(execution_mode='agent-full-access'))
        self.assertIsNone(task.authorization_card.max_duration_seconds)
        self.assertIn('不设运行时限', task.authorization_card.cost_notice)
        with self.assertRaises(HarnessError):
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        self.provider.execute_task.assert_not_called()
        self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True, accept_full_access=True))
        await asyncio.gather(*list(self.service.jobs.values()))
        result = self.service.get(task.id)
        self.assertEqual(result.status, 'review_required', result.reason)
        self.assertEqual(result.cli_invocations_used, 1)
        self.assertIsNone(result.grant.budget.max_duration_seconds)
        self.assertIsNone(result.grant.expires_at)
        self.assertEqual(result.model_calls_used, 0)
        self.assertEqual(result.observations['codex']['result']['result'], '修改完成，这是普通文字。')
        changes = result.observations['native_workspace_changes']
        self.assertTrue(changes['available'])
        self.assertIn('native-fixture.txt', [item['path'] for item in changes['files']])
        self.provider.generate.assert_not_called()
        self.assertTrue(result.grant.revoked)

    async def test_custom_agent_timeout_is_captured_by_new_authorization_card(self):
        self.provider.settings = lambda: SimpleNamespace(
            provider='codebuddycli', model='chosen-model', agent_timeout_minutes=90)
        task = self.service.prepare(self.request(execution_mode='agent-full-access'))
        self.assertEqual(task.authorization_card.max_duration_seconds, 5400)
        self.assertIn('最长 90 分钟', task.authorization_card.cost_notice)
