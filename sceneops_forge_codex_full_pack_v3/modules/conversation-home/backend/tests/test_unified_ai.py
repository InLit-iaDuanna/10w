"""Contract/persistence/provider cases maintained, NOT RUN pending authorization."""
import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from conversation_home.ai_repository import AIRepository
from conversation_home.unified_router import ADVICE_PROMPTS
from sceneops_ai_provider import ProviderFailure, ProviderService
from sceneops_codebuddy import CodeBuddyFailure, complete


class UnifiedPersistenceTests(unittest.TestCase):
    def test_every_group_has_domain_advice(self):
        groups = ('project-planning', 'concept-assets', 'character-animation', 'world-logic',
            'ui-audio-vfx', 'render-ops', 'unity-build', 'version-review', 'ai-playtest', 'integration-ops')
        for group in groups:
            self.assertIn(group, ADVICE_PROMPTS)
        self.assertTrue(ADVICE_PROMPTS['concept-assets'].startswith(ADVICE_PROMPTS['concept-lab']))
        self.assertTrue(ADVICE_PROMPTS['project-planning'].startswith(ADVICE_PROMPTS['design-room']))

    def test_empty_scope_persistence_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'workspace.sqlite3'
            service = ProviderService(path)
            repository = AIRepository(path)
            self.assertEqual(repository.conversation(None).messages, [])
            self.assertEqual(service.settings().model, 'cli-default')
            repository.append_exchange('one', 'question', 'reply', 'hy3')
            service.update_settings(model='hy3')
            reopened = ProviderService(path)
            self.assertEqual(len(repository.conversation('one').messages), 2)
            self.assertEqual(repository.conversation('two').messages, [])
            self.assertEqual(repository.conversation(None).messages, [])
            self.assertEqual(reopened.settings().model, 'hy3')

    def test_existing_cli_model_is_migrated_losslessly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'workspace.sqlite3'
            with sqlite3.connect(path) as connection:
                connection.execute('CREATE TABLE conversation_ai_settings (id INTEGER PRIMARY KEY, model TEXT NOT NULL)')
                connection.execute('INSERT INTO conversation_ai_settings VALUES(1,?)', ('hy3-x',))
            service = ProviderService(path)
            self.assertEqual(service.settings().provider, 'codebuddycli')
            self.assertEqual(service.settings().model, 'hy3-x')

    def test_secret_is_write_only_and_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'workspace.sqlite3'
            secret = Path(directory) / 'provider.json'
            service = ProviderService(path, secret)
            settings = service.update_settings(provider='openai-compatible', model='custom-model',
                                               base_url='http://127.0.0.1:11434/v1', api_key='fixture-key')
            self.assertTrue(settings.api_key_configured)
            self.assertNotIn('fixture-key', repr(settings))
            self.assertEqual(secret.stat().st_mode & 0o777, 0o600)

    def test_external_plain_http_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'workspace.sqlite3')
            with self.assertRaises(ProviderFailure) as failure:
                service.update_settings(provider='openai-compatible', base_url='http://example.com/v1')
            self.assertEqual(failure.exception.code, 'BASE_URL_HTTPS_REQUIRED')


class UnifiedProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_model_omitted_and_tools_disabled(self):
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b'''[
            {"type":"message","role":"user","content":"fixture prompt"},
            {"type":"reasoning","content":"fixture reasoning"},
            {"type":"message","role":"assistant","content":"fixture text"},
            {"type":"result","subtype":"success","result":"fixture text","is_error":false}
        ]''', b'credential-like diagnostic')
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/fixture/codebuddy'), \
             patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process) as spawn:
            self.assertEqual(await complete('fixture prompt'), 'fixture text')
        args = spawn.call_args.args
        self.assertNotIn('--model', args)
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--strict-mcp-config', args)
        self.assertEqual(args[args.index('--mcp-config') + 1], '{"mcpServers":{}}')
        self.assertNotIn('--dangerously-skip-permissions', args)
        process.communicate.assert_awaited_once_with(b'fixture prompt')

    async def test_single_result_object_remains_compatible(self):
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (
            b'{"type":"result","subtype":"success","result":"legacy fixture","is_error":false}', b'')
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/fixture/codebuddy'), \
             patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process):
            self.assertEqual(await complete('fixture prompt'), 'legacy fixture')

    async def test_failed_cli_is_categorized_without_stderr(self):
        process = AsyncMock()
        process.returncode = 1
        process.communicate.return_value = (b'', b'401 secret credential')
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/fixture/codebuddy'), \
             patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process):
            with self.assertRaises(CodeBuddyFailure) as failure:
                await complete('fixture prompt', 'hy3')
        self.assertEqual(failure.exception.code, 'CLI_AUTH_REQUIRED')
        self.assertNotIn('secret', str(failure.exception))

    async def test_cancellation_stops_process(self):
        process = AsyncMock()
        process.pid = 123
        process.returncode = None
        process.communicate.side_effect = asyncio.CancelledError()
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/fixture/codebuddy'), \
             patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process), \
             patch('sceneops_codebuddy.provider.os.killpg') as kill:
            with self.assertRaises(asyncio.CancelledError):
                await complete('fixture prompt')
        kill.assert_called_once()
        process.wait.assert_awaited_once()

    async def test_openai_chat_completions_shape(self):
        response = MagicMock()
        response.is_redirect = False
        response.status_code = 200
        response.json.return_value = {'choices': [{'message': {'content': 'fixture reply'}}]}
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'workspace.sqlite3')
            service.update_settings(provider='openai-compatible', model='custom-model',
                                    base_url='https://provider.example/v1', api_key='fixture-key')
            with patch('sceneops_ai_provider.service.httpx.AsyncClient', return_value=client):
                self.assertEqual(await service.complete('hello'), 'fixture reply')
        call = client.post.await_args
        self.assertEqual(call.args[0], 'https://provider.example/v1/chat/completions')
        messages = call.kwargs['json']['messages']
        self.assertEqual([message['role'] for message in messages], ['system', 'user'])
        self.assertTrue(messages[0]['content'])
        self.assertEqual(messages[1], {'role': 'user', 'content': 'hello'})
        self.assertEqual(call.kwargs['headers']['Authorization'], 'Bearer fixture-key')
