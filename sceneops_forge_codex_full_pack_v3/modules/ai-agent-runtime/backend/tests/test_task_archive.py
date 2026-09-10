from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase
from sceneops_ai_agents.task_models import AgentTaskRecord, AuthorizationCard
from sceneops_ai_agents.task_repository import AgentTaskRepository
from sceneops_harness import HarnessError

class TaskArchiveTests(TestCase):
    def test_persistent_archive_restore_preserves_execution_and_project_scope(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'tasks.sqlite'
            repo = AgentTaskRepository(path)
            task = repo.create(AgentTaskRecord(project_id='project-a', goal='Archive fixture', status='failed',
                authorization_card=AuthorizationCard(workspace_root=directory)))
            repo.create(AgentTaskRecord(project_id='project-b', goal='Other project',
                authorization_card=AuthorizationCard(workspace_root=directory)))
            original = task.model_dump(exclude={'archived'})
            self.assertTrue(repo.archive(task.id, True).archived)
            repo = AgentTaskRepository(path)
            self.assertEqual(repo.list('project-a', False), [])
            self.assertEqual([item.id for item in repo.list('project-a', True)], [task.id])
            self.assertEqual(repo.list('project-b', True), [])
            self.assertEqual(repo.get(task.id).model_dump(exclude={'archived'}), original)
            repo.update(task.id, lambda item: setattr(item, 'reason', 'reviewed'), 'test.reviewed')
            self.assertTrue(repo.get(task.id).archived)
            repo.archive(task.id, False)
            self.assertFalse(repo.get(task.id).archived)
            self.assertEqual(len(repo.list('project-a', False)), 1)

    def test_active_execution_cannot_be_archived(self):
        with TemporaryDirectory() as directory:
            repo = AgentTaskRepository(Path(directory) / 'tasks.sqlite')
            for status, owner in [('queued', None), ('running', None), ('cancel_pending', None), ('blocked', 123)]:
                task = repo.create(AgentTaskRecord(project_id='project', goal='Running fixture', status=status, owner_pid=owner,
                    authorization_card=AuthorizationCard(workspace_root=directory)))
                with self.assertRaises(HarnessError): repo.archive(task.id, True)
                self.assertFalse(repo.get(task.id).archived)
