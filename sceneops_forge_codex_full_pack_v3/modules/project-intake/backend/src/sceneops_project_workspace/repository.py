"""SQLite repository for explicit local project and workbench draft saves."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4
from pydantic import JsonValue
from .git_projects import GitProjects
from .game_projects import GameProjects

from .models import (FolderEntry, FolderListing, FolderProject, ModuleDocument,
    ModuleId, Project, SampleId, StructuredDesignArtifact)


class RevisionConflict(ValueError):
    pass


class InvalidFolderPath(ValueError):
    pass


class FolderProjectConflict(ValueError):
    pass


class WorkspaceRepository(Protocol):
    def list_projects(self) -> list[Project]: ...
    def get_project(self, project_id: str) -> Project: ...
    def create_project(self, name: str) -> Project: ...
    def get_document(self, project_id: str, module_id: ModuleId) -> ModuleDocument: ...
    def save_document(self, document: ModuleDocument, expected_revision: int) -> ModuleDocument: ...
    def list_directory(self, path: str | Path | None = None) -> FolderListing: ...
    def create_folder_project(self, parent_path: str | Path, name: str) -> FolderProject: ...
    def list_folder_projects(self) -> list[FolderProject]: ...
    def get_folder_project(self, project_id: str) -> FolderProject: ...
    def write_design_draft(self, project_id: str,
        payload: dict[str, JsonValue]) -> StructuredDesignArtifact: ...
    def create_design_snapshot(self, project_id: str, payload: dict[str, JsonValue],
        version: int) -> StructuredDesignArtifact: ...
    def ensure_project_git(self, project_id: str) -> dict: ...
    def commit_design_version(self, project_id: str, version: int, payload: dict) -> dict: ...
    def open_card_worktree(self, project_id: str, card_id: str, title: str, card: dict | None = None) -> dict: ...
    def get_card_worktree(self, project_id: str, card_id: str) -> dict: ...
    def initialize_game_project(self, project_id: str, selection: dict) -> dict: ...


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
                CREATE TABLE IF NOT EXISTS workspace_folder_projects (
                    project_id TEXT PRIMARY KEY REFERENCES workspace_projects(project_id),
                    root_path TEXT NOT NULL UNIQUE,
                    bound_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_card_worktrees (
                    project_id TEXT NOT NULL, card_id TEXT NOT NULL,
                    branch TEXT NOT NULL, worktree_path TEXT NOT NULL UNIQUE,
                    base_commit TEXT NOT NULL,
                    PRIMARY KEY (project_id, card_id));
                CREATE TABLE IF NOT EXISTS workspace_git_versions (
                    project_id TEXT NOT NULL, version INTEGER NOT NULL,
                    commit_id TEXT NOT NULL, index_synced INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (project_id, version));
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(workspace_git_versions)")}
            if "index_synced" not in columns:
                connection.execute("ALTER TABLE workspace_git_versions ADD COLUMN index_synced INTEGER NOT NULL DEFAULT 0")

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

    def list_directory(self, path=None):
        directory = self._safe_existing_directory(Path.home() if path is None else Path(path))
        entries = []
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name.casefold())
        except PermissionError as error:
            raise InvalidFolderPath("没有权限读取此目录。") from error
        for child in children:
            try:
                if child.is_symlink():
                    entries.append(FolderEntry(name=child.name, path=str(child), kind="symlink", selectable=False))
                elif child.is_dir():
                    entries.append(FolderEntry(name=child.name, path=str(child), kind="directory", selectable=True))
            except OSError:
                continue
        parent = directory.parent if directory.parent != directory else None
        return FolderListing(path=str(directory), parent_path=str(parent) if parent else None, entries=entries)

    def create_folder_project(self, parent_path, name):
        parent = self._safe_existing_directory(Path(parent_path))
        clean_name = name.strip()
        if clean_name in {".", ".."} or Path(clean_name).name != clean_name or "\x00" in clean_name:
            raise InvalidFolderPath("项目名称必须是单个目录名称。")
        root = parent / clean_name
        try:
            root.mkdir(mode=0o700)
        except FileExistsError as error:
            raise FolderProjectConflict("目标目录已存在；请选择其他名称以保留原内容。") from error
        except OSError as error:
            raise InvalidFolderPath("无法在所选目录中创建项目。") from error

        now = datetime.now(timezone.utc)
        project = Project(project_id="prj_" + uuid4().hex, name=clean_name, created_at=now, updated_at=now)
        try:
            with self.connect() as connection:
                connection.execute("INSERT INTO workspace_projects VALUES (?, ?, ?, ?)",
                    (project.project_id, project.name, now.isoformat(), now.isoformat()))
                connection.execute("INSERT INTO workspace_folder_projects VALUES (?, ?, ?)",
                    (project.project_id, str(root), now.isoformat()))
        except Exception:
            try:
                root.rmdir()
            except OSError:
                pass
            raise
        self.ensure_project_git(project.project_id)
        return FolderProject(project_id=project.project_id, name=project.name, root_path=str(root))

    def ensure_project_git(self, project_id):
        return GitProjects(self).ensure(project_id)

    def commit_design_version(self, project_id, version, payload):
        return GitProjects(self).commit_version(project_id, version, payload)

    def open_card_worktree(self, project_id, card_id, title, card=None):
        result = GitProjects(self).open_card(project_id, card_id, title, card)
        GameProjects(self).materialize_card(project_id, Path(result["worktree_path"]),
                                            (card or {}).get("technical_plan"))
        return result

    def get_card_worktree(self, project_id, card_id):
        return GitProjects(self).get_card(project_id, card_id)

    def initialize_game_project(self, project_id, selection):
        return GameProjects(self).initialize(project_id, selection)

    def list_folder_projects(self):
        with self.connect() as connection:
            rows = connection.execute("""SELECT p.project_id, p.name, f.root_path
                FROM workspace_folder_projects f JOIN workspace_projects p USING (project_id)
                ORDER BY p.created_at, p.project_id""").fetchall()
        return [FolderProject.model_validate(dict(row)) for row in rows]

    def get_folder_project(self, project_id):
        with self.connect() as connection:
            row = connection.execute("""SELECT p.project_id, p.name, f.root_path
                FROM workspace_folder_projects f JOIN workspace_projects p USING (project_id)
                WHERE p.project_id=?""", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        project = FolderProject.model_validate(dict(row))
        self._safe_existing_directory(Path(project.root_path))
        return project

    def write_design_draft(self, project_id, payload):
        design = self._design_directory(project_id)
        target = design / "draft.json"
        temporary = design / (".draft-" + uuid4().hex + ".tmp")
        try:
            self._write_json_exclusive(temporary, payload)
            os.replace(temporary, target)
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()
        return StructuredDesignArtifact(project_id=project_id, kind="draft", path=str(target))

    def create_design_snapshot(self, project_id, payload, version):
        if version < 1:
            raise ValueError("设计快照版本必须大于零。")
        snapshots = self._real_directory(self._design_directory(project_id) / "snapshots", create=True)
        target = snapshots / f"v{version}.json"
        try:
            self._write_json_exclusive(target, payload)
        except FileExistsError:
            if target.is_symlink() or not target.is_file():
                raise InvalidFolderPath("设计快照路径不安全。")
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise FolderProjectConflict("此版本快照已存在且无法核对。") from error
            if existing != payload:
                raise FolderProjectConflict("此版本快照已存在，不能覆盖。")
        return StructuredDesignArtifact(project_id=project_id, kind="snapshot", version=version, path=str(target))

    @staticmethod
    def _safe_existing_directory(path):
        if not path.is_absolute():
            raise InvalidFolderPath("目录路径必须是绝对路径。")
        if ".." in path.parts:
            raise InvalidFolderPath("目录路径不能包含上级跳转。")
        current = Path(path.anchor)
        try:
            for part in path.parts[1:]:
                current = current / part
                if current.is_symlink():
                    raise InvalidFolderPath("不允许通过符号链接访问目录。")
            if not current.is_dir():
                raise InvalidFolderPath("目录不存在或不是文件夹。")
        except OSError as error:
            raise InvalidFolderPath("无法访问此目录。") from error
        return current

    @staticmethod
    def _real_directory(path, create=False):
        try:
            if create:
                path.mkdir(mode=0o700)
            if path.is_symlink() or not path.is_dir():
                raise InvalidFolderPath("项目存储目录不安全。")
        except FileExistsError:
            if path.is_symlink() or not path.is_dir():
                raise InvalidFolderPath("项目存储目录不安全。")
        return path

    def _design_directory(self, project_id):
        root = self._safe_existing_directory(Path(self.get_folder_project(project_id).root_path))
        metadata = self._real_directory(root / ".sceneops", create=True)
        return self._real_directory(metadata / "design", create=True)

    @staticmethod
    def _write_json_exclusive(path, payload):
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8") + b"\n"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
