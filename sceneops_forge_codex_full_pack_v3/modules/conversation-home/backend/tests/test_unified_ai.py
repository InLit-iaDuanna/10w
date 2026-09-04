"""Contract/persistence/provider cases maintained, NOT RUN pending authorization."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from conversation_home.ai_repository import AIRepository
from conversation_home.unified_schemas import AISettings
from conversation_home.unified_router import ADVICE_PROMPTS
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
            repository = AIRepository(path)
            self.assertEqual(repository.conversation(None).messages, [])
            self.assertEqual(repository.settings().model, 'cli-default')
            repository.append_exchange('one', 'question', 'reply', 'hy3')
            repository.save_settings(AISettings(model='hy3'))
            reopened = AIRepository(path)
            self.assertEqual(len(reopened.conversation('one').messages), 2)
            self.assertEqual(reopened.conversation('two').messages, [])
            self.assertEqual(reopened.conversation(None).messages, [])
            self.assertEqual(reopened.settings().model, 'hy3')

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(ValueError):
            AISettings(model='unknown')

class UnifiedProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_model_omitted_and_tools_disabled(self):
        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b'{"result":"fixture text","is_error":false}', b'credential-like diagnostic')
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

    async def test_failed_cli_does_not_expose_stderr(self):
        process = AsyncMock()
        process.returncode = 1
        process.communicate.return_value = (b'', b'secret credential')
        with patch('sceneops_codebuddy.provider.shutil.which', return_value='/fixture/codebuddy'), \
             patch('sceneops_codebuddy.provider.asyncio.create_subprocess_exec', return_value=process):
            with self.assertRaises(CodeBuddyFailure) as failure:
                await complete('fixture prompt', 'hy3')
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
