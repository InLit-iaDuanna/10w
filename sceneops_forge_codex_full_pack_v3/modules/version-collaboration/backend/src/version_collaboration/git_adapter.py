from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Iterable

from .base import Clock, ExecutionMode, UtcClock
from .errors import ErrorCode, VersionCollaborationError
from .git_models import (
    GitCapabilities,
    GitRepositoryState,
    GitRollbackCommand,
    GitRollbackResult,
    GitVersionDiff,
    IntegrationHealth,
    LfsLockResult,
    LfsUnlockResult,
    RollbackPreview,
    validate_relative_path,
)
from .git_reader import GitRepositoryReader, parse_lfs_pointer
from .git_rollback import GitRollbackExecutor
from .git_runner import GitCommandRunner


class GitCliAdapter:
    adapter_id = "git.cli"
    adapter_version = "0.1.0"

    def __init__(
        self,
        allowed_project_roots: Iterable[Path],
        *,
        runner: GitCommandRunner | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._allowed_roots = tuple(path.resolve() for path in allowed_project_roots)
        self._runner = runner or GitCommandRunner()
        self._clock = clock or UtcClock()
        self._reader = GitRepositoryReader(self._runner, self._clock)
        self._rollback = GitRollbackExecutor(self._runner, self._reader)

    def health_check(self, project_root: Path) -> IntegrationHealth:
        checked_at = self._clock.now()
        try:
            root = self._validate_root(project_root)
            result = self._runner.run(
                "health_check", ("rev-parse", "--is-inside-work-tree"), cwd=root
            )
            connected = result.stdout.strip() == "true"
            return IntegrationHealth(
                integration_id="git",
                connected=connected,
                mode=(ExecutionMode.LIVE if connected else ExecutionMode.BLOCKED),
                checked_at=checked_at,
                reason=(
                    None
                    if connected
                    else "The configured path is not a Git worktree."
                ),
            )
        except VersionCollaborationError as error:
            if error.code == ErrorCode.PATH_OUTSIDE_PROJECT:
                raise
            return IntegrationHealth(
                integration_id="git",
                connected=False,
                mode=ExecutionMode.BLOCKED,
                checked_at=checked_at,
                reason=error.message,
            )

    def capabilities(self, project_root: Path) -> GitCapabilities:
        root = self._validate_root(project_root)
        version = self._runner.run(
            "git_version", ("--version",), cwd=root
        ).stdout.strip()
        lfs = self._runner.run(
            "git_lfs_version",
            ("lfs", "version"),
            cwd=root,
            allowed_return_codes=(0, 1, 128, 129),
        )
        has_lfs = lfs.return_code == 0
        operations = [
            "inspect",
            "compare",
            "rollback.dry_run",
            "rollback.execute",
        ]
        if has_lfs:
            operations.extend(
                ("lfs.lock.inspect", "lfs.lock.acquire", "lfs.lock.release")
            )
        return GitCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            git_version=version,
            lfs_cli_available=has_lfs,
            operations=tuple(operations),
            mode=ExecutionMode.LIVE,
        )

    def inspect(
        self, project_id: str, repository_id: str, project_root: Path
    ) -> GitRepositoryState:
        root = self._require_repository(project_root)
        return self._reader.inspect(project_id, repository_id, root)

    def compare_versions(
        self,
        repository_id: str,
        project_root: Path,
        base_commit: str,
        target_commit: str,
    ) -> GitVersionDiff:
        root = self._require_repository(project_root)
        return self._reader.compare_versions(
            repository_id, root, base_commit, target_commit
        )

    def dry_run_rollback(
        self, project_root: Path, command: GitRollbackCommand
    ) -> RollbackPreview:
        root = self._require_repository(project_root)
        state = self._reader.inspect(
            "project_preview", "repository_preview", root
        )
        target = self._reader.resolve_commit(root, command.target_commit)
        changes = self._reader.committed_changes(
            root, state.version.commit_id, target
        )
        reasons: list[str] = []
        if state.version.commit_id != command.expected_head:
            reasons.append("stale_base")
        if state.dirty:
            reasons.append("dirty_worktree")
        if state.conflicted:
            reasons.append("merge_conflict")
        return RollbackPreview(
            current_head=state.version.commit_id,
            target_commit=target,
            changes=changes,
            blocked_reasons=tuple(reasons),
            mode=ExecutionMode.BLOCKED if reasons else ExecutionMode.LIVE,
        )

    def acquire_lfs_lock(
        self, project_root: Path, path: str, operation_id: str
    ) -> LfsLockResult:
        root = self._require_lfs(project_root)
        safe_path = validate_relative_path(path)
        output = self._runner.run(
            "lfs_lock_acquire",
            ("lfs", "lock", "--json", safe_path),
            cwd=root,
            mutation=True,
        )
        return self._parse_lfs_lock(output.stdout, operation_id)

    def inspect_lfs_lock(
        self, project_root: Path, path: str
    ) -> LfsLockResult | None:
        root = self._require_lfs(project_root)
        safe_path = validate_relative_path(path)
        output = self._runner.run(
            "lfs_lock_inspect",
            ("lfs", "locks", "--json", f"--path={safe_path}"),
            cwd=root,
        )
        try:
            payload = json.loads(output.stdout)
            locks = payload if isinstance(payload, list) else payload["locks"]
            if not isinstance(locks, list) or not all(
                isinstance(item, dict) for item in locks
            ):
                raise TypeError("locks payload is not an array of objects")
            matches = [item for item in locks if item.get("path") == safe_path]
            if len(matches) > 1:
                raise ValueError("multiple locks returned for one path")
            return (
                self._lfs_lock_from_payload(matches[0]) if matches else None
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise VersionCollaborationError(
                ErrorCode.INCOMPATIBLE_SCHEMA,
                "Git LFS returned an incompatible lock-list response.",
                details={"path": safe_path},
            ) from error

    def release_lfs_lock(
        self,
        project_root: Path,
        external_lock_id: str,
        expected_path: str,
        operation_id: str,
    ) -> LfsUnlockResult:
        root = self._require_lfs(project_root)
        safe_path = validate_relative_path(expected_path)
        if not external_lock_id or external_lock_id.startswith("-"):
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "LFS lock identity is invalid.",
                details={"operation_id": operation_id},
            )
        output = self._runner.run(
            "lfs_lock_release",
            ("lfs", "unlock", "--json", "--id", external_lock_id),
            cwd=root,
            mutation=True,
        )
        try:
            payload = json.loads(output.stdout)
            if not isinstance(payload, list) or len(payload) != 1:
                raise TypeError("unlock payload is not a single-result array")
            result = payload[0]
            if not isinstance(result, dict) or result.get("unlocked") is not True:
                raise TypeError("unlock result did not confirm success")
            actual_id = result.get("id")
            actual_path = result.get("path") or safe_path
            if actual_id != external_lock_id or actual_path != safe_path:
                raise ValueError("unlock result identity does not match the request")
            return LfsUnlockResult(
                external_lock_id=str(actual_id),
                path=str(actual_path),
                mode=ExecutionMode.LIVE,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise VersionCollaborationError(
                ErrorCode.INCOMPATIBLE_SCHEMA,
                "Git LFS returned an incompatible unlock response.",
                details={"operation_id": operation_id},
            ) from error

    def execute_rollback(
        self,
        project_root: Path,
        command: GitRollbackCommand,
        *,
        cancellation: Event | None = None,
    ) -> GitRollbackResult:
        root = self._require_repository(project_root)
        command = self._rollback.normalize(root, command)
        existing = self._rollback.find_completed(root, command)
        if existing is not None:
            return existing
        preview = self.dry_run_rollback(root, command)
        if preview.blocked_reasons:
            code = (
                ErrorCode.STALE_BASE
                if "stale_base" in preview.blocked_reasons
                else ErrorCode.GIT_DIRTY
            )
            raise VersionCollaborationError(
                code,
                "Rollback execution no longer matches its approved dry-run.",
                details={"blocked_reasons": list(preview.blocked_reasons)},
                suggested_actions=(
                    "review.rollback.propose",
                    "version.status.refresh",
                ),
            )
        if not preview.changes:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "Rollback target already matches the current tracked content.",
                details={"target_commit": preview.target_commit},
                suggested_actions=("version.status.refresh",),
            )
        return self._rollback.execute_new(
            root,
            command,
            preview,
            cancellation=cancellation,
        )

    def _validate_root(self, project_root: Path) -> Path:
        root = project_root.resolve()
        if root not in self._allowed_roots:
            raise VersionCollaborationError(
                ErrorCode.PATH_OUTSIDE_PROJECT,
                "Project path is outside the adapter allowlist.",
                details={"project_root": str(root)},
            )
        return root

    def _require_repository(self, project_root: Path) -> Path:
        root = self._validate_root(project_root)
        result = self._runner.run(
            "repository_check",
            ("rev-parse", "--is-inside-work-tree"),
            cwd=root,
            allowed_return_codes=(0, 128),
        )
        if result.return_code != 0 or result.stdout.strip() != "true":
            raise VersionCollaborationError(
                ErrorCode.GIT_OFFLINE,
                "The configured project is not an available Git worktree.",
                suggested_actions=("integration.open",),
            )
        return root

    def _require_lfs(self, project_root: Path) -> Path:
        root = self._require_repository(project_root)
        if not self.capabilities(root).lfs_cli_available:
            raise VersionCollaborationError(
                ErrorCode.GIT_OFFLINE,
                "Git LFS locking is unavailable; binary collaboration remains blocked.",
                suggested_actions=("integration.open",),
            )
        return root

    @staticmethod
    def _parse_lfs_lock(output: str, operation_id: str) -> LfsLockResult:
        try:
            payload = json.loads(output)
            lock = payload.get("lock", payload)
            return GitCliAdapter._lfs_lock_from_payload(lock)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise VersionCollaborationError(
                ErrorCode.INCOMPATIBLE_SCHEMA,
                "Git LFS returned an incompatible lock response.",
                details={"operation_id": operation_id},
            ) from error

    @staticmethod
    def _lfs_lock_from_payload(lock: object) -> LfsLockResult:
        if not isinstance(lock, dict):
            raise TypeError("lock payload is not an object")
        external_lock_id = lock.get("id")
        path = lock.get("path")
        timestamp = lock.get("locked_at")
        if not isinstance(external_lock_id, str) or not external_lock_id:
            raise TypeError("lock identity is missing")
        if not isinstance(path, str) or not path:
            raise TypeError("lock path is missing")
        if not isinstance(timestamp, str) or not timestamp:
            raise TypeError("lock timestamp is missing")
        owner = lock.get("owner", {})
        if not isinstance(owner, dict):
            raise TypeError("lock owner is not an object")
        locked_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if locked_at.tzinfo is None or locked_at.utcoffset() is None:
            raise ValueError("lock timestamp is not timezone-aware")
        return LfsLockResult(
            external_lock_id=external_lock_id,
            path=path,
            owner_name=(owner.get("name") or owner.get("login") or "unknown"),
            locked_at=locked_at.astimezone(timezone.utc),
            mode=ExecutionMode.LIVE,
        )

__all__ = ["GitCliAdapter", "parse_lfs_pointer"]
