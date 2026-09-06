"""One real Git worktree path, deterministic actions, no model or code execution."""
import asyncio
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask, AgentAction


class CardGitWriteSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_registered_git_worktree_receives_code_without_commit_or_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            data = root/'data'
            repository = SqliteWorkspaceRepository(data/'state.sqlite3')
            project = repository.create_folder_project(root, 'game')
            version = repository.commit_design_version(project.project_id, 1, {'title':'fixture'})
            branch = repository.open_card_worktree(project.project_id, 'map', '地图', card={'title':'地图'})
            provider = SimpleNamespace(database_path=data/'state.sqlite3',
                settings=lambda: SimpleNamespace(provider='codebuddycli', model='fixture'),
                generate=AsyncMock(side_effect=AssertionError('No real model call')))
            service = AgentTaskService(data/'state.sqlite3', repository, data, provider=provider,
                card_context=lambda project_id, card_id: {'card':{'title':'最新地图草稿'},'notice':'fixture'})
            try:
                task = service.prepare(PrepareAgentTask(project_id=project.project_id, card_id='map',
                    task_profile='card-development', goal='创建源码，不运行'))
                self.assertEqual(task.observations['card_context']['card']['title'], '最新地图草稿')
                source = Path(branch['worktree_path'])/'main.ts'
                self.assertFalse(source.exists())
                service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
                    accept_unknown_cost=True), actions=[
                    AgentAction(action_id='write', capability_id='code.file.write', rationale='fixture',
                        inputs={'path':'main.ts','expected_content':None,'content':'export const speed = 2;\n'}),
                    AgentAction(action_id='finish', capability_id='agent.finish', rationale='fixture', inputs={'summary':'待检查'}),
                ])
                await asyncio.gather(*list(service.jobs.values()))
                result = service.get(task.id)
                self.assertEqual(result.status, 'review_required', result.reason)
                self.assertEqual(source.read_text(), 'export const speed = 2;\n')
                head = subprocess.check_output(['git','-C',branch['worktree_path'],'rev-parse','HEAD'], text=True).strip()
                self.assertEqual(head, version['commit'])
                self.assertFalse((Path(project.root_path)/'main.ts').exists())
                self.assertFalse(result.observations['code']['compilation_verified'])
                provider.generate.assert_not_awaited()
            finally: await service.close()
