"""SQLite repository for explicit local project and workbench draft saves."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .models import ModuleDocument, ModuleId, Project, SampleId


class RevisionConflict(ValueError):
    pass


class WorkspaceRepository(Protocol):
    def list_projects(self) -> list[Project]: ...
    def get_project(self, project_id: str) -> Project: ...
    def create_project(self, name: str) -> Project: ...
    def get_document(self, project_id: str, module_id: ModuleId) -> ModuleDocument: ...
    def save_document(self, document: ModuleDocument, expected_revision: int) -> ModuleDocument: ...


class SqliteWorkspaceRepository:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS workspace_projects (
                    project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_module_drafts (
                    project_id TEXT NOT NULL REFERENCES workspace_projects(project_id),
                    module_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    sample_id TEXT, payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, module_id));
            """)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def list_projects(self):
        with self.connect() as connection:
            return [Project.model_validate(dict(row)) for row in connection.execute(
                "SELECT * FROM workspace_projects ORDER BY created_at, project_id")]

    def exists(self, project_id: str) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM workspace_projects WHERE project_id=?",
                (project_id,)).fetchone() is not None

    def get_project(self, project_id: str):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM workspace_projects WHERE project_id=?",
                (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return Project.model_validate(dict(row))

    def create_project(self, name: str):
        now = datetime.now(timezone.utc)
        project = Project(project_id="prj_" + uuid4().hex, name=name.strip(), created_at=now, updated_at=now)
        with self.connect() as connection:
            connection.execute("INSERT INTO workspace_projects VALUES (?, ?, ?, ?)",
                (project.project_id, project.name, now.isoformat(), now.isoformat()))
        return project

    def get_document(self, project_id: str, module_id: ModuleId):
        self.get_project(project_id)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM workspace_module_drafts WHERE project_id=? AND module_id=?",
                (project_id, module_id)).fetchone()
        if row is None:
            return ModuleDocument(project_id=project_id, module_id=module_id, revision=0)
        return ModuleDocument(**{**dict(row), "payload": json.loads(row["payload"])})

    def save_document(self, document: ModuleDocument, expected_revision: int):
        self.get_project(document.project_id)
        saved = document.model_copy(update={"revision": expected_revision + 1})
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision FROM workspace_module_drafts WHERE project_id=? AND module_id=?",
                (document.project_id, document.module_id)).fetchone()
            if (row["revision"] if row else 0) != expected_revision:
                raise RevisionConflict("草稿已在另一窗口修改，请重新加载后再保存。")
            connection.execute("""INSERT INTO workspace_module_drafts VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id,module_id) DO UPDATE SET revision=excluded.revision,
                sample_id=excluded.sample_id,payload=excluded.payload""",
                (saved.project_id, saved.module_id, saved.revision, saved.sample_id,
                 json.dumps(saved.payload, ensure_ascii=False, allow_nan=False)))
            connection.execute("UPDATE workspace_projects SET updated_at=? WHERE project_id=?",
                (datetime.now(timezone.utc).isoformat(), document.project_id))
        return saved
