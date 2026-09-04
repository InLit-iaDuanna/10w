"""Regression coverage maintained but not executed during integration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sceneops_project_workspace import ModuleDocument, SqliteWorkspaceRepository
from sceneops_project_workspace.repository import RevisionConflict


class WorkspaceRepositoryTests(unittest.TestCase):
    def test_empty_and_explicit_persistence(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            self.assertEqual(repository.list_projects(), [])
            project = repository.create_project("人工创建的项目")
            initial = repository.get_document(project.project_id, "world-logic")
            self.assertEqual(initial.revision, 0)
            saved = repository.save_document(initial.model_copy(update={"payload": {"notes": "草稿"}}), 0)
            reopened = SqliteWorkspaceRepository(database)
            self.assertEqual(reopened.get_document(project.project_id, "world-logic"), saved)

    def test_project_isolation_and_revision_conflict(self):
        with TemporaryDirectory() as directory:
            repository = SqliteWorkspaceRepository(Path(directory) / "sceneops.sqlite3")
            first, second = repository.create_project("项目 A"), repository.create_project("项目 B")
            draft = ModuleDocument(project_id=first.project_id, module_id="character-animation", revision=0, payload={"notes": "A"})
            repository.save_document(draft, 0)
            self.assertEqual(repository.get_document(second.project_id, "character-animation").payload, {})
            with self.assertRaises(RevisionConflict):
                repository.save_document(draft, 0)
            with self.assertRaises(KeyError):
                repository.get_document("unknown", "character-animation")
