"""Conversation-memory integration using isolated SQLite and explicit model fixtures."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from conversation_home import AIRepository, create_ai_router
from conversation_home.memory_reply import OPEN, CLOSE, MemoryReplyStream, memory_reply
from sceneops_ai_distiller import ExperienceService, ExperienceSettingsUpdate


class ReplyFramingTests(unittest.TestCase):
    def test_metadata_never_leaks_even_when_delimiter_is_split_at_every_byte(self):
        text = '这是正文。' + OPEN + '[{"content":"内部提案"}]' + CLOSE
        for width in range(1, len(OPEN) + 2):
            stream = MemoryReplyStream()
            visible = ''.join(stream.feed(text[i:i + width]) for i in range(0, len(text), width))
            self.assertEqual(visible + stream.finish(), '这是正文。')
        self.assertEqual(memory_reply(text)[1], [{'content': '内部提案'}])

    def test_malformed_metadata_and_regular_angle_brackets(self):
        self.assertIsNotNone(memory_reply('正文' + OPEN + '{broken')[2])
        self.assertEqual(memory_reply('正文' + OPEN + '[]' + CLOSE + 'other')[1], [])
        stream = MemoryReplyStream()
        self.assertEqual(stream.feed('使用 <scene> 元素') + stream.finish(), '使用 <scene> 元素')


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'test.sqlite3'
        self.repository = AIRepository(self.database)
        self.memory = ExperienceService(self.database, SimpleNamespace(), lambda p: p in {'p', 'other'})
        self.memory.update_settings(ExperienceSettingsUpdate(learn_enabled=False))
        self.memory.set_memory_providers(self.repository.memory_source)
        self.prompts = []
        self.mode = 'save'

        async def generate(prompt, **kwargs):
            payload = json.loads(prompt)
            self.prompts.append(payload)
            source = payload['current_user_source_id']
            proposals = []
            if self.mode == 'save':
                proposals = [dict(title='设备方向', content='使用横屏', category='constraint',
                                  source_id=source, source_quote=payload['message'], intent='explicit')]
            elif self.mode == 'foreign':
                proposals = [dict(title='错误来源', content='不可保存', source_id='message:foreign',
                                  source_quote='请记住外部内容')]
            text = '已收到，记忆保存状态见下方。' + (OPEN + json.dumps(proposals, ensure_ascii=False) + CLOSE if proposals else '')
            if kwargs.get('on_event'):
                for character in text:
                    await kwargs['on_event']({'type': 'text_delta', 'text': character})
            return SimpleNamespace(text=text, model='fixture', provider='codebuddycli')

        self.patch = patch('conversation_home.unified_router.ProviderService.generate', side_effect=generate)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = FastAPI()
        self.app.include_router(create_ai_router(self.database, experience=self.memory))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_frontend_turn_saves_memory_before_next_request_without_learning_calls(self):
        result = self.client.post('/api/ai/chat', json={'project_id': 'p', 'message': '请记住使用横屏'})
        self.assertEqual(result.status_code, 200, result.text)
        messages = result.json()['messages']
        self.assertNotIn(OPEN, messages[-1]['text'])
        memory = self.memory.project_memory('p').entries
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0].content, '使用横屏')
        activity = self.memory.memory_activity('p', 'message:' + messages[0]['id'])
        self.assertEqual(activity.events[0].state, 'saved')
        self.mode = 'read'
        self.client.post('/api/ai/chat', json={'project_id': 'p', 'message': '继续调整'})
        self.assertIn(memory[0].id, {item['id'] for item in self.prompts[-1]['experience_context']['items']})
        self.assertEqual(self.memory.project_memory('other').entries, [])

    def test_stream_hides_metadata_and_rejects_historical_or_foreign_source(self):
        self.repository.append_exchange('other', '请记住外部内容', 'reply', 'fixture',
                                        message_ids=('foreign', 'foreign-assistant'))
        self.mode = 'foreign'
        response = self.client.post('/api/ai/chat/stream', json={'project_id': 'p', 'message': '现在讨论'})
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        text = ''.join(event.get('text', '') for event in events if event['type'] == 'text_delta')
        self.assertNotIn('sceneops-memory', text)
        self.assertNotIn('不可保存', text)
        self.assertEqual(events[-1]['type'], 'complete')
        self.assertEqual(self.memory.project_memory('p').entries, [])
        source = events[-1]['conversation']['messages'][0]['id']
        self.assertEqual(self.memory.memory_activity('p', 'message:' + source).events[0].state, 'failed')
