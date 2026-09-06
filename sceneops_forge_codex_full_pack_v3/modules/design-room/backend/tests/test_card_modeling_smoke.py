"""Isolated source selection and sub-conversation, no real inference or model files."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import JourneyCommand, CardBranch, ProductionCard
from sceneops_project_workspace import SqliteWorkspaceRepository
from test_journey_smoke import FixtureProvider


class CardModelingSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_deep_modeling_alignment_uses_eight_question_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders,
                                             FixtureProvider(alignment_detail='deep'))
            state = service.get(folder.project_id)
            state.stage = 'cards'
            state.cards = [ProductionCard(id='map', title='地图', description='空间', acceptance='检查')]
            state.card_branches = [CardBranch(card_id='map', branch='codex/card-map',
                worktree_path=str(root / 'fixture'), base_commit='fixture')]
            state.active_card_id = 'map'
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)',
                           (state.project_id, state.model_dump_json()))

            async def act(operation, **values):
                nonlocal state
                state = await service.command(state.project_id, JourneyCommand(operation=operation,
                    expected_revision=state.revision, request_id=uuid4().hex, **values))

            await act('choose_model_source', card_id='map', model_source='create')
            await act('message', text='一棵低多边形大树')
            for index in range(8):
                question = state.modeling_sessions[0].messages[-1]
                self.assertIsNotNone(question.question)
                await act('message', question_message_id=question.id, option_index=index % 2)
            messages = state.modeling_sessions[0].messages
            self.assertIsNone(messages[-1].question)
            self.assertEqual(sum(message.question is not None for message in messages), 8)

    async def test_modeling_alignment_uses_four_large_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders,
                                             FixtureProvider(alignment_detail='standard'))
            state = service.get(folder.project_id)
            state.stage = 'cards'
            state.cards = [ProductionCard(id='map', title='地图', description='空间', acceptance='检查')]
            state.card_branches = [CardBranch(card_id='map', branch='codex/card-map',
                worktree_path=str(root / 'fixture'), base_commit='fixture')]
            state.active_card_id = 'map'
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)',
                           (state.project_id, state.model_dump_json()))

            async def act(operation, **values):
                nonlocal state
                state = await service.command(state.project_id, JourneyCommand(operation=operation,
                    expected_revision=state.revision, request_id=uuid4().hex, **values))

            await act('choose_model_source', card_id='map', model_source='create')
            await act('message', text='一棵低多边形大树')
            first = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=first.id, option_index=0)
            second = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=second.id, option_index=1)
            third = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=third.id, option_index=0)
            fourth = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=fourth.id, option_index=1)
            messages = state.modeling_sessions[0].messages
            self.assertIsNone(messages[-1].question)
            self.assertIn('完成对齐', messages[-1].text)
            self.assertEqual(sum(message.question is not None for message in messages), 4)
            self.assertEqual([message.modeling_block for message in messages if message.role == 'user'],
                             ['brief', 'shape', 'scale', 'surface', 'interaction'])

    async def test_concise_modeling_alignment_stops_after_two_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders,
                                             FixtureProvider(alignment_detail='concise'))
            state = service.get(folder.project_id)
            state.stage = 'cards'
            state.cards = [ProductionCard(id='map', title='地图', description='空间', acceptance='检查')]
            state.card_branches = [CardBranch(card_id='map', branch='codex/card-map',
                worktree_path=str(root / 'fixture'), base_commit='fixture')]
            state.active_card_id = 'map'
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)',
                           (state.project_id, state.model_dump_json()))

            async def act(operation, **values):
                nonlocal state
                state = await service.command(state.project_id, JourneyCommand(operation=operation,
                    expected_revision=state.revision, request_id=uuid4().hex, **values))

            await act('choose_model_source', card_id='map', model_source='create')
            await act('message', text='一棵低多边形大树')
            first = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=first.id, option_index=0)
            second = state.modeling_sessions[0].messages[-1]
            await act('message', question_message_id=second.id, option_index=1)
            messages = state.modeling_sessions[0].messages
            self.assertIsNone(messages[-1].question)
            self.assertEqual(sum(message.question is not None for message in messages), 2)
            self.assertEqual([message.modeling_block for message in messages if message.role == 'user'],
                             ['brief', 'shape', 'scale'])

    async def test_source_and_scoped_conversation_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root / 'state.sqlite3', folders, provider)
            state = service.get(folder.project_id)
            state.stage = 'cards'
            state.cards = [ProductionCard(id='map', title='地图', description='空间', acceptance='检查')]
            state.card_branches = [CardBranch(card_id='map', branch='codex/card-map', worktree_path=str(root / 'fixture'), base_commit='fixture')]
            state.active_card_id = 'map'
            state.composer_draft = '项目总对话草稿'
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)', (state.project_id, state.model_dump_json()))

            async def act(operation, **values):
                nonlocal state
                state = await service.command(state.project_id, JourneyCommand(operation=operation,
                    expected_revision=state.revision, request_id=uuid4().hex, **values))

            await act('choose_model_source', card_id='map', model_source='create')
            session_id = state.active_modeling_id
            self.assertEqual(provider.calls, 0)
            await act('save_draft', text='森林模型')
            await act('message', text='森林模型')
            self.assertEqual(len(state.messages), 0)
            self.assertEqual(len(state.modeling_sessions[0].messages), 2)
            self.assertIsNotNone(state.modeling_sessions[0].messages[-1].question)
            self.assertEqual(state.composer_draft, '项目总对话草稿')
            await act('close_modeling', context_draft='尚未发送的模型细节')
            self.assertEqual(state.modeling_sessions[0].composer_draft, '尚未发送的模型细节')
            await act('choose_model_source', card_id='map', model_source='import')
            self.assertEqual(state.modeling_sessions[-1].stage, 'awaiting_import')
            calls = provider.calls
            with self.assertRaises(HTTPException): await act('message', text='假装这是文件')
            self.assertEqual(provider.calls, calls)
            with self.assertRaises(HTTPException):
                await act('open_modeling', card_id='another-card', modeling_id=session_id)
            await act('open_modeling', card_id='map', modeling_id=session_id)
            await act('choose_model_source', card_id='map', model_source='create')
            self.assertEqual(len(state.modeling_sessions), 2)
            await act('new_modeling', card_id='map', model_source='create')
            self.assertEqual(len(state.modeling_sessions), 3)
            self.assertEqual(state.modeling_sessions[-1].id, state.active_modeling_id)
            self.assertEqual(state.modeling_sessions[-1].messages, [])
            restored = PlanningJourneyService(root / 'state.sqlite3', folders, provider).get(state.project_id)
            self.assertEqual(restored, state)
            self.assertEqual(restored.modeling_sessions[0].mode, 'planned')
            self.assertFalse(list(Path(folder.root_path).rglob('*.glb')))
