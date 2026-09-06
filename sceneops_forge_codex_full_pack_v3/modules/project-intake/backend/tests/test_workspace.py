"""Regression coverage maintained but not executed during integration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sceneops_project_workspace import (ModuleDocument, SqliteWorkspaceRepository,
    create_folder_router)
from sceneops_project_workspace.repository import (FolderProjectConflict,
    RevisionConflict)


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


class FolderProjectSmokeTests(unittest.TestCase):
    @staticmethod
    def fixture():
        path = Path(__file__).parent / "fixtures" / "folder_project.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_folder_project_persists_and_design_snapshot_is_immutable(self):
        fixture = self.fixture()
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            database = parent / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(parent, fixture["name"])
            repository.write_design_draft(project.project_id, fixture["draft"])
            first = repository.create_design_snapshot(
                project.project_id, fixture["draft"], fixture["snapshot_version"])
            retried = repository.create_design_snapshot(
                project.project_id, fixture["draft"], fixture["snapshot_version"])

            reopened = SqliteWorkspaceRepository(database)
            self.assertEqual(reopened.get_folder_project(project.project_id), project)
            self.assertEqual(first, retried)
            with self.assertRaises(FolderProjectConflict):
                reopened.create_design_snapshot(project.project_id, {"changed": True}, 1)

    def test_folder_router_browses_and_reopens_without_touching_existing_directory(self):
        fixture = self.fixture()
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            existing = parent / "existing"
            existing.mkdir()
            marker = existing / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            app = FastAPI()
            app.include_router(create_folder_router(repository))
            client = TestClient(app)

            listing = client.get("/api/workspace/folders", params={"path": str(parent)})
            self.assertEqual(listing.status_code, 200)
            self.assertIn("existing", [entry["name"] for entry in listing.json()["entries"]])
            created = client.post("/api/workspace/folder-projects", json={
                "parent_path": str(parent), "name": fixture["name"],
            })
            self.assertEqual(created.status_code, 201)
            project_id = created.json()["project_id"]
            self.assertEqual(client.get(f"/api/workspace/folder-projects/{project_id}").status_code, 200)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            conflict = client.post("/api/workspace/folder-projects", json={
                "parent_path": str(parent), "name": "existing",
            })
            self.assertEqual(conflict.status_code, 409)

    def test_symlink_directory_is_visible_but_never_selectable(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            real = parent / "real"
            real.mkdir()
            link = parent / "linked"
            link.symlink_to(real, target_is_directory=True)
            repository = SqliteWorkspaceRepository(parent / "sceneops.sqlite3")

            listing = repository.list_directory(parent)
            linked = next(entry for entry in listing.entries if entry.name == "linked")
            self.assertEqual(linked.kind, "symlink")
            self.assertFalse(linked.selectable)
