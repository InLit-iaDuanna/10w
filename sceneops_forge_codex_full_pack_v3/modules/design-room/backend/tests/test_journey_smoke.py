"""One isolated planning path and boundary checks, with a labelled provider fixture."""
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
from sceneops_ai_provider import ProviderFailure
from sceneops_project_workspace import GitProjectError, SqliteWorkspaceRepository
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import (JourneyCommand, Outline, JourneyVersion,
    ProductionCard, GrillReply)


class FixtureProvider:
    def __init__(self, alignment_detail='standard'):
        self.calls = 0
        self.alignment_detail = alignment_detail
    def settings(self):
        return SimpleNamespace(model='fixture', provider='codebuddycli',
                               alignment_detail=self.alignment_detail)
    async def generate(self, prompt, **kwargs):
        self.calls += 1
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
        elif schema and schema['title'] == 'CompactCardProposal':
            text = json.dumps({'cards': [
                {'id':'world-3d', 'title':'3D 世界', 'description':'场景与资产', 'dependencies':[], 'acceptance':'世界可见', 'status':'planned'},
                {'id':'core-gameplay', 'title':'核心玩法', 'description':'移动与交互', 'dependencies':['world-3d'], 'acceptance':'玩法可运行', 'status':'planned'},
                {'id':'growth-feedback', 'title':'成长与反馈', 'description':'界面与反馈', 'dependencies':['core-gameplay'], 'acceptance':'反馈清晰', 'status':'planned'},
                {'id':'demo-delivery', 'title':'完成 Demo', 'description':'整合与交付', 'dependencies':['growth-feedback'], 'acceptance':'可以交付', 'status':'planned'},
            ]})
        elif schema:
            text = json.dumps({'cards': [{'id':'map', 'title':'地图', 'description':'基础空间', 'dependencies':[], 'acceptance':'存在出口', 'status':'planned'}]})
        else: text = '你希望玩家最主要的目标是什么？建议先确定探索目标。'
        if kwargs.get('on_event'):
            await kwargs['on_event']({'type': 'text_delta', 'text': text})
        return SimpleNamespace(text=text, provider='codebuddycli', model='fixture')


class JourneySmoke(unittest.IsolatedAsyncioTestCase):
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
