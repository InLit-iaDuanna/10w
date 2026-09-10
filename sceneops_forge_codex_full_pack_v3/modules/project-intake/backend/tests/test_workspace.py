"""Regression coverage maintained but not executed during integration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import sqlite3
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sceneops_project_workspace import (ModuleDocument, SqliteWorkspaceRepository,
    create_folder_router)
from sceneops_project_workspace.git_projects import GitProjectError, GitProjects
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
            identity = json.loads((Path(project.root_path) / ".sceneops" / "project.json").read_text())
            self.assertEqual(set(identity), {"schema_version", "project_id", "name", "created_at"})
            self.assertNotIn(str(parent), json.dumps(identity))
            repository.write_design_draft(project.project_id, fixture["draft"])
            self.assertEqual(repository.read_design_draft(project.project_id), fixture["draft"])
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
            inspection = client.post("/api/workspace/folder-projects/inspect", json={
                "path": created.json()["root_path"],
            })
            self.assertEqual(inspection.status_code, 200)
            self.assertEqual(inspection.json()["status"], "registered")
            self.assertEqual(client.post("/api/workspace/folder-projects/inspect", json={
                "path": str(existing),
            }).json()["status"], "missing_identity")
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            conflict = client.post("/api/workspace/folder-projects", json={
                "parent_path": str(parent), "name": "existing",
            })
            self.assertEqual(conflict.status_code, 409)

    def test_forget_folder_project_preserves_source_and_can_be_restored(self):
        fixture = self.fixture()
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            app = FastAPI()
            app.include_router(create_folder_router(repository))
            client = TestClient(app)
            project = repository.create_folder_project(parent, fixture["name"])
            root = Path(project.root_path)
            draft = repository.write_design_draft(project.project_id, fixture["draft"])

            response = client.delete(f"/api/workspace/folder-projects/{project.project_id}")

            self.assertEqual(response.status_code, 204)
            self.assertEqual(repository.list_folder_projects(), [])
            self.assertTrue(root.is_dir())
            self.assertTrue((root / ".git").is_dir())
            self.assertTrue((root / ".sceneops" / "project.json").is_file())
            self.assertTrue(Path(draft.path).is_file())
            inspection = repository.inspect_folder_project(root)
            self.assertEqual(inspection.status, "recoverable")
            restored = client.post("/api/workspace/folder-projects/recover", json={
                "path": str(root), "resolution": "restore",
            })
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["project_id"], project.project_id)

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

    def test_git_initialization_failure_never_returns_a_registered_project(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            app = FastAPI()
            app.include_router(create_folder_router(repository))
            client = TestClient(app)
            with patch.object(GitProjects, "initialize_root", side_effect=GitProjectError("fixture failure")):
                response = client.post("/api/workspace/folder-projects", json={
                    "parent_path": str(parent), "name": "interrupted",
                })
            self.assertEqual(response.status_code, 409)
            self.assertEqual(repository.list_folder_projects(), [])
            root = parent / "interrupted"
            self.assertTrue((root / ".sceneops" / "project.json").is_file())
            inspection = repository.inspect_folder_project(root)
            self.assertEqual(inspection.status, "recoverable")
            restored = client.post("/api/workspace/folder-projects/recover", json={
                "path": str(root), "resolution": "restore",
            })
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["project_id"], inspection.project_id)

    def test_database_registration_failure_leaves_a_recoverable_identity(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            with patch.object(repository, "_register_folder_project",
                              side_effect=sqlite3.OperationalError("fixture failure")):
                with self.assertRaises(sqlite3.OperationalError):
                    repository.create_folder_project(parent, "recoverable")
            root = parent / "recoverable"
            inspection = repository.inspect_folder_project(root)
            self.assertEqual(inspection.status, "recoverable")
            restored = repository.recover_folder_project(root, "restore")
            self.assertEqual(restored.project_id, inspection.project_id)
            self.assertEqual(restored.project_kind, "sceneops_created")

    def test_moved_project_keeps_identity_and_copy_requires_a_new_identity(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            original = repository.create_folder_project(parent, "original")
            original_root = Path(original.root_path)
            moved_root = parent / "moved"
            shutil.move(original_root, moved_root)
            unavailable = next(item for item in repository.list_folder_projects()
                               if item.project_id == original.project_id)
            self.assertFalse(unavailable.root_available)
            moved = repository.inspect_folder_project(moved_root)
            self.assertEqual(moved.status, "move_candidate")
            self.assertEqual(set(moved.allowed_resolutions), {"move", "copy"})
            rebound = repository.recover_folder_project(moved_root, "move")
            self.assertEqual(rebound.project_id, original.project_id)
            self.assertEqual(rebound.root_path, str(moved_root))

            copied_root = parent / "copied"
            shutil.copytree(moved_root, copied_root)
            duplicate = repository.inspect_folder_project(copied_root)
            self.assertEqual(duplicate.status, "identity_conflict")
            self.assertEqual(duplicate.allowed_resolutions, ["copy"])
            copied = repository.recover_folder_project(copied_root, "copy")
            self.assertNotEqual(copied.project_id, original.project_id)
            self.assertEqual(copied.project_kind, "existing_unadopted")
            identity = json.loads((copied_root / ".sceneops" / "project.json").read_text())
            self.assertEqual(identity["copied_from_project_id"], original.project_id)

    def test_moved_project_repairs_existing_card_worktree(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(parent / "data" / "sceneops.sqlite3")
            project = repository.create_folder_project(parent, "original")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            repository.initialize_game_project(project.project_id, {
                "target_platform": "web",
                "engine": "threejs",
                "code_architecture": "object-component",
                "architecture_label": "对象／组件式",
                "selection_method": "manual",
                "rationale": "移动恢复夹具",
                "tradeoffs": ["测试"],
                "ecs_library": None,
            }, 1)
            before = repository.open_card_worktree(project.project_id, "world-3d", "3D 世界")
            moved_root = parent / "moved"
            shutil.move(project.root_path, moved_root)

            recovered = repository.recover_folder_project(moved_root, "move")
            after = repository.get_card_worktree(project.project_id, "world-3d")

            self.assertEqual(recovered.root_path, str(moved_root))
            self.assertEqual(after["worktree_path"], before["worktree_path"])
            self.assertEqual(after["branch"], "codex/card-world-3d")

    def test_legacy_registered_project_without_identity_remains_readable(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            database = parent / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(parent, "legacy")
            (Path(project.root_path) / ".sceneops" / "project.json").unlink()
            with repository.connect() as connection:
                connection.execute("UPDATE workspace_folder_projects SET project_kind='legacy' WHERE project_id=?",
                                   (project.project_id,))
            reopened = SqliteWorkspaceRepository(database)
            self.assertEqual(reopened.get_folder_project(project.project_id).project_kind, "legacy")
            self.assertEqual(reopened.inspect_folder_project(project.root_path).status, "missing_identity")
