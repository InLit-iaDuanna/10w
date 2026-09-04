"""Maintained adapter cases; not run in the lab integration task."""
import unittest
from unittest.mock import AsyncMock, patch
from conversation_home.codebuddy import complete, CodeBuddyFailure
from conversation_home.schemas import ChatRequest

class CodeBuddyTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_only_arguments_and_success(self):
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b'{"result":"hello","is_error":false}', b'')
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/host/codebuddy'), patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process) as spawn:
            response = await complete(ChatRequest(model='hy3', prompt='hello'))
        args = spawn.call_args.args
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertNotIn('--dangerously-skip-permissions', args)
        self.assertEqual(response.mode, 'live')
        self.assertEqual(response.text, 'hello')

    async def test_missing_cli_is_blocked(self):
        with patch('sceneops_codebuddy.provider.shutil.which', return_value=None):
            with self.assertRaises(CodeBuddyFailure) as failure:
                await complete(ChatRequest(model='hy3', prompt='hello'))
        self.assertEqual(failure.exception.code, 'CLI_UNAVAILABLE')
