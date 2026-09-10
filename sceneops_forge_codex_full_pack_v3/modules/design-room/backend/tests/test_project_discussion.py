import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
from pydantic import ValidationError
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import JourneyCommand, ProjectDiscussionReply

DIRECTION = dict(core_experience='收集三颗星后返回基地', perspective_style='俯视太空',
                 simplified_scope='单关，有胜负与重开', code_architecture='object-component', camera_mode='fit-scene')
QUESTION = dict(prompt='主要挑战是什么？', options=[dict(label='躲避巡逻机', description='节奏轻快'),
                dict(label='限时寻路', description='偏探索')], recommended_index=0)

class Provider:
    calls = 0
    def settings(self): return SimpleNamespace(model='fixture', provider='codebuddycli')
    async def generate(self, prompt, **kwargs):
        self.calls += 1
        reply = dict(text='先确定主要挑战。', question=QUESTION) if self.calls == 1 else dict(text='收集星星并躲避巡逻机，返回基地获胜。', direction=DIRECTION)
        return SimpleNamespace(text=json.dumps(reply), provider='codebuddycli', model='fixture')

class DiscussionSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_discussion_to_production_without_cards_or_model_granted_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'conversation')
            provider = Provider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(project.project_id)
            async def act(operation, **kw):
                nonlocal state
                state = await service.command(project.project_id, JourneyCommand(request_id=f'r{state.revision}',
                    expected_revision=state.revision, operation=operation, **kw))
                return state
            await act('set_execution_policy', execution_policy='full-access')
            self.assertEqual(provider.calls, 0)
            await act('discuss_game', text='做个收集星星的小游戏')
            question_id = state.messages[-1].id
            self.assertIsNotNone(state.messages[-1].question)
            self.assertIsNone(state.technical_plan)
            await act('discuss_game', question_message_id=question_id, option_index=0)
            self.assertEqual(state.messages[-2].reply_to, question_id)
            self.assertIsNotNone(state.demo_direction_draft)
            self.assertIsNone(state.technical_plan)
            self.assertEqual(state.execution_policy, 'full-access')
            self.assertEqual(state.cards, [])
            with self.assertRaises(HTTPException):
                await service.command(project.project_id, JourneyCommand(request_id='stale-answer',
                    expected_revision=state.revision, operation='discuss_game', question_message_id=question_id, option_index=0))
            await act('confirm_demo_direction', **DIRECTION)
            self.assertTrue(state.initial_demo_direction.confirmed)
            self.assertEqual(state.initial_demo_direction.camera_mode, 'fit-scene')
            self.assertIsNotNone(state.technical_plan)
            self.assertEqual(state.cards, [])
            self.assertEqual(service.get(project.project_id).execution_policy, 'full-access')
            self.assertEqual(provider.calls, 2)

    def test_model_cannot_grant_permissions_or_both_ask_and_prepare(self):
        with self.assertRaises(ValidationError):
            ProjectDiscussionReply(text='开始', direction=DIRECTION, execution_policy='full-access')
        with self.assertRaises(ValidationError):
            ProjectDiscussionReply(text='还有问题', direction=DIRECTION, question=QUESTION)
