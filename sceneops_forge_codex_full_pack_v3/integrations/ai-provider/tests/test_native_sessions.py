"""Deterministic native production contract; no account or model request."""
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
import tempfile
from sceneops_ai_provider import codex_cli
from sceneops_codebuddy.agent import arguments


class NativeSessionTests(IsolatedAsyncioTestCase):
    def test_production_arguments_and_legacy_isolation(self):
        config = {'mcpServers': {'sceneops': {'command': '/usr/bin/python3', 'args': ['bridge.py'], 'env': {'SESSION_TOKEN': 'fixture'}}}}
        native = codex_cli._arguments(full_access=True, authorized_scope='fixture', native_production=True,
            session_id='session-123', permission_mode='scoped', mcp_config=config)
        self.assertEqual(native[-3:], ['resume', 'session-123', '-'])
        self.assertNotIn('--ephemeral', native)
        self.assertNotIn('--ignore-rules', native)
        self.assertIn('workspace-write', native)
        self.assertIn('orchestrator.skills.enabled=true', native)
        self.assertFalse(any(value.startswith('features.') and value.endswith('=false') for value in native))
        self.assertIn('features.multi_agent=true', native)
        self.assertIn('features.workspace_dependencies=true', native)
        self.assertIn('mcp_servers.sceneops.command="/usr/bin/python3"', native)
        self.assertIn('--ephemeral', codex_cli._arguments())
        buddy = arguments('cli-default', 'low', native_production=True, session_id='session-123',
            permission_mode='scoped', mcp_config=config)
        self.assertEqual(buddy[-2:], ['--resume', 'session-123'])
        self.assertIn('acceptEdits', buddy)
        self.assertNotIn('--no-session-persistence', buddy)
        self.assertEqual(buddy[buddy.index('--tools') + 1], 'default')
        self.assertIn('--no-session-persistence', arguments('cli-default', 'low'))

    async def test_codex_immediate_id_and_mismatch_failure(self):
        observed = []
        async def receive(event):
            observed.append(event)
        async def run(executable, args, directory, prompt, timeout, **kwargs):
            if args == ['--version']:
                return b'codex-cli 0.153.4', b'', 0
            await kwargs['on_event']({'type': 'session_started', 'session_id': 'session-123'})
            self.assertEqual(observed[0]['session_id'], 'session-123')
            return b'{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n{"type":"turn.completed"}', b'', 0
        with tempfile.TemporaryDirectory() as directory, patch.object(codex_cli, '_run', run), patch.object(codex_cli, 'resolve_cli_executable', return_value='fixture'):
            result = await codex_cli.invoke_agent('new request only', workspace_root=Path(directory).resolve(),
                authorized_scope='fixture', native_production=True, session_id='session-123', on_event=receive)
            self.assertEqual(result['session_id'], 'session-123')
            self.assertEqual(result['cli_version'], 'codex-cli 0.153.4')
            self.assertEqual(observed[0]['cli_version'], 'codex-cli 0.153.4')
            with self.assertRaises(codex_cli.CodexFailure) as error:
                await codex_cli.invoke_agent('fixture', workspace_root=Path(directory).resolve(),
                    authorized_scope='fixture', native_production=True, session_id='other')
            self.assertEqual(error.exception.code, 'CODEX_SESSION_MISMATCH')
