"""Project native preparation and authorization without model or game execution."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import AsyncMock, patch

from sceneops_ai_agents import AuthorizeAgentTask
from sceneops_harness import HarnessError
import test_project_demo_task as project_fixture


class ProjectNativeAuthorizationSmoke(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = project_fixture.ProjectDemoTaskSmoke.asyncSetUp
    asyncTearDown = project_fixture.ProjectDemoTaskSmoke.asyncTearDown

    def request(self, mode='agent-full-access'):
        return project_fixture.ProjectDemoTaskSmoke.request(self).model_copy(update={
            'task_profile': 'project-demo-agent', 'execution_mode': mode})

    async def test_prepare_authorize_registered_project_and_new_followup(self):
        request = type(self.request()).model_validate(self.request().model_dump())
        task = self.service.prepare(request)
        typed = self.service.prepare(self.request('typed-tools'))
        followup = self.service.prepare(request.model_copy(update={'goal': '追加一个跳跃动作'}))
        self.assertIn('_native_', task.id)
        self.assertEqual(len({task.id, typed.id, followup.id}), 3)
        self.assertIsNone(task.authorization_card.card_id)
        self.assertEqual(task.authorization_card.capability_ids,
                         ['agent.task.execute'])
        self.assertEqual(self.provider.generate.await_count, 0)
        with self.assertRaisesRegex(HarnessError, '明确确认风险'):
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        with patch.object(self.service, '_run', new=AsyncMock()):
            authorized = self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id,
                accept_unknown_cost=True, accept_full_access=True))
            await asyncio.gather(*list(self.service.jobs.values()))
        self.assertEqual(authorized.grant.workspace_root,
                         self.workspace.open_project_demo_workspace(self.project.project_id)['workspace_root'])
        checked = self.service.check_grant(task.id, 'agent.task.execute')
        self.assertEqual(checked.grant.execution_mode, 'agent-full-access')
        self.assertEqual(checked.grant.budget.max_metered_calls, 2)
        from sceneops_ai_agents.native_project_delivery import deliver_native_project
        async def game_result(current, operation):
            return {'run': {'id': 'fixture_' + operation, 'operation': operation, 'passed': True}}
        with patch.object(self.service.game, 'execute', new=AsyncMock(side_effect=game_result)) as execute:
            await deliver_native_project(self.service, task.id)
        self.assertEqual([call.args[1] for call in execute.await_args_list],
                         ['prepare', 'check', 'build', 'preview_start'])
        self.assertEqual(self.service.get(task.id).observations['game_project']['run']['operation'],
                         'preview_start')

    async def test_changed_grant_is_denied(self):
        task = self.service.prepare(self.request())
        with patch.object(self.service, '_run', new=AsyncMock()):
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id,
                accept_unknown_cost=True, accept_full_access=True))
            await asyncio.gather(*list(self.service.jobs.values()))
        def change(current):
            current.grant.workspace_id = 'demo_ws_wrong'
        self.service.records.update(task.id, change, 'test.scope_changed')
        with self.assertRaises(HarnessError) as caught:
            self.service.check_grant(task.id, 'agent.task.execute')
        self.assertEqual(caught.exception.code, 'TASK_SCOPE_DENIED')

    def test_selected_asset_evidence_ignores_catalog_and_detects_source_reference(self):
        with tempfile.TemporaryDirectory(prefix='sceneops-asset-usage-') as directory:
            root = Path(directory)
            asset_root = root / 'public/sceneops-assets/sceneops-haven-kit/v5'
            asset_root.mkdir(parents=True)
            catalog_path = asset_root / 'catalog.selected.json'
            catalog_path.write_text(json.dumps({'entries': [{
                'source_asset_id': 'cottage', 'url': '/sceneops-assets/sceneops-haven-kit/v5/cottage.glb'}
            ]}), encoding='utf-8')
            task = SimpleNamespace(observations={'selected_builtin_assets': {
                'catalog_path': catalog_path.relative_to(root).as_posix(),
                'catalog': {'entries': [{'source_asset_id': 'cottage',
                    'url': '/sceneops-assets/sceneops-haven-kit/v5/cottage.glb'}]}}})
            service = object.__new__(project_fixture.AgentTaskService)
            service.get = Mock(return_value=task)
            service.records = Mock()
            service.records.update.side_effect = lambda _id, change, *_args: change(task)

            absent = service.inspect_prepared_asset_usage('task', root)
            absent_adjustments = list(task.observations['production_preparation_adjustments'])
            (root / 'src').mkdir()
            (root / 'src/game.ts').write_text(
                "load('/sceneops-assets/sceneops-haven-kit/v5/cottage.glb')", encoding='utf-8')
            present = service.inspect_prepared_asset_usage('task', root)

            self.assertEqual(absent[0]['actual_reference'], 'not_observed')
            self.assertEqual(absent_adjustments[0]['state'],
                             'selected_reference_not_observed')
            self.assertEqual(present[0]['actual_reference'], 'referenced')
            self.assertEqual(present[0]['reference_paths'], ['src/game.ts'])
            self.assertEqual(task.observations['production_preparation_adjustments'], [])

    async def test_preparation_is_reused_within_request_and_new_goal_gets_new_selection(self):
        class Preparation:
            def __init__(self):
                self.calls = []
            async def prepare(self, request):
                self.calls.append(request)
                return SimpleNamespace(status='succeeded', preparation_id='prep-' + request.request_key,
                    call=SimpleNamespace(status='succeeded', usage={'total_tokens': 2}, cost_usd=None),
                    model_dump=lambda **_kwargs: {'status': 'succeeded', 'recommendation': {
                        'assets': [], 'experiences': [], 'skills': []},
                        'call': {'status': 'succeeded', 'usage': {'total_tokens': 2}}})
            async def selected_context(self, request, result, *, record_memory=True):
                return {'status': 'succeeded', 'selected_details': []}

        preparation = Preparation()
        task = SimpleNamespace(id='task-native', project_id='project', goal='首版',
            observations={'demo_goals': [{'request_id': 'initial', 'goal': '首版'}]},
            authorization_card=SimpleNamespace(task_profile='project-demo-agent',
                                               capability_ids=['agent.task.execute']),
            grant=SimpleNamespace(include_demo_assets=True, expires_at=None, workspace_id='workspace',
                                  execution_mode='agent-full-access',
                                  budget=SimpleNamespace(max_metered_calls=4)),
            model_calls_used=0, model_tokens_known=0, budget_accounting_complete=True,
            cost_usd=None)
        service = object.__new__(project_fixture.AgentTaskService)
        service.production_preparation = preparation
        service.builtin_project_install_selected = Mock()
        service.project_asset_install_selected = Mock()
        service.get = Mock(side_effect=lambda _id: task)
        service.records = Mock()
        service.records.update.side_effect = lambda _id, change, *_args: (change(task), task)[1]

        await service.ensure_production_preparation(task.id)
        await service.ensure_production_preparation(task.id)
        task.goal = '增加敌人'
        task.observations['demo_goals'].append({'request_id': 'followup-1', 'goal': task.goal})
        task.observations.pop('production_preparation')
        task.observations.pop('production_preparation_context')
        await service.ensure_production_preparation(task.id)

        self.assertEqual(len(preparation.calls), 2)
        self.assertNotEqual(preparation.calls[0].request_key, preparation.calls[1].request_key)
        self.assertIn('code.demo_assets.install', preparation.calls[0].available_capability_ids)
        self.assertEqual(task.model_calls_used, 2)

    async def test_selected_asset_provision_failure_is_recorded_without_stopping_task(self):
        task = SimpleNamespace(
            id='task-native', project_id='project',
            authorization_card=SimpleNamespace(task_profile='project-demo-agent'),
            grant=SimpleNamespace(include_demo_assets=True),
            observations={'production_preparation': {'recommendation': {'assets': [{
                'candidate_id': 'builtin:sceneops-haven-kit-cottage',
                'version': 'sceneops-haven-kit:5', 'purpose': '出生点',
            }]}}},
        )
        service = object.__new__(project_fixture.AgentTaskService)
        service.get = Mock(return_value=task)
        service.builtin_project_install_selected = Mock(
            side_effect=RuntimeError('fixture copy failure'))
        service.project_asset_install_selected = None
        service.records = Mock()
        service.records.update.side_effect = lambda _id, change, *_args: (change(task), task)[1]

        report = await service.install_prepared_project_assets(task.id)

        self.assertEqual(report['materialization'][0]['state'], 'not_provided')
        self.assertEqual(report['provision_failures'][0]['candidate_id'],
                         'builtin:sceneops-haven-kit-cottage')
        self.assertEqual(task.observations['production_preparation']['materialization'],
                         report['materialization'])

    async def test_card_game_provides_selected_project_asset_to_card_workspace(self):
        task = SimpleNamespace(
            id='task-card', project_id='project',
            authorization_card=SimpleNamespace(task_profile='card-development'),
            grant=SimpleNamespace(include_demo_assets=True, card_id='world-3d'),
            observations={'production_preparation': {'recommendation': {'assets': [{
                'candidate_id': 'project:libasset-tree', 'version': '3',
                'purpose': '地标', 'reason': '项目已有',
            }]}}},
        )
        provided = {'catalog': {'entries': [{'project_asset_id': 'libasset-tree',
            'url': '/sceneops-project-assets/libasset-tree/v3/model.glb'}]},
            'materialization': [{'candidate_id': 'project:libasset-tree',
                'provision_state': 'provided', 'copy_state': 'copied'}],
            'installed_files': ['public/sceneops-project-assets/libasset-tree/v3/model.glb'],
            'preserved_files': [], 'catalog_path': None}
        service = object.__new__(project_fixture.AgentTaskService)
        service.get = Mock(return_value=task)
        service.builtin_project_install_selected = None
        service.project_asset_install_selected = Mock(return_value=provided)
        service.records = Mock()
        service.records.update.side_effect = lambda _id, change, *_args: (change(task), task)[1]

        report = await service.install_prepared_project_assets(task.id)

        service.project_asset_install_selected.assert_called_once_with(
            'project', [{'project_asset_id': 'libasset-tree', 'version': '3',
                         'purpose': '地标', 'reason': '项目已有'}], 'world-3d')
        self.assertEqual(report['entries'][0]['project_asset_id'], 'libasset-tree')
