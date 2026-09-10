"""Focused completion contract checks, without real CLI or network requests."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from sceneops_ai_provider import ProviderService


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_chat_uses_text_not_unsolicited_structured_output(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'workspace.sqlite3')
            service.update_settings(reasoning_effort='high')
            with patch('sceneops_ai_provider.service.cli_invoke_json', new=AsyncMock(return_value={
                'result': 'plain reply', 'structured_output': {'unexpected': True}})) as invoke:
                result = await service.generate('hello')
            self.assertEqual(result.text, 'plain reply')
            self.assertIsNone(result.structured)
            self.assertEqual(invoke.await_args.kwargs['effort'], 'high')

    async def test_transcript_through_cli_validation_to_provider(self):
        schema = {'type': 'object', 'properties': {'status': {'type': 'string'}},
                  'required': ['status'], 'additionalProperties': False}
        process = Mock()
        process.returncode = 0
        process.stdin = Mock(drain=AsyncMock())
        process.stdout, process.stderr = asyncio.StreamReader(), asyncio.StreamReader()
        process.wait = AsyncMock(return_value=0)
        process.stdout.feed_data(json.dumps(
            {'type': 'result', 'subtype': 'success', 'result': '{"status":"ok"}'}
        ).encode() + b'\n')
        process.stdout.feed_eof()
        process.stderr.feed_eof()
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'workspace.sqlite3')
            with patch('sceneops_codebuddy.provider.resolve_cli_executable', return_value='/fixture/codebuddy'), \
                 patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process):
                value = await service.structured('reply with status', schema, model='glm-5.3-flash')
            self.assertEqual(value, {'status': 'ok'})
            self.assertIn(json.dumps(schema, ensure_ascii=False).encode(), process.stdin.write.call_args.args[0])

    async def test_structured_request_can_extend_cli_timeout(self):
        schema = {'type': 'object', 'properties': {}, 'additionalProperties': False}
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'workspace.sqlite3')
            with patch('sceneops_ai_provider.service.cli_invoke_json', new=AsyncMock(return_value={
                'result': '{}', 'structured_output': {}})) as invoke:
                value = await service.structured('build a model', schema, timeout=600)
            self.assertEqual(value, {})
            self.assertEqual(invoke.await_args.kwargs['timeout'], 600)


if __name__ == '__main__':
    unittest.main()
