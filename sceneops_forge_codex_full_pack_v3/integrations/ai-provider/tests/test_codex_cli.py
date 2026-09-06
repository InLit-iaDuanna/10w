"""Deterministic Codex transport contracts; never invoke live inference."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from sceneops_ai_provider import codex_cli


def transcript(text='你好', usage=None):
    return ('\n'.join(json.dumps(event, ensure_ascii=False) for event in [
        {'type': 'thread.started', 'thread_id': 'fixture-thread'},
        {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'not the reply'}},
        {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}},
        {'type': 'turn.completed', 'usage': usage},
    ]) + '\n').encode()


class CodexTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_primary_path(self):
        runner = AsyncMock(side_effect=[(codex_cli.SUPPORTED_VERSION + b'\n', b'', 0),
            (transcript('{"ok":true}', {'input_tokens': 12, 'output_tokens': 3}), b'', 0)])
        schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
        with patch.object(codex_cli.shutil, 'which', return_value='/fixture/codex'), \
                patch.object(codex_cli, '_run', runner):
            result = await codex_cli.invoke_json('只回答状态', schema=schema)
        self.assertEqual(result['structured_output'], {'ok': True})
        self.assertEqual(result['usage'], {'input_tokens': 12, 'output_tokens': 3})
        arguments = runner.call_args.args[1]
        self.assertNotIn('只回答状态', arguments)
        self.assertIn('只回答状态'.encode(), runner.call_args.args[3])
        self.assertIn('--ignore-user-config', arguments)
        self.assertIn('--ignore-rules', arguments)
        self.assertIn('orchestrator.mcp.enabled=false', arguments)
        self.assertIn('features.shell_tool=false', arguments)
        self.assertIn('features.hooks=false', arguments)

    async def test_incompatible_version_never_starts_inference(self):
        runner = AsyncMock(return_value=(b'codex-cli 0.99.0\n', b'', 0))
        with patch.object(codex_cli.shutil, 'which', return_value='/fixture/codex'), \
                patch.object(codex_cli, '_run', runner):
            with self.assertRaises(codex_cli.CodexFailure) as failure:
                await codex_cli.invoke_json('hello')
        self.assertEqual(failure.exception.code, 'CODEX_VERSION_UNSUPPORTED')
        self.assertEqual(runner.await_count, 1)

    def test_explicit_model_is_passed_as_one_argument(self):
        arguments = codex_cli._arguments('gpt-example')
        self.assertEqual(arguments[arguments.index('--model') + 1], 'gpt-example')
        self.assertNotIn('--model', codex_cli._arguments())

    def test_failed_transcript_does_not_expose_provider_text(self):
        with self.assertRaises(codex_cli.CodexFailure) as failure:
            codex_cli._parse_output(b'{"type":"turn.failed","error":{"message":"401 secret-token"}}')
        self.assertEqual(failure.exception.code, 'CODEX_AUTH_REQUIRED')
        self.assertNotIn('secret-token', str(failure.exception))

    def test_incomplete_and_invalid_structured_output_rejected(self):
        with self.assertRaises(codex_cli.CodexFailure):
            codex_cli._parse_output(b'{"type":"item.completed","item":{"type":"agent_message","text":"hi"}}')
        with self.assertRaises(codex_cli.CodexFailure) as failure:
            codex_cli._structured_result({'result': '{"ok":"yes"}'},
                {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}})
        self.assertEqual(failure.exception.code, 'CODEX_STRUCTURED_INVALID')

    async def test_output_is_bounded(self):
        stream = Mock(read=AsyncMock(side_effect=[b'abcd', b'e']))
        with patch.object(codex_cli, 'MAX_OUTPUT_BYTES', 4):
            with self.assertRaises(codex_cli.CodexFailure) as failure:
                await codex_cli._read_bounded(stream)
        self.assertEqual(failure.exception.code, 'CODEX_OUTPUT_LIMIT')

    async def test_timeout_and_cancellation_stop_process(self):
        for exception in (asyncio.TimeoutError(), asyncio.CancelledError()):
            process = Mock()
            with patch.object(codex_cli.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)), \
                    patch.object(codex_cli, '_exchange', AsyncMock(side_effect=exception)), \
                    patch.object(codex_cli, '_stop', AsyncMock()) as stop:
                expected = codex_cli.CodexFailure if isinstance(exception, asyncio.TimeoutError) else asyncio.CancelledError
                with self.assertRaises(expected):
                    await codex_cli._run('/fixture/codex', [], '/tmp', b'hello', 1)
                stop.assert_awaited_once_with(process)

    def test_parent_endpoint_and_secrets_are_not_inherited(self):
        with patch.dict(codex_cli.os.environ, {'HOME': '/fixture/home', 'CODEX_HOME': '/fixture/codex',
                'OPENAI_API_KEY': 'secret', 'OPENAI_BASE_URL': 'https://unexpected.invalid',
                'CODEX_THREAD_ID': 'parent-thread', 'CODEX_EXEC_SERVER_URL': 'ws://unexpected.invalid',
                'CODEX_EXEC_SERVER_NOISE_AUTH_TOKEN': 'parent-runtime-secret'}, clear=True):
            self.assertEqual(codex_cli._environment(), {'HOME': '/fixture/home', 'CODEX_HOME': '/fixture/codex',
                                                       'CODEX_EXEC_SERVER_URL': 'none'})

    async def test_agent_uses_full_access_only_in_explicit_entry(self):
        event = {'type': 'item.completed', 'item': {'type': 'command_execution', 'status': 'completed',
                 'command': 'echo secret-token', 'aggregated_output': 'secret-token'}}
        async def run(*args, **kwargs):
            if args[1] == ['--version']:
                return codex_cli.SUPPORTED_VERSION, b'', 0
            for summary in codex_cli._event_summaries([event]):
                await kwargs['on_event'](summary)
            return json.dumps(event).encode() + b'\n' + transcript('完成'), b'', 0
        runner = AsyncMock(side_effect=run)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(codex_cli.shutil, 'which', return_value='/fixture/codex'), \
                patch.object(codex_cli, '_run', runner):
            root = Path(directory).resolve()
            result = await codex_cli.invoke_agent('完成任务', workspace_root=root, authorized_scope='仅本次独立项目。')
        arguments = runner.call_args.args[1]
        self.assertIn('danger-full-access', arguments)
        self.assertIn('features.shell_tool=true', arguments)
        self.assertIn('features.unified_exec=true', arguments)
        self.assertIn('features.plugins=false', arguments)
        self.assertIn('model_reasoning_effort="low"', arguments)
        instructions = next(value for value in arguments if value.startswith('developer_instructions='))
        self.assertIn('服务端授权范围：仅本次独立项目。', instructions)
        self.assertNotIn('完成任务', instructions)
        self.assertEqual(runner.call_args.args[2], str(root))
        self.assertIs(runner.call_args.kwargs['full_access'], True)
        self.assertEqual(result['events'], [{'type': 'command_execution', 'phase': 'completed',
                                            'status': 'completed', 'verification': 'reported'}])
        self.assertNotIn('secret-token', json.dumps(result))
        self.assertIn('read-only', codex_cli._arguments())
        self.assertEqual(codex_cli._environment()['CODEX_EXEC_SERVER_URL'], 'none')
        with patch.dict(codex_cli.os.environ, {'CODEX_EXEC_SERVER_URL': 'ws://unrelated.invalid'}):
            self.assertNotIn('CODEX_EXEC_SERVER_URL', codex_cli._environment(full_access=True))

    async def test_agent_rejects_missing_relative_and_symlink_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            link = root / 'link'
            link.symlink_to(root, target_is_directory=True)
            for path in (Path('relative'), root / 'missing', link):
                with self.subTest(path=path), patch.object(codex_cli, '_run', AsyncMock()) as runner:
                    with self.assertRaises(codex_cli.CodexFailure) as failure:
                        await codex_cli.invoke_agent('task', workspace_root=path, authorized_scope='仅本次独立项目。')
                    self.assertEqual(failure.exception.code, 'CODEX_WORKSPACE_INVALID')
                    runner.assert_not_awaited()

    def test_reasoning_does_not_invent_lite_enum(self):
        self.assertIn('model_reasoning_effort="low"', codex_cli._arguments('gpt-5.6-sol'))
        with self.assertRaises(codex_cli.CodexFailure):
            codex_cli._arguments(reasoning_effort='lite')

    async def test_stream_emits_sanitized_event_before_process_completes(self):
        process = Mock(returncode=0, stdout=asyncio.StreamReader(), stderr=asyncio.StreamReader())
        process.stdin = Mock(drain=AsyncMock())
        process.wait = AsyncMock(return_value=0)
        observed, first_event = [], asyncio.Event()
        async def receive(event):
            observed.append(event)
            first_event.set()
        with patch.object(codex_cli.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)), \
                patch.object(codex_cli, '_stop', AsyncMock()):
            running = asyncio.create_task(codex_cli._run('/fixture/codex', [], '/tmp', b'task', 2,
                full_access=True, on_event=receive))
            event = {'type': 'item.started', 'item': {'id': 'item_7', 'type': 'command_execution',
                'status': 'in_progress', 'command': 'secret-command', 'aggregated_output': 'secret-output'}}
            encoded = json.dumps(event).encode() + b'\n'
            process.stdout.feed_data(encoded[:17])
            process.stdout.feed_data(encoded[17:])
            await asyncio.wait_for(first_event.wait(), 1)
            self.assertFalse(running.done())
            process.stdout.feed_data(transcript('done'))
            process.stdout.feed_eof()
            process.stderr.feed_eof()
            await running
        self.assertEqual(observed[0], {'item_id': 'item_7', 'type': 'command_execution',
            'phase': 'started', 'status': 'in_progress', 'verification': 'reported'})
        self.assertNotIn('secret', json.dumps(observed))

    def test_plan_and_existing_artifact_candidates_are_reported_not_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'scene.glb').touch()
            (root / 'link.glb').symlink_to(root / 'scene.glb')
            events = codex_cli._event_summaries([
                {'type': 'item.updated', 'item': {'id': 'item_1', 'type': 'todo_list',
                    'items': [{'text': 'secret-plan-content', 'completed': True}]}},
                {'type': 'item.completed', 'item': {'id': 'item_2', 'type': 'file_change', 'status': 'completed',
                    'changes': [{'path': path, 'kind': 'add'} for path in
                                ['scene.glb', 'link.glb', '../outside.glb', 'missing.png']]}}
            ], workspace_root=root)
        self.assertEqual(events[0]['steps'], [{'index': 0, 'completed': True, 'verification': 'reported'}])
        self.assertEqual(events[1]['files'], [{'path': 'scene.glb', 'kind': 'add', 'verification': 'exists'}])
        self.assertNotIn('secret', json.dumps(events))

    def test_native_image_generation_requires_explicit_full_access_opt_in(self):
        self.assertIn('features.image_generation=false', codex_cli._arguments())
        enabled = codex_cli._arguments(full_access=True, authorized_scope='允许本次任务图像生成。',
                                       allow_image_generation=True)
        self.assertIn('features.image_generation=true', enabled)
        self.assertIn('features.plugins=false', enabled)
        self.assertIn('orchestrator.mcp.enabled=false', enabled)


if __name__ == '__main__':
    unittest.main()
