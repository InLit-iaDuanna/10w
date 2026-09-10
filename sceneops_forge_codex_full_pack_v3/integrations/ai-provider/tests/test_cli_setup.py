"""Deterministic setup fixtures: no real install, login, or model calls."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from sceneops_ai_provider import cli_setup


class CLISetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_install_smoke(self):
        service = cli_setup.CLISetup()
        installed = set()
        async def install(arguments, timeout):
            self.assertEqual(timeout, 300)
            self.assertIn('@openai/codex@0.144.1', arguments)
            installed.add('codex')
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli_setup.platform, 'system', return_value='Darwin'), \
                patch.object(cli_setup.shutil, 'which', return_value='/fixture/npm'), \
                patch.object(cli_setup, 'cli_install_prefix', return_value=Path(directory)), \
                patch.object(cli_setup, 'resolve_cli_executable', side_effect=lambda name: '/fixture/codex' if name in installed else None), \
                patch.object(cli_setup, 'codex_version', AsyncMock(return_value='0.144.1')), \
                patch.object(cli_setup, 'run_command', side_effect=install):
            self.assertEqual((await service.start_install(['codexcli']))['operation']['state'], 'installing')
            await service.task
            self.assertEqual((await service.status())['operation']['state'], 'succeeded')
            self.assertTrue((await service.status())['tools'][0]['installed'])

    async def test_install_failure_does_not_expose_output(self):
        service = cli_setup.CLISetup()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli_setup, 'cli_install_prefix', return_value=Path(directory)), \
                patch.object(cli_setup, 'resolve_cli_executable', return_value=None), \
                patch.object(cli_setup, 'run_command', AsyncMock(side_effect=OSError('secret-token'))):
            await service._install(['codexcli'], '/fixture/npm')
        self.assertEqual(service.operation['state'], 'failed')
        self.assertNotIn('secret-token', service.operation['message'])

    async def test_concurrent_install_rejected(self):
        service = cli_setup.CLISetup()
        service.task = asyncio.create_task(asyncio.sleep(0))
        with self.assertRaises(cli_setup.SetupFailure):
            await service.start_install(['codexcli'])
        await service.task

    async def test_login_only_fixed_command(self):
        service = cli_setup.CLISetup()
        runner = AsyncMock()
        with patch.object(cli_setup.platform, 'system', return_value='Darwin'), \
                patch.object(cli_setup, 'resolve_cli_executable', return_value='/fixture/bin/codex'), \
                patch.object(cli_setup, 'run_command', runner):
            await service.login('codexcli')
        self.assertEqual(runner.call_args.args[0][:2], ['/usr/bin/osascript', '-e'])
        self.assertIn('/fixture/bin/codex login', runner.call_args.args[0][3])

    async def test_incompatible_repair_smoke(self):
        service = cli_setup.CLISetup()
        installed = False
        async def install(arguments, timeout):
            nonlocal installed
            self.assertIn('@openai/codex@0.144.1', arguments)
            self.assertIn('--prefix', arguments)
            installed = True
        async def version(executable):
            return '0.144.1' if installed else '0.140.0'
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli_setup.platform, 'system', return_value='Darwin'), \
                patch.object(cli_setup.shutil, 'which', return_value='/fixture/npm'), \
                patch.object(cli_setup, 'cli_install_prefix', return_value=Path(directory)), \
                patch.object(cli_setup, 'resolve_cli_executable', side_effect=lambda name: '/fixture/codex' if name == 'codex' else None), \
                patch.object(cli_setup, 'codex_version', side_effect=version), \
                patch.object(cli_setup, 'run_command', side_effect=install):
            self.assertFalse((await service.status())['tools'][0]['compatible'])
            await service.start_install(['codexcli'])
            await service.task
            self.assertEqual(service.operation['state'], 'succeeded')
            self.assertTrue((await service.status())['tools'][0]['compatible'])

    async def test_chinese_login_path_is_separate_argument(self):
        runner = AsyncMock()
        with patch.object(cli_setup.platform, 'system', return_value='Darwin'), \
                patch.object(cli_setup, 'resolve_cli_executable', return_value='/Users/用户 空间/bin/codex'), \
                patch.object(cli_setup, 'run_command', runner):
            await cli_setup.CLISetup().login('codexcli')
        arguments = runner.call_args.args[0]
        self.assertNotIn('用户', arguments[2])
        self.assertEqual(arguments[3], "'/Users/用户 空间/bin/codex' login")

    async def test_managed_executable_precedes_global(self):
        from sceneops_codebuddy import cli_paths
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'bin').mkdir()
            executable = prefix / 'bin' / 'codex'
            executable.write_text('fixture')
            executable.chmod(0o700)
            with patch.object(cli_paths, 'cli_install_prefix', return_value=prefix), \
                    patch.object(cli_paths.shutil, 'which', return_value='/global/codex'):
                self.assertEqual(cli_paths.resolve_cli_executable('codex'), str(executable))
