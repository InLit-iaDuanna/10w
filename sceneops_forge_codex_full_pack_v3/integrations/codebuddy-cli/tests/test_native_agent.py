"""Native transport fixtures: prose is not an action schema, partial output survives failure."""
import json
import unittest
import sys
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from sceneops_codebuddy import CodeBuddyFailure, invoke_agent
from sceneops_codebuddy.agent import activity


class NativeAgentTransportTests(IsolatedAsyncioTestCase):
    async def exchange(self, events, receive):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            executable = root / 'native-cli-fixture'
            executable.write_text('#!' + sys.executable + '\nimport sys\nsys.stdin.read()\n' +
                ''.join('print(' + repr(json.dumps(event)) + ', flush=True)\n' for event in events))
            executable.chmod(0o700)
            with patch('sceneops_codebuddy.agent.shutil.which', return_value=str(executable)):
                return await invoke_agent('fixture only', workspace_root=root,
                    authorized_scope='temporary fixture', on_event=receive)

    async def test_prose_and_partial_failure(self):
        received = []
        async def receive(event): received.append(event)
        message = {'type':'stream_event', 'event':{'type':'content_block_delta',
            'delta':{'type':'text_delta', 'text':'正在检查文件。'}}}
        result = await self.exchange([message, {'type':'result', 'subtype':'success',
            'result':'完成。这是普通文字。'}], receive)
        self.assertEqual(result['result'], '完成。这是普通文字。')
        self.assertEqual(received[-1]['text'], '正在检查文件。')
        with self.assertRaises(CodeBuddyFailure):
            await self.exchange([message], receive)
        self.assertEqual(received[-1]['text'], '正在检查文件。')

    def test_tool_arguments_are_projected_without_file_contents(self):
        event = activity({'type':'assistant', 'message':{'id':'message-1', 'content':[
            {'type':'tool_use', 'id':'read-1', 'name':'Read', 'input':{'file_path':'src/main.ts', 'offset':12}},
            {'type':'tool_use', 'id':'bash-1', 'name':'Bash', 'input':{'command':'pnpm check', 'description':'检查类型'}},
            {'type':'tool_use', 'id':'write-1', 'name':'Write', 'input':{'file_path':'src/main.ts', 'content':'private content'}}]}})
        self.assertEqual(event['tools'][0]['input'], {'file_path':'src/main.ts','offset':12})
        self.assertEqual(event['tools'][1]['input']['command'], 'pnpm check')
        self.assertNotIn('content', event['tools'][2]['input'])

    async def test_persistent_session_emits_id_before_result_and_rejects_missing_id(self):
        received = []
        async def receive(event): received.append(event)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            executable = root / 'session-fixture'
            prefix = ('#!' + sys.executable + '\nimport sys,json\n'
                'if "--version" in sys.argv: print("fixture 1.0");sys.exit(0)\n'
                'sys.stdin.read()\n')
            result = {'type': 'result', 'subtype': 'success', 'result': 'done'}
            executable.write_text(prefix + 'print(' + repr(json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 'session-123'})) + ',flush=True)\n' + 'print(' + repr(json.dumps(result)) + ',flush=True)\n')
            executable.chmod(0o700)
            with patch('sceneops_codebuddy.agent.resolve_cli_executable', return_value=str(executable)):
                value = await invoke_agent('new request', workspace_root=root, authorized_scope='fixture',
                    native_production=True, permission_mode='scoped', session_id='session-123', on_event=receive)
                self.assertEqual(received[0], {'type': 'session_started', 'session_id': 'session-123', 'cli_version': 'fixture 1.0'})
                self.assertEqual(value['session_id'], 'session-123')
                self.assertEqual(value['cli_version'], 'fixture 1.0')
                executable.write_text(prefix + 'print(' + repr(json.dumps(result)) + ',flush=True)\n')
                with self.assertRaises(CodeBuddyFailure) as error:
                    await invoke_agent('fixture', workspace_root=root, authorized_scope='fixture', native_production=True)
                self.assertEqual(error.exception.code, 'CLI_SESSION_MISSING')


class NativeDeferredToolTests(unittest.TestCase):
    def test_production_keeps_mcp_discovery_and_execution_tools(self):
        from sceneops_codebuddy.agent import arguments
        args = arguments('cli-default', 'medium', native_production=True, permission_mode='scoped')
        enabled = set(args[args.index('--tools') + 1].split(','))
        self.assertTrue({'ToolSearch', 'DeferExecuteTool', 'WaitForMcpServers', 'Skill'} <= enabled)


    def test_native_bridge_permission_is_scoped_to_sceneops(self):
        from sceneops_codebuddy.agent import arguments
        config = {'mcpServers': {'sceneops': {'command': '/fixture/python', 'args': ['bridge.py']}}}
        args = arguments('cli-default', 'low', native_production=True,
            permission_mode='scoped', mcp_config=config)
        self.assertEqual(args[args.index('--permission-mode') + 1], 'acceptEdits')
        self.assertEqual(args[args.index('--allowedTools') + 1:],
            ['DeferExecuteTool(mcp__sceneops__*)', 'mcp__sceneops__*'])
        self.assertNotIn('DeferExecuteTool', args)
        self.assertNotIn('mcp__*', args)
        self.assertNotIn('--allowedTools', arguments('cli-default', 'low'))
        self.assertNotIn('--allowedTools', arguments('cli-default', 'low', native_production=True))
        self.assertNotIn('--allowedTools', arguments('cli-default', 'low', native_production=True,
            mcp_config={'mcpServers': {'unrelated': {'command': '/fixture/python'}}}))
