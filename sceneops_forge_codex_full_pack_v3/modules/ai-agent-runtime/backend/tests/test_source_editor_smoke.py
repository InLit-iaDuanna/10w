"""One isolated registered-worktree edit path and its write boundary; no model/build."""
import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from pydantic import ValidationError
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_harness import HarnessError
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask, AgentAction
from sceneops_ai_agents.source_editor import source_index, source_file, save_source, SaveCardSource
from sceneops_ai_agents.context_projection import task_context_summary


class SourceEditorSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_card_source_save_and_scoped_agent_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            data = root / 'data'
            repository = SqliteWorkspaceRepository(data / 'state.sqlite3')
            project = repository.create_folder_project(root, 'game')
            repository.commit_design_version(project.project_id, 1, {'title':'fixture'})
            plan = {'target_platform':'web', 'engine':'threejs', 'code_architecture':'ecs',
                'architecture_label':'ECS · Miniplex', 'selection_method':'manual',
                'rationale':'fixture', 'tradeoffs':[], 'ecs_library':'miniplex'}
            repository.initialize_game_project(project.project_id, plan, 1)
            branch = repository.open_card_worktree(project.project_id, 'input', '输入', card={'title':'输入','technical_plan':plan})
            provider = SimpleNamespace(database_path=data/'state.sqlite3',
                settings=lambda:SimpleNamespace(provider='codebuddycli', model='fixture'),
                generate=AsyncMock(side_effect=AssertionError('No model call')))
            service = AgentTaskService(data/'state.sqlite3', repository, data, provider=provider,
                card_context=lambda *_:{'card':{'title':'输入'}, 'technical_plan':plan})
            try:
                path = 'src/game/systems/inputSystem.ts'
                other = 'src/main.ts'
                callback = service.card_context
                service.card_context = lambda *_: (_ for _ in ()).throw(AssertionError('Browsing must not require execution alignment'))
                index = source_index(service, project.project_id, 'input')
                service.card_context = callback
                self.assertEqual(index.architecture, 'ECS · Miniplex')
                self.assertIn(path, [item.path for item in index.files if item.section=='src/game/systems'])
                before = source_file(service, project.project_id, 'input', path).content
                edited = before + '\n// manual change\n'
                saved = await save_source(service, project.project_id, 'input',
                    SaveCardSource(path=path, expected_content=before, content=edited))
                self.assertEqual(saved.status, 'review_required', saved.reason)
                self.assertEqual(saved.grant.source_write_paths, [path])
                self.assertEqual(source_file(service, project.project_id, 'input', path).content, edited)
                with self.assertRaises(HarnessError):
                    await save_source(service, project.project_id, 'input',
                        SaveCardSource(path=path, expected_content=before, content='outdated'))
                with self.assertRaises(ValidationError):
                    PrepareAgentTask(project_id=project.project_id, card_id='input', task_profile='card-development',
                        execution_mode='agent-full-access', goal='invalid', source_write_paths=[path])
                request = PrepareAgentTask(project_id=project.project_id, card_id='input',
                    task_profile='card-development', goal='selected file only', source_write_paths=[path])
                task = service.prepare(request)
                outside = source_file(service, project.project_id, 'input', other).content
                service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                    accept_unknown_cost=True), actions=[AgentAction(action_id='outside',
                    capability_id='code.file.write', rationale='outside selected scope',
                    inputs={'path':other, 'expected_content':outside, 'content':'must not write'})])
                await asyncio.gather(*list(service.jobs.values()))
                refused = service.get(task.id)
                self.assertNotEqual(refused.actions[0].state, 'succeeded')
                self.assertEqual(source_file(service, project.project_id, 'input', other).content, outside)
                self.assertEqual(task_context_summary(refused)['source_write_paths'], [path])
                self.assertEqual(service.code.rows(task.id), [])
                # The same persisted allowlist permits the selected file through the actual writer.
                task = service.prepare(request)
                service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                    accept_unknown_cost=True), actions=[
                    AgentAction(action_id='inside', capability_id='code.file.write', rationale='selected edit',
                        inputs={'path':path,'expected_content':edited,'content':edited+'// scoped change\n'}),
                    AgentAction(action_id='finish',capability_id='agent.finish',rationale='read back',inputs={'summary':'done'})])
                await asyncio.gather(*list(service.jobs.values()))
                self.assertEqual(service.get(task.id).status, 'review_required', service.get(task.id).reason)
                self.assertEqual(service.get(task.id).grant.source_write_paths,[path])
                self.assertEqual((Path(branch['worktree_path'])/path).read_text(),edited+'// scoped change\n')
                provider.generate.assert_not_awaited()
            finally:
                await service.close()
