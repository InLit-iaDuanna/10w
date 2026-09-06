from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Optional

from pydantic import Field, field_validator

from .base import CommitId, ExecutionMode, FrozenModel, StableId, VersionReference, require_utc


RelativePath = Annotated[str, Field(min_length=1, max_length=4096)]


def validate_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or normalized.startswith("./"):
        raise ValueError("path must be a normalized project-relative path")
    return normalized


class GitChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNTRACKED = "untracked"
    CONFLICT = "conflict"


class GitFileChange(FrozenModel):
    path: RelativePath
    kind: GitChangeKind
    old_path: Optional[RelativePath] = None
    additions: Optional[int] = Field(default=None, ge=0)
    deletions: Optional[int] = Field(default=None, ge=0)
    binary: bool = False

    _validate_path = field_validator("path")(validate_relative_path)
    _validate_old_path = field_validator("old_path")(lambda value: validate_relative_path(value) if value else value)


class LfsPointer(FrozenModel):
    path: RelativePath
    object_id: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    size: int = Field(ge=0)
    algorithm: str = Field(default="sha256", pattern=r"^sha256$")
    pointer_version: str = Field(default="https://git-lfs.github.com/spec/v1")
    object_available: Optional[bool] = None
    lock_required: bool = False
    active_lock_id: Optional[StableId] = None

    _validate_path = field_validator("path")(validate_relative_path)


class LfsLockResult(FrozenModel):
    external_lock_id: str = Field(min_length=1, max_length=320)
    path: RelativePath
    owner_name: str = Field(min_length=1, max_length=320)
    locked_at: datetime
    mode: ExecutionMode

    _validate_path = field_validator("path")(validate_relative_path)
    _utc = field_validator("locked_at")(require_utc)


class LfsUnlockResult(FrozenModel):
    external_lock_id: str = Field(min_length=1, max_length=320)
    path: RelativePath
    mode: ExecutionMode

    _validate_path = field_validator("path")(validate_relative_path)


class GitBranch(FrozenModel):
    name: str = Field(min_length=1, max_length=255)
    commit_id: CommitId
    current: bool = False


class GitCommit(FrozenModel):
    parent_ids: tuple[CommitId, ...] = ()
    commit_id: CommitId
    author: str = Field(min_length=1, max_length=320)
    authored_at: datetime
    subject: str = Field(min_length=1, max_length=1024)

    _utc = field_validator("authored_at")(require_utc)


class GitCapabilities(FrozenModel):
    adapter_id: str
    adapter_version: str
    git_version: str
    lfs_cli_available: bool
    operations: tuple[str, ...]
    mode: ExecutionMode


class IntegrationHealth(FrozenModel):
    integration_id: str
    connected: bool
    mode: ExecutionMode
    checked_at: datetime
    reason: Optional[str] = None

    _utc = field_validator("checked_at")(require_utc)


class GitRepositoryState(FrozenModel):
    project_id: StableId
    version: VersionReference
    dirty: bool
    conflicted: bool
    changes: tuple[GitFileChange, ...]
    lfs_pointers: tuple[LfsPointer, ...]
    branches: tuple[GitBranch, ...]
    commits: tuple[GitCommit, ...]
    mode: ExecutionMode
    captured_at: datetime

    _utc = field_validator("captured_at")(require_utc)


class GitVersionDiff(FrozenModel):
    base: VersionReference
    target: VersionReference
    changes: tuple[GitFileChange, ...]
    lfs_pointers: tuple[LfsPointer, ...]
    mode: ExecutionMode


class GitProgress(FrozenModel):
    operation: str
    stage: str
    state: str = Field(pattern=r"^(started|completed|failed|cancelled)$")


class GitRollbackCommand(FrozenModel):
    operation_id: StableId
    proposal_id: StableId
    approval_id: StableId
    expected_head: CommitId
    target_commit: CommitId
    commit_message: str = Field(min_length=1, max_length=240)


class RollbackPreview(FrozenModel):
    current_head: CommitId
    target_commit: CommitId
    changes: tuple[GitFileChange, ...]
    blocked_reasons: tuple[str, ...]
    mode: ExecutionMode


class GitRollbackResult(FrozenModel):
    operation_id: StableId
    previous_head: CommitId
    resulting_head: CommitId
    changed_paths: tuple[RelativePath, ...]
    approval_id: StableId
    mode: ExecutionMode
