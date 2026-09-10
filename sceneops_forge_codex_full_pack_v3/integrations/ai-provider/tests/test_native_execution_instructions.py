"""Trusted runtime instructions reach native CLI control channels, never user input."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sceneops_ai_provider import ProviderService, ProviderFailure, codex_cli
from sceneops_codebuddy import invoke_agent as invoke_codebuddy


class NativeExecutionInstructionTests(unittest.IsolatedAsyncioTestCase):
    async def test_codebuddy_system_flag_preserves_base_and_separates_user_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            executable = root / 'fixture-cli'
            executable.write_text('#!' + sys.executable + '\n' +
                'import json, pathlib, sys\n' +
                'pathlib.Path("received.json").write_text(json.dumps({"args":sys.argv[1:],"stdin":sys.stdin.read()}))\n' +
                'print(json.dumps({"type":"result","subtype":"success","result":"fixture"}))\n')
            executable.chmod(0o700)
            with patch('sceneops_codebuddy.agent.shutil.which', return_value=str(executable)):
                await invoke_codebuddy('untrusted project goal', workspace_root=root,
                    authorized_scope='registered workspace only', system_prompt='trusted responsive camera policy')
            received = json.loads((root / 'received.json').read_text())
        args = received['args']
        instructions = args[args.index('--append-system-prompt') + 1]
        self.assertIn('trusted responsive camera policy', instructions)
        self.assertIn('不要输出凭据', instructions)
        self.assertNotIn('untrusted project goal', instructions)
        self.assertNotIn('trusted responsive camera policy', received['stdin'])
        self.assertIn('untrusted project goal', received['stdin'])
        self.assertIn('--strict-mcp-config', args)
        self.assertIn('{"disableAllHooks":true}', args)

    async def test_codex_developer_flag_preserves_scope_and_separates_user_input(self):
        transcript = b'{"type":"item.completed","item":{"type":"agent_message","text":"fixture"}}\n{"type":"turn.completed","usage":{}}\n'
        runner = AsyncMock(side_effect=[(codex_cli.SUPPORTED_VERSION, b'', 0), (transcript, b'', 0)])
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(codex_cli, 'resolve_cli_executable', return_value='/fixture/codex'), \
                patch.object(codex_cli, '_run', runner):
            await codex_cli.invoke_agent('untrusted project goal', workspace_root=Path(directory).resolve(),
                authorized_scope='registered workspace only', system_prompt='trusted responsive camera policy')
        args = runner.call_args.args[1]
        instructions = next(value for value in args if value.startswith('developer_instructions='))
        self.assertIn('trusted responsive camera policy', instructions)
        self.assertIn('registered workspace only', instructions)
        self.assertIn(codex_cli.AGENT_PROMPT, json.loads(instructions.split('=', 1)[1]))
        self.assertNotIn('untrusted project goal', instructions)
        self.assertEqual(runner.call_args.args[3], b'untrusted project goal')
        self.assertIn('features.plugins=false', args)
        self.assertIn('orchestrator.mcp.enabled=false', args)

    async def test_provider_forwards_only_explicit_trusted_instructions_and_retains_route_check(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ProviderService(Path(directory) / 'state.sqlite3')
            for provider, target in [('codebuddycli', 'sceneops_codebuddy.invoke_agent'),
                                     ('codexcli', 'sceneops_ai_provider.codex_cli.invoke_agent')]:
                with patch.object(service, 'settings', return_value=SimpleNamespace(
                        provider=provider, model='cli-default', reasoning_effort='low')), \
                        patch(target, new=AsyncMock(return_value={'result': 'fixture'})) as invoke:
                    await service.execute_task('user goal', workspace_root=Path(directory), model='cli-default',
                        authorized_scope='registered scope', timeout=10, expected_provider=provider,
                        execution_instructions='trusted camera policy')
                    self.assertEqual(invoke.call_args.kwargs['system_prompt'], 'trusted camera policy')
                    self.assertEqual(invoke.call_args.args, ('user goal',))
                    with self.assertRaises(ProviderFailure):
                        await service.execute_task('user goal', workspace_root=Path(directory), model='changed-model',
                            authorized_scope='registered scope', timeout=10, expected_provider=provider,
                            execution_instructions='trusted camera policy')
                    self.assertEqual(invoke.await_count, 1)
