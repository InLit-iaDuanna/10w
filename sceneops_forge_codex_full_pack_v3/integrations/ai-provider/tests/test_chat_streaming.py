"""Deterministic transport fixtures; no model, network or external process calls."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

from sceneops_ai_provider.codex_cli import _chat_event
from sceneops_ai_provider.openai_stream import _events, _response_events
from sceneops_codebuddy.provider import CodeBuddyFailure, _stream_event, _stream_exchange


class ChatStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_codebuddy_callback_precedes_process_completion(self):
        process = Mock()
        process.stdin = Mock(drain=AsyncMock())
        process.stdout, process.stderr = asyncio.StreamReader(), asyncio.StreamReader()
        process.wait = AsyncMock()
        received = asyncio.Event()
        values = []
        async def receive(event):
            values.append(event)
            received.set()
        task = asyncio.create_task(_stream_exchange(process, b'fixture', receive))
        line = json.dumps({'type': 'stream_event', 'event': {'type': 'content_block_delta',
            'delta': {'type': 'text_delta', 'text': '你好'}}}).encode() + b'\n'
        process.stdout.feed_data(line[:20])
        process.stdout.feed_data(line[20:])
        try:
            await asyncio.wait_for(received.wait(), 1)
            self.assertFalse(task.done())
            self.assertEqual(values, [{'type': 'text_delta', 'text': '你好'}])
        finally:
            process.stdout.feed_eof()
            process.stderr.feed_eof()
            await task

    async def test_invalid_stream_fails_without_raw_output(self):
        process = Mock(stdin=Mock(drain=AsyncMock()), wait=AsyncMock())
        process.stdout, process.stderr = asyncio.StreamReader(), asyncio.StreamReader()
        process.stdout.feed_data(b'private-invalid-output\n')
        process.stdout.feed_eof()
        process.stderr.feed_eof()
        with self.assertRaises(CodeBuddyFailure) as caught:
            await _stream_exchange(process, b'fixture', AsyncMock())
        self.assertNotIn('private', str(caught.exception))

    async def test_sse_fragmented_utf8_and_multiline(self):
        class Response:
            async def aiter_bytes(self):
                raw = 'data: 你好\r\ndata: world\r\n\r\n'.encode()
                for value in raw:
                    yield bytes([value])
        self.assertEqual([value async for value in _events(Response())], ['你好\nworld'])

    async def test_responses_stream_uses_delta_and_completed_response(self):
        completed = {'status': 'completed', 'output': [{'type': 'message',
            'content': [{'type': 'output_text', 'text': '你好'}]}],
            'usage': {'input_tokens': 2, 'output_tokens': 1, 'total_tokens': 3}}
        frames = [
            {'type': 'response.output_text.delta', 'delta': '你'},
            {'type': 'response.output_text.delta', 'delta': '好'},
            {'type': 'response.completed', 'response': completed},
        ]
        class Response:
            async def aiter_bytes(self):
                yield ''.join(f'data: {json.dumps(frame, ensure_ascii=False)}\n\n'
                              for frame in frames).encode()
        received = AsyncMock()
        text, usage = await _response_events(Response(), received)
        self.assertEqual(text, '你好')
        self.assertEqual(usage, {'input_tokens': 2, 'output_tokens': 1, 'total_tokens': 3})
        self.assertEqual([call.args[0]['text'] for call in received.await_args_list], ['你', '好'])

    def test_only_actual_text_and_reasoning_are_forwarded(self):
        self.assertIsNone(_chat_event({'type': 'item.completed', 'item': {
            'type': 'command_execution', 'aggregated_output': 'private'}}))
        self.assertEqual(_chat_event({'type': 'item.completed', 'item': {
            'type': 'reasoning', 'text': 'provider summary'}}),
            {'type': 'reasoning_delta', 'text': 'provider summary'})
        self.assertIsNone(_stream_event({'type': 'stream_event', 'event': {
            'type': 'content_block_delta', 'delta': {'type': 'signature_delta', 'signature': 'private'}}}))


if __name__ == '__main__':
    unittest.main()
