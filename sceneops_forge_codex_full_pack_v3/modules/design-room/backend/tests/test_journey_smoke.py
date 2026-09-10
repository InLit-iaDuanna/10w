"""One isolated planning path and boundary checks, with a labelled provider fixture."""
import json
import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
from sceneops_ai_provider import ProviderFailure
from sceneops_project_workspace import GitProjectError, SqliteWorkspaceRepository
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import (JourneyCommand, Outline, JourneyVersion,
    ProductionCard, GrillReply, GameTechnicalPlan, GameProjectScaffold, JourneyMessage,
    PlanningQuestion, QuestionOption)


class FixtureProvider:
    def __init__(self, alignment_detail='standard'):
        self.calls = 0
        self.alignment_detail = alignment_detail
    def settings(self):
        return SimpleNamespace(model='fixture', provider='codebuddycli',
                               alignment_detail=self.alignment_detail)
    async def generate(self, prompt, **kwargs):
        self.calls += 1
        self.last_prompt = prompt
        schema = kwargs.get('schema')
        if schema and schema['title'] == 'Outline':
            text = Outline(title='烟测策划', experience='探索', core_loop='移动到出口', scope='一个场景', acceptance='到达出口').model_dump_json()
        elif schema and schema['title'] == 'GrillReply':
            text = json.dumps({'text': '先确定目标。', 'question': {'prompt':'玩家的主要目标是什么？',
                'options':[{'label':'探索', 'description':'寻找出口'}, {'label':'战斗', 'description':'击败敌人'}], 'recommended_index':0}})
        elif schema and schema['title'] == 'AlignmentSummaryReply':
            text = json.dumps({'text': '已按当前详细程度完成对齐，可以生成下一步方案。'})
        elif schema and schema['title'] == 'ArchitectureRecommendation':
            text = json.dumps({'code_architecture':'ecs','rationale':'实体较多，规则适合按系统组合。',
                'tradeoffs':['批量更新清楚','需要理解实体与系统']})
        elif schema and schema['title'] == 'RevisionReply':
            text = json.dumps({'text':'已提出地图修改，等待确认。', 'revised_outline':None,
                'revised_cards':[{'id':'map','title':'森林地图','description':'森林空间','dependencies':[], 'acceptance':'存在出口','status':'planned'}], 'rationale':'按用户要求改为森林。'})
        elif schema and schema['title'] == 'DomainCardProposal':
            text = json.dumps({'cards': [
                {'id':'world-3d', 'domain_ids':['assets-animation','world','lookdev'], 'title':'3D 世界', 'description':'场景与资产', 'dependencies':[], 'acceptance':'世界可见', 'status':'planned'},
                {'id':'core-gameplay', 'domain_ids':['gameplay'], 'title':'核心玩法', 'description':'移动与交互', 'dependencies':['world-3d'], 'acceptance':'玩法可运行', 'status':'planned'},
                {'id':'growth-feedback', 'domain_ids':['ui-audio'], 'title':'成长与反馈', 'description':'界面与反馈', 'dependencies':['core-gameplay'], 'acceptance':'反馈清晰', 'status':'planned'},
                {'id':'demo-delivery', 'domain_ids':['delivery'], 'title':'完成 Demo', 'description':'整合与交付', 'dependencies':['growth-feedback'], 'acceptance':'可以交付', 'status':'planned'},
            ]})
        elif schema:
            text = json.dumps({'cards': [{'id':'map', 'title':'地图', 'description':'基础空间', 'dependencies':[], 'acceptance':'存在出口', 'status':'planned'}]})
        else: text = '你希望玩家最主要的目标是什么？建议先确定探索目标。'
        if kwargs.get('on_event'):
            await kwargs['on_event']({'type': 'text_delta', 'text': text})
        return SimpleNamespace(text=text, provider='codebuddycli', model='fixture')


class FixturePreparation:
    def __init__(self):
        self.calls = []

    async def prepare(self, request):
        self.calls.append(request)
        return SimpleNamespace(call=SimpleNamespace(status='succeeded'),
            model_dump=lambda **_kwargs: {'status':'succeeded', 'recommendation':{
                'assets':[], 'experiences':[{'candidate_id':'camera-single-screen',
                    'revision':1, 'purpose':'镜头', 'adoption':'reference', 'reason':'匹配'}],
                'skills':[], 'production_advice':[], 'conflicts':[], 'gaps':[]}})

    async def selected_context(self, request, result):
        return {'status':'succeeded', 'recommendation':result.model_dump()['recommendation'],
                'selected_details':[{'identity':{'candidate_id':'camera-single-screen'},
                                     'content':{'body':'固定看到完整可玩区域'}}]}


class JourneySmoke(unittest.IsolatedAsyncioTestCase):
    async def test_planning_uses_one_preparation_call_without_bulk_experience_injection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            preparation = FixturePreparation()
            service = PlanningJourneyService(root / 'state.sqlite3', folders, provider,
                                             production_preparation=preparation)
            state = service.get(project.project_id)

            result = await service.generate(state, '讨论一屏收集游戏')

            self.assertIn('固定看到完整可玩区域', provider.last_prompt)
            self.assertNotIn('experience_context', provider.last_prompt)
            self.assertEqual(len(preparation.calls), 1)
            self.assertEqual(state.model_calls, 2)
            self.assertEqual(state.production_preparation['status'], 'succeeded')

    async def test_short_demo_direction_creates_project_without_outline_cards_and_reopens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root / 'state.sqlite3', folders, provider)

            with self.assertRaisesRegex(HTTPException, '确认第一版 Demo'):
                service.project_demo_context(project.project_id)
            state = await service.command(project.project_id, JourneyCommand(
                request_id='confirm-short-direction', expected_revision=0,
                operation='confirm_demo_direction', core_experience='找到钥匙并打开出口门',
                perspective_style='第三人称俯视、低多边形森林',
                simplified_scope='一个场景、一把钥匙、两扇共享木门',
                code_architecture='ecs', selection_method='manual'))

            self.assertTrue(state.initial_demo_direction.confirmed)
            self.assertTrue(state.initial_demo_direction.direction_id.startswith('direction_'))
            self.assertEqual(state.technical_plan.code_architecture, 'ecs')
            self.assertEqual(state.technical_plan.scaffold.design_version, 1)
            self.assertIsNone(state.outline)
            self.assertEqual(state.versions, [])
            self.assertEqual(state.cards, [])
            self.assertEqual(provider.calls, 0)
            game_root = Path(state.technical_plan.scaffold.root_path)
            self.assertTrue((game_root / 'src/game/systems/movementSystem.ts').is_file())
            direction_id = state.initial_demo_direction.direction_id
            context = service.project_demo_context(project.project_id)
            self.assertEqual(context['direction_id'], direction_id)
            self.assertEqual(context['technical_plan']['ecs_library'], 'miniplex')

            repeated = await service.command(project.project_id, JourneyCommand(
                request_id='repeat-short-direction', expected_revision=state.revision,
                operation='confirm_demo_direction', core_experience='找到钥匙并打开出口门',
                perspective_style='第三人称俯视、低多边形森林',
                simplified_scope='一个场景、一把钥匙、两扇共享木门',
                code_architecture='ecs', selection_method='manual'))
            self.assertEqual(repeated.initial_demo_direction.direction_id, direction_id)

            changed = await service.command(project.project_id, JourneyCommand(
                request_id='change-short-direction', expected_revision=repeated.revision,
                operation='confirm_demo_direction', core_experience='找到钥匙并打开出口门',
                perspective_style='第三人称俯视、低多边形森林',
                simplified_scope='一个场景、一把钥匙、一扇出口门',
                code_architecture='ecs', selection_method='manual'))
            self.assertNotEqual(changed.initial_demo_direction.direction_id, direction_id)
            self.assertEqual(changed.versions, [])
            reopened = PlanningJourneyService(
                root / 'state.sqlite3', folders, provider).get(project.project_id)
            self.assertEqual(reopened.initial_demo_direction, changed.initial_demo_direction)
            self.assertEqual(service.project_demo_context(project.project_id)['direction_id'],
                             changed.initial_demo_direction.direction_id)

    async def test_moved_project_returns_current_root_in_saved_journey(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders, FixtureProvider())
            state = service.get(project.project_id)
            state.technical_plan = GameTechnicalPlan(code_architecture='object-component',
                architecture_label='对象／组件式', selection_method='manual', rationale='测试',
                tradeoffs=['测试'], scaffold=GameProjectScaffold(root_path=project.root_path,
                    initialization_status='generated'), selected_at='2026-09-07T00:00:00Z')
            with service.connection() as database:
                database.execute('INSERT OR REPLACE INTO design_journeys VALUES (?,?)',
                                 (project.project_id, state.model_dump_json()))
            moved_root = root / 'moved'
            shutil.move(project.root_path, moved_root)
            folders.recover_folder_project(moved_root, 'move')

            moved = service.get(project.project_id)

            self.assertEqual(moved.root_path, str(moved_root))
            self.assertEqual(moved.technical_plan.scaffold.root_path, str(moved_root))

    async def test_recovered_project_imports_its_saved_conversation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original_database = root / 'original.sqlite3'
            folders = SqliteWorkspaceRepository(original_database)
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(original_database, folders, FixtureProvider())
            saved = await service.command(project.project_id, JourneyCommand(
                request_id='idea', expected_revision=0, operation='message', text='做一个探索游戏'))

            recovered_database = root / 'recovered.sqlite3'
            recovered_folders = SqliteWorkspaceRepository(recovered_database)
            recovered_folders.recover_folder_project(project.root_path, 'restore')
            recovered_service = PlanningJourneyService(
                recovered_database, recovered_folders, FixtureProvider())
            restored = recovered_service.get(project.project_id)

            self.assertEqual(restored.messages, saved.messages)
            self.assertEqual(restored.revision, saved.revision)
            self.assertEqual(restored.model_calls, saved.model_calls)
            with recovered_service.connection() as database:
                self.assertEqual(database.execute(
                    'SELECT COUNT(*) FROM design_journeys WHERE project_id=?',
                    (project.project_id,)).fetchone()[0], 1)
            self.assertEqual(
                PlanningJourneyService(recovered_database, recovered_folders, FixtureProvider())
                .get(project.project_id).messages,
                saved.messages)

    async def test_recovered_project_rejects_another_projects_conversation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original_database = root / 'original.sqlite3'
            folders = SqliteWorkspaceRepository(original_database)
            project = folders.create_folder_project(root, 'project')
            state = PlanningJourneyService(original_database, folders, FixtureProvider()).get(project.project_id)
            folders.write_design_draft(project.project_id,
                state.model_copy(update={'project_id': 'prj_another'}).model_dump(mode='json'))

            recovered_database = root / 'recovered.sqlite3'
            recovered_folders = SqliteWorkspaceRepository(recovered_database)
            recovered_folders.recover_folder_project(project.root_path, 'restore')
            recovered_service = PlanningJourneyService(
                recovered_database, recovered_folders, FixtureProvider())

            with self.assertRaisesRegex(HTTPException, '属于另一个项目'):
                recovered_service.get(project.project_id)

    async def test_card_discussion_is_saved_in_its_own_conversation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders, FixtureProvider())
            state = service.get(project.project_id)
            state.stage = 'cards'
            state.outline = Outline(title='探索', experience='移动', core_loop='移动与交互',
                scope='一个场景', acceptance='可以完成目标')
            state.versions = [JourneyVersion(number=1, confirmed_at='2026-09-07T00:00:00Z',
                outline=state.outline)]
            state.cards = [ProductionCard(id='gameplay', title='核心玩法', description='移动与交互',
                dependencies=[], acceptance='玩法可运行', status='planned')]
            await service.apply(state, JourneyCommand(request_id='select', expected_revision=0,
                operation='select_card', card_id='gameplay', main_scroll_top=412.5))
            self.assertEqual(state.main_scroll_top, 412.5)
            with service.connection() as database:
                database.execute('INSERT INTO design_journeys VALUES (?,?)',
                    (project.project_id, state.model_dump_json()))

            replied = await service.command(project.project_id, JourneyCommand(
                request_id='card-chat', expected_revision=0, operation='message', text='如何实现'))

            self.assertEqual(replied.messages, [])
            self.assertEqual([message.role for message in replied.card_messages['gameplay']],
                             ['user', 'assistant'])
            self.assertEqual(replied.card_messages['gameplay'][0].text, '如何实现')
            self.assertIn('已提出地图修改', replied.card_messages['gameplay'][1].text)
            with self.assertRaisesRegex(HTTPException, '完成本轮实现对齐'):
                service.development_context(project.project_id, 'gameplay')
            replied.card_alignment_summaries['gameplay'] = '只实现移动到出口的可试玩切片。'
            with service.connection() as database:
                database.execute('UPDATE design_journeys SET payload=? WHERE project_id=?',
                    (replied.model_dump_json(), project.project_id))
            context = service.development_context(project.project_id, 'gameplay')
            self.assertEqual([message['role'] for message in context['card_discussion']],
                             ['user', 'assistant'])
            self.assertEqual(context['card_alignment_summary'], '只实现移动到出口的可试玩切片。')

    async def test_card_coding_requires_completed_bounded_alignment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root / 'state.sqlite3', folders, FixtureProvider())
            state = service.get(project.project_id)
            state.stage = 'cards'
            state.outline = Outline(title='探索', experience='移动', core_loop='移动与交互',
                scope='一个场景', acceptance='可以完成目标')
            state.versions = [JourneyVersion(number=1, confirmed_at='2026-09-07T00:00:00Z',
                outline=state.outline)]
            state.technical_plan = GameTechnicalPlan(code_architecture='ecs', architecture_label='ECS',
                selection_method='manual', rationale='测试技术方案', tradeoffs=['测试'], ecs_library='miniplex',
                scaffold=GameProjectScaffold(root_path=str(root / 'project'), initialization_status='generated'),
                selected_at='2026-09-07T00:00:00Z')
            state.cards = [ProductionCard(id='gameplay', title='核心玩法', description='移动与交互',
                dependencies=[], acceptance='玩法可运行', status='planned')]
            state.active_card_id = 'gameplay'

            # The implementation-alignment command must start with one question and cannot unlock Coding early.
            await service.apply(state, JourneyCommand(request_id='align', expected_revision=0,
                operation='start_card_alignment'))
            self.assertIsNotNone(state.card_messages['gameplay'][-1].question)
            self.assertNotIn('gameplay', state.card_alignment_summaries)

            for turn in range(4):
                question = state.card_messages['gameplay'][-1]
                await service.apply(state, JourneyCommand(request_id=f'answer-{turn}', expected_revision=0,
                    operation='message', question_message_id=question.id, option_index=0))

            self.assertEqual(state.card_alignment_summaries['gameplay'],
                '已按当前详细程度完成对齐，可以生成下一步方案。')
            self.assertIsNone(state.card_messages['gameplay'][-1].question)
            self.assertIn('确认执行后才会开始', state.card_messages['gameplay'][-1].text)
            self.assertEqual(state.card_alignment_summary_ids['gameplay'], state.card_messages['gameplay'][-1].id)

            await service.apply(state, JourneyCommand(request_id='realign', expected_revision=0,
                operation='start_card_alignment'))
            next_round = state.card_messages['gameplay'][-1]
            await service.apply(state, JourneyCommand(request_id='realign-answer', expected_revision=0,
                operation='message', question_message_id=next_round.id, option_index=0))
            self.assertNotIn('gameplay', state.card_alignment_summaries)
            self.assertIsNotNone(state.card_messages['gameplay'][-1].question)

    async def test_card_entry_alignment_and_manual_finish_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root / 'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root / 'state.sqlite3', folders, provider)
            state = service.get(project.project_id)
            state.stage = 'cards'
            state.outline = Outline(title='探索', experience='移动', core_loop='移动到出口',
                scope='一个场景', acceptance='找到出口')
            state.versions = [JourneyVersion(number=1, confirmed_at='2026-09-07T00:00:00Z', outline=state.outline)]
            state.technical_plan = GameTechnicalPlan(code_architecture='ecs', architecture_label='ECS',
                selection_method='manual', rationale='测试方案', tradeoffs=['测试'], ecs_library='miniplex',
                scaffold=GameProjectScaffold(root_path=str(root / 'project'), initialization_status='generated'),
                selected_at='2026-09-07T00:00:00Z')
            for card_id in ('world-3d', 'core-gameplay', 'growth-feedback', 'demo-delivery'):
                state.cards.append(ProductionCard(id=card_id, title=card_id, description='小切片',
                    dependencies=[], acceptance='可以试玩', status='planned'))
                calls = provider.calls
                command = JourneyCommand(request_id=card_id, expected_revision=0,
                    operation='select_card', card_id=card_id)
                await service.apply(state, command)
                self.assertEqual(provider.calls, calls + 1)
                first = state.card_messages[card_id][-1]
                self.assertEqual(state.card_alignment_start_ids[card_id], first.id)
                await service.apply(state, command)
                self.assertEqual(provider.calls, calls + 1)
                with self.assertRaisesRegex(HTTPException, '先讨论'):
                    await service.apply(state, JourneyCommand(request_id='empty', expected_revision=0,
                        operation='finish_card_alignment'))
                await service.apply(state, JourneyCommand(request_id='answer', expected_revision=0,
                    operation='message', question_message_id=first.id, option_index=0))
                await service.apply(state, JourneyCommand(request_id='finish', expected_revision=0,
                    operation='finish_card_alignment'))
                summary_id = state.card_alignment_summary_ids[card_id]
                self.assertEqual(summary_id, state.card_messages[card_id][-1].id)
                self.assertIn('是否现在按这个范围制作可试玩 Demo', state.card_messages[card_id][-1].text)
                self.assertEqual(service._development_context(state, card_id)['card_alignment_id'], summary_id)
                calls = provider.calls
                await service.apply(state, JourneyCommand(request_id='repeat-finish', expected_revision=0,
                    operation='finish_card_alignment'))
                self.assertEqual(provider.calls, calls)
                await service.apply(state, JourneyCommand(request_id='scope-change', expected_revision=0,
                    operation='message', text='缩小范围，只做出口标记。'))
                self.assertNotIn(card_id, state.card_alignment_summaries)
                self.assertNotIn(card_id, state.card_alignment_summary_ids)
                self.assertIsNotNone(state.card_messages[card_id][-1].question)

    async def test_structured_failure_retries_once_with_feedback(self):
        class FailOnceProvider(FixtureProvider):
            def __init__(self):
                super().__init__()
                self.prompts = []

            async def generate(self, prompt, **kwargs):
                self.prompts.append(prompt)
                if len(self.prompts) == 1:
                    self.calls += 1
                    raise ProviderFailure('CLI_STRUCTURED_INVALID',
                        'CodeBuddy JSON 未通过结构校验（additionalProperties）。')
                return await super().generate(prompt, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = FailOnceProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(project.project_id)

            result = await service.generate(state, '生成一个问题。', GrillReply)

            self.assertEqual(provider.calls, 2)
            self.assertEqual(state.model_calls, 2)
            self.assertIn('你上一次对同一请求的返回是错误的', provider.prompts[1])
            self.assertIn('CLI_STRUCTURED_INVALID', provider.prompts[1])
            self.assertEqual(service.get(project.project_id).model_calls, 2)
            self.assertEqual(GrillReply.model_validate_json(result.text).text, '先确定目标。')

    async def test_structured_failure_stops_after_one_automatic_retry(self):
        class AlwaysInvalidProvider(FixtureProvider):
            async def generate(self, prompt, **kwargs):
                self.calls += 1
                raise ProviderFailure('CLI_STRUCTURED_INVALID',
                    'CodeBuddy JSON 未通过结构校验（additionalProperties）。')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = AlwaysInvalidProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(project.project_id)

            with self.assertRaisesRegex(ProviderFailure, '自动纠正重试仍未通过结构校验'):
                await service.generate(state, '生成一个问题。', GrillReply)

            self.assertEqual(provider.calls, 2)
            self.assertEqual(service.get(project.project_id).model_calls, 2)

    async def test_schema_invalid_json_is_corrected_before_command_is_saved(self):
        class MissingFieldsProvider(FixtureProvider):
            async def generate(self, prompt, **kwargs):
                if self.calls == 0:
                    self.calls += 1
                    return SimpleNamespace(text='{}', provider='openai-compatible', model='fixture')
                self.correction = prompt
                return await super().generate(prompt, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = MissingFieldsProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(project.project_id)
            state.stage = 'grill'
            await service.apply(state, JourneyCommand(request_id='outline', expected_revision=0,
                operation='generate_outline'))
            self.assertEqual(state.outline.title, '烟测策划')
            self.assertEqual(provider.calls, 2)
            self.assertEqual(service.get(project.project_id).model_calls, 2)
            self.assertIn('JOURNEY_STRUCTURED_INVALID', provider.correction)
            self.assertIn('missing', provider.correction)

    async def test_schema_invalid_retries_stop_with_upstream_failure(self):
        class InvalidProvider(FixtureProvider):
            async def generate(self, prompt, **kwargs):
                self.calls += 1
                return SimpleNamespace(text='{}', provider='openai-compatible', model='fixture')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = InvalidProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            with self.assertRaises(ProviderFailure) as caught:
                await service.generate(service.get(project.project_id), '生成大纲。', Outline)
            self.assertEqual(caught.exception.code, 'JOURNEY_STRUCTURED_INVALID')
            self.assertEqual(caught.exception.status_code, 502)
            self.assertIn('自动纠正重试仍未通过结构校验', str(caught.exception))
            self.assertEqual(provider.calls, 2)
            self.assertEqual(service.get(project.project_id).model_calls, 2)
            self.assertIsNone(service.get(project.project_id).outline)

    async def test_domain_invalid_question_is_rejected_inside_retry(self):
        class InvalidRecommendationProvider(FixtureProvider):
            async def generate(self, prompt, **kwargs):
                result = await super().generate(prompt, **kwargs)
                value = json.loads(result.text)
                value['question']['recommended_index'] = 2
                result.text = json.dumps(value)
                return result

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = InvalidRecommendationProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            with self.assertRaisesRegex(ProviderFailure, '推荐项不存在'):
                await service.generate(service.get(project.project_id), '生成问题。', GrillReply)
            self.assertEqual(provider.calls, 2)

    async def test_transport_failure_is_not_retried(self):
        class OfflineProvider(FixtureProvider):
            async def generate(self, prompt, **kwargs):
                self.calls += 1
                raise ProviderFailure('OPENAI_NETWORK_ERROR', '无法连接服务。')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = OfflineProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            with self.assertRaises(ProviderFailure) as caught:
                await service.generate(service.get(project.project_id), '生成问题。', GrillReply)
            self.assertEqual(caught.exception.code, 'OPENAI_NETWORK_ERROR')
            self.assertEqual(provider.calls, 1)

    async def test_concise_alignment_stops_after_two_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root/'state.sqlite3', folders,
                                             FixtureProvider(alignment_detail='concise'))
            state = await service.command(project.project_id, JourneyCommand(
                request_id='idea', expected_revision=0, operation='message', text='探索游戏'))
            state = await service.command(project.project_id, JourneyCommand(
                request_id='grill', expected_revision=state.revision, operation='start_grill'))
            first = state.messages[-1]
            state = await service.command(project.project_id, JourneyCommand(
                request_id='answer-one', expected_revision=state.revision, operation='message',
                question_message_id=first.id, option_index=0))
            second = state.messages[-1]
            self.assertIsNotNone(second.question)
            state = await service.command(project.project_id, JourneyCommand(
                request_id='answer-two', expected_revision=state.revision, operation='message',
                question_message_id=second.id, option_index=1))
            self.assertIsNone(state.messages[-1].question)
            self.assertIn('完成对齐', state.messages[-1].text)
            self.assertEqual(sum(message.question is not None for message in state.messages), 2)

    async def test_invalid_legacy_card_does_not_persist_blocking_git_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root/'state.sqlite3', folders, FixtureProvider())
            state = service.get(project.project_id)
            state.stage = 'cards'
            state.outline = Outline(title='fixture', experience='探索', core_loop='走到出口', scope='场景', acceptance='出口')
            state.versions = [JourneyVersion(number=1, confirmed_at='2026-09-06T00:00:00Z', outline=state.outline)]
            state.cards = [ProductionCard(id='_legacy', title='旧卡片', description='旧数据', acceptance='检查')]
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)', (state.project_id, state.model_dump_json()))
            with self.assertRaises(HTTPException):
                await service.command(state.project_id, JourneyCommand(request_id='invalid-card', expected_revision=0, operation='select_card', card_id='_legacy'))
            with service.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM design_journey_exports').fetchone()[0], 0)
            saved = await service.command(state.project_id, JourneyCommand(request_id='after-failure', expected_revision=0, operation='save_draft', text='仍可编辑'))
            self.assertEqual(saved.composer_draft, '仍可编辑')

    async def test_one_question_options_and_real_delta_callback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root/'state.sqlite3', folders, FixtureProvider())
            events = []
            async def receive(event): events.append(event)
            state = await service.command(project.project_id, JourneyCommand(request_id='idea', expected_revision=0, operation='message', text='探索游戏'), on_event=receive)
            self.assertTrue(any(event['type'] == 'text_delta' for event in events))
            events.clear()
            state = await service.command(project.project_id, JourneyCommand(request_id='grill', expected_revision=state.revision, operation='start_grill'), on_event=receive)
            question = state.messages[-1]
            self.assertEqual(len(question.question.options), 2)
            self.assertFalse(any(event['type'] == 'text_delta' for event in events), 'Structured JSON must never leak as streamed prose')
            state = await service.command(project.project_id, JourneyCommand(request_id='answer', expected_revision=state.revision, operation='message', question_message_id=question.id, option_index=1))
            self.assertEqual(state.messages[-2].text, '战斗')
            self.assertEqual(state.messages[-2].reply_to, question.id)
            with self.assertRaises(HTTPException):
                await service.command(project.project_id, JourneyCommand(request_id='duplicate-answer', expected_revision=state.revision, operation='message', question_message_id=question.id, option_index=1))

    async def test_question_cannot_be_answered_after_its_step_has_ended(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(project.project_id)
            question = JourneyMessage(id='old-question', role='assistant', text='先确定属性。',
                created_at='2026-09-07T00:00:00Z', question=PlanningQuestion(
                    prompt='角色属性项怎么设计？', recommended_index=0,
                    options=[QuestionOption(label='少量可感属性', description='四到五项'),
                             QuestionOption(label='细分多属性', description='七项以上')]))
            state.messages = [question]
            state.stage = 'cards'
            with service.connection() as database:
                database.execute('INSERT OR REPLACE INTO design_journeys VALUES (?,?)',
                                 (project.project_id, state.model_dump_json()))
            with self.assertRaises(HTTPException) as caught:
                await service.command(project.project_id, JourneyCommand(request_id='stale-answer',
                    expected_revision=0, operation='message', question_message_id=question.id,
                    option_index=0))
            self.assertEqual(caught.exception.status_code, 409)
            self.assertIn('步骤已经结束', caught.exception.detail)
            self.assertEqual(provider.calls, 0)

    async def test_folder_to_v1_cards_and_reopen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(folder.project_id)
            async def act(operation, **values):
                nonlocal state
                command = JourneyCommand(request_id=f'request_{state.revision}', expected_revision=state.revision, operation=operation, **values)
                state = await service.command(folder.project_id, command)
                return command
            await act('save_draft', text='idea')
            self.assertEqual(provider.calls, 0)
            command = await act('message', text='做探索游戏')
            await service.command(folder.project_id, command)
            self.assertEqual(provider.calls, 1)
            await act('start_grill')
            await act('message', text='找到出口')
            await act('generate_outline')
            await act('confirm_version')
            snapshot = Path(folder.root_path)/'.sceneops/design/snapshots/v1.json'
            self.assertEqual(json.loads(snapshot.read_text())['number'], 1)
            await act('recommend_architecture')
            self.assertEqual(state.architecture_recommendation.code_architecture, 'ecs')
            await act('confirm_technical_plan', code_architecture='ecs', selection_method='ai')
            self.assertEqual(state.technical_plan.ecs_library, 'miniplex')
            game_root = Path(state.technical_plan.scaffold.root_path)
            self.assertTrue((game_root/'src/game/systems/movementSystem.ts').is_file())
            self.assertEqual(json.loads((game_root/'package.json').read_text())['dependencies']['miniplex'], '2.0.0')
            await act('generate_cards')
            self.assertEqual(state.cards[0].status, 'planned')
            await act('message', text='地图改成森林')
            self.assertEqual(state.cards[0].title, '3D 世界')
            proposal = state.changes[-1]
            await act('accept_change', change_id=proposal.id)
            self.assertEqual(state.cards[0].title, '森林地图')
            self.assertEqual(len(state.versions), 1)
            self.assertEqual(state.git_versions[0].tag, 'v1')
            await act('select_card', card_id='map')
            branch = state.card_branches[0]
            self.assertTrue(Path(branch.worktree_path).is_dir())
            self.assertEqual(branch.branch, 'codex/card-map')
            self.assertTrue((Path(branch.worktree_path)/'src/game/systems/movementSystem.ts').is_file())
            brief = json.loads((Path(branch.worktree_path)/'.sceneops/card-brief.json').read_text())
            self.assertEqual(brief['card']['technical_plan']['code_architecture'], 'ecs')
            await act('select_card', card_id='map')
            self.assertEqual(len(state.card_branches), 1)
            restored = PlanningJourneyService(root/'state.sqlite3', folders, provider).get(folder.project_id)
            self.assertEqual(restored, state)
            with self.assertRaises(HTTPException):
                await service.command(folder.project_id, JourneyCommand(request_id='stale', expected_revision=0, operation='confirm_version'))
            with self.assertRaises(ValueError):
                folders.create_design_snapshot(folder.project_id, {'changed': True}, 1)

    async def test_manual_object_component_project_and_legacy_state_are_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            service = PlanningJourneyService(root/'state.sqlite3', folders, FixtureProvider())
            state = service.get(folder.project_id)
            state.stage = 'stack'
            state.outline = Outline(title='收集游戏', experience='移动收集', core_loop='移动—收集—计分',
                scope='一个场景', acceptance='可以移动并得到三分')
            state.versions = [JourneyVersion(number=1, confirmed_at='2026-09-06T00:00:00Z', outline=state.outline)]
            folders.commit_design_version(folder.project_id, 1, state.versions[-1].model_dump(mode='json'))
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)', (folder.project_id, state.model_dump_json()))
            selected = await service.command(folder.project_id, JourneyCommand(request_id='architecture',
                expected_revision=0, operation='confirm_technical_plan',
                code_architecture='object-component', selection_method='manual'))
            project_root = Path(folder.root_path)
            self.assertTrue((project_root/'src/game/objects/Player.ts').is_file())
            self.assertFalse((project_root/'src/game/systems/movementSystem.ts').exists())
            self.assertNotIn('miniplex', json.loads((project_root/'package.json').read_text())['dependencies'])
            restored = PlanningJourneyService(root/'state.sqlite3', folders, FixtureProvider()).get(folder.project_id)
            self.assertEqual(restored.technical_plan, selected.technical_plan)

            legacy = restored.model_dump(mode='json', exclude={'technical_plan','architecture_recommendation'})
            legacy['stage'] = 'cards'
            legacy['stack'] = 'threejs'
            with service.connection() as db:
                db.execute('UPDATE design_journeys SET payload=? WHERE project_id=?',
                    (json.dumps(legacy, ensure_ascii=False), folder.project_id))
            before = (project_root/'src/game/objects/Player.ts').read_text()
            reopened = service.get(folder.project_id)
            self.assertIsNone(reopened.technical_plan)
            self.assertEqual((project_root/'src/game/objects/Player.ts').read_text(), before)

    async def test_existing_project_requires_adoption_before_opening_a_new_card(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            folder = folders.create_folder_project(root, 'existing-game')
            project_root = Path(folder.root_path)
            source = project_root/'src/main.ts'
            source.parent.mkdir(parents=True)
            source.write_text('export const existingGame = true;\n')
            package = project_root/'package.json'
            package.write_text('{"scripts":{"check":"custom"}}\n')
            (project_root/'.env').write_text('PRIVATE_FIXTURE=1\n')
            dependencies = project_root/'node_modules/example'
            dependencies.mkdir(parents=True)
            (dependencies/'index.js').write_text('ignored\n')
            selection = {'target_platform':'web', 'engine':'threejs',
                'code_architecture':'object-component', 'architecture_label':'对象／组件式',
                'selection_method':'manual', 'rationale':'沿用已有对象代码。',
                'tradeoffs':['继续整理对象依赖'], 'ecs_library':None}
            folders.commit_design_version(folder.project_id, 1, {'title':'existing'})
            scaffold = folders.initialize_game_project(folder.project_id, selection, 1)
            self.assertEqual(scaffold['initialization_status'], 'existing')
            self.assertEqual(scaffold['project_kind'], 'existing_unadopted')
            self.assertIsNone(scaffold['baseline_commit'])
            self.assertEqual(source.read_text(), 'export const existingGame = true;\n')
            plan = {**selection, 'selected_at':'2026-09-06T00:00:00Z', 'scaffold':scaffold}
            with self.assertRaisesRegex(GitProjectError, '采用流程'):
                folders.open_card_worktree(folder.project_id, 'continue', '继续开发',
                    card={'technical_plan':plan})
            self.assertFalse((root/'card-worktrees').exists())
            self.assertEqual(package.read_text(), '{"scripts":{"check":"custom"}}\n')
            self.assertEqual(source.read_text(), 'export const existingGame = true;\n')

    async def test_interrupted_snapshot_export_reconciles_without_new_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            folder = folders.create_folder_project(root, 'project')
            provider = FixtureProvider()
            service = PlanningJourneyService(root/'state.sqlite3', folders, provider)
            state = service.get(folder.project_id)
            state.stage = 'outline'
            state.outline = Outline(title='fixture', experience='探索', core_loop='移动', scope='一个场景', acceptance='出口')
            with service.connection() as db:
                db.execute('INSERT INTO design_journeys VALUES (?,?)', (folder.project_id, state.model_dump_json()))
            command = JourneyCommand(request_id='confirm', expected_revision=0, operation='confirm_version')
            write = folders.write_design_draft
            def fail(*args): raise OSError('injected draft write failure')
            folders.write_design_draft = fail
            with self.assertRaises(OSError): await service.command(folder.project_id, command)
            folders.write_design_draft = write
            recovered = await service.command(folder.project_id, command)
            self.assertEqual(len(recovered.versions), 1)
            self.assertEqual(provider.calls, 0)

    async def test_two_service_instances_cannot_commit_same_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folders = SqliteWorkspaceRepository(root/'state.sqlite3')
            project = folders.create_folder_project(root, 'project')
            arrived, release = asyncio.Event(), asyncio.Event()
            class WaitingProvider(FixtureProvider):
                async def generate(self, *args, **kwargs):
                    arrived.set()
                    await release.wait()
                    return await super().generate(*args, **kwargs)
            first = PlanningJourneyService(root/'state.sqlite3', folders, WaitingProvider())
            second = PlanningJourneyService(root/'state.sqlite3', folders, FixtureProvider())
            pending = asyncio.create_task(first.command(project.project_id, JourneyCommand(request_id='first', expected_revision=0, operation='message', text='original')))
            await arrived.wait()
            await second.command(project.project_id, JourneyCommand(request_id='second', expected_revision=0, operation='save_draft', text='newer'))
            release.set()
            with self.assertRaises(HTTPException): await pending
            self.assertEqual(second.get(project.project_id).composer_draft, 'newer')
