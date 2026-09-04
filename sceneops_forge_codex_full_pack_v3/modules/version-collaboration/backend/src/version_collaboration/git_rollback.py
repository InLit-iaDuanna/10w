from __future__ import annotations

import os
from pathlib import Path
from threading import Event

from .base import ExecutionMode
from .errors import ErrorCode, VersionCollaborationError
from .git_models import (
    GitRollbackCommand,
    GitRollbackResult,
    RollbackPreview,
)
from .git_reader import GitRepositoryReader
from .git_runner import GitCommandRunner


_COMMIT_HOOKS = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
)


class GitRollbackExecutor:
    """Creates a forward rollback commit with an atomic expected-HEAD update."""

    def __init__(
        self, runner: GitCommandRunner, reader: GitRepositoryReader
    ) -> None:
        self._runner = runner
        self._reader = reader

    def normalize(
        self, root: Path, command: GitRollbackCommand
    ) -> GitRollbackCommand:
        return command.model_copy(
            update={
                "expected_head": self._reader.resolve_commit(
                    root, command.expected_head
                ),
                "target_commit": self._reader.resolve_commit(
                    root, command.target_commit
                ),
            }
        )

    def find_completed(
        self, root: Path, command: GitRollbackCommand
    ) -> GitRollbackResult | None:
        actual_head = self._reader.resolve_commit(root, "HEAD")
        marker = f"SceneOps-Operation: {command.operation_id}"
        output = self._runner.run(
            "rollback_idempotency_check",
            (
                "log",
                "--all",
                "--fixed-strings",
                f"--grep={marker}",
                "--format=%H%x1f%B%x1e",
            ),
            cwd=root,
        ).stdout
        matches: list[GitRollbackResult] = []
        collisions: list[str] = []
        for record in output.split("\x1e"):
            if "\x1f" not in record:
                continue
            commit_id, message = record.split("\x1f", 1)
            commit_id = commit_id.strip()
            trailers = self._trailers(message)
            if trailers.get("SceneOps-Operation") != command.operation_id:
                continue
            if not self._matches(root, commit_id, command, trailers):
                collisions.append(commit_id)
                continue
            matches.append(
                GitRollbackResult(
                    operation_id=command.operation_id,
                    previous_head=command.expected_head,
                    resulting_head=commit_id,
                    changed_paths=tuple(
                        change.path
                        for change in self._reader.committed_changes(
                            root, command.expected_head, commit_id
                        )
                    ),
                    approval_id=command.approval_id,
                    mode=ExecutionMode.LIVE,
                )
            )
        if collisions or len(matches) > 1:
            raise VersionCollaborationError(
                ErrorCode.DUPLICATE_RECORD,
                "A Git commit reuses this rollback operation identity with different immutable content.",
                details={
                    "operation_id": command.operation_id,
                    "collision_commits": collisions,
                    "matching_commits": [item.resulting_head for item in matches],
                },
            )
        if not matches:
            return None
        completed = matches[0]
        if completed.resulting_head != actual_head:
            raise VersionCollaborationError(
                ErrorCode.DUPLICATE_RECORD,
                "This rollback operation exists on another ref but is not the current HEAD.",
                details={
                    "operation_id": command.operation_id,
                    "operation_commit": completed.resulting_head,
                    "current_head": actual_head,
                },
            )
        if self._reader.working_changes(root):
            raise VersionCollaborationError(
                ErrorCode.GIT_DIRTY,
                "The rollback commit is current but its index/worktree synchronization is incomplete or has changed.",
                details={"operation_id": command.operation_id},
                suggested_actions=("version.status.refresh",),
            )
        return completed

    def execute_new(
        self,
        root: Path,
        command: GitRollbackCommand,
        preview: RollbackPreview,
        *,
        cancellation: Event | None,
    ) -> GitRollbackResult:
        self._require_supported_commit_policy(root)
        self._require_unchanged_base(root, command.expected_head)
        target_tree = self._tree_id(root, command.target_commit)
        message = self._commit_message(command)
        created = self._runner.run(
            "rollback_commit_create",
            (
                "commit-tree",
                target_tree,
                "-p",
                command.expected_head,
                "-m",
                message,
            ),
            cwd=root,
            cancellation=cancellation,
            mutation=True,
        ).stdout.strip()
        self._require_unchanged_base(root, command.expected_head)
        try:
            update = self._runner.run(
                "rollback_ref_compare_and_swap",
                (
                    "update-ref",
                    "-m",
                    f"SceneOps approved rollback {command.proposal_id}",
                    "HEAD",
                    created,
                    command.expected_head,
                ),
                cwd=root,
                allowed_return_codes=(0, 128),
                cancellation=cancellation,
                mutation=True,
            )
        except VersionCollaborationError:
            if self._reader.resolve_commit(root, "HEAD") == created:
                self._restore_ref(root, command.expected_head, created)
            raise
        if update.return_code != 0:
            raise VersionCollaborationError(
                ErrorCode.STALE_BASE,
                "Git HEAD changed at the atomic rollback boundary.",
                details={"expected_commit": command.expected_head},
                suggested_actions=(
                    "review.rollback.propose",
                    "version.status.refresh",
                ),
            )
        if self._workspace_changed_from(root, command.expected_head):
            self._restore_ref(root, command.expected_head, created)
            raise VersionCollaborationError(
                ErrorCode.GIT_DIRTY,
                "The worktree changed while the approved rollback was committing.",
                suggested_actions=("version.status.refresh",),
            )
        self._require_created_head(root, created)
        try:
            self._runner.run(
                "rollback_worktree_sync",
                (
                    "restore",
                    f"--source={created}",
                    "--staged",
                    "--worktree",
                    "--",
                    ".",
                ),
                cwd=root,
                cancellation=cancellation,
                mutation=True,
            )
        except VersionCollaborationError:
            self._restore_ref(root, command.expected_head, created)
            self._runner.run(
                "rollback_worktree_compensate",
                (
                    "restore",
                    f"--source={command.expected_head}",
                    "--staged",
                    "--worktree",
                    "--",
                    ".",
                ),
                cwd=root,
                mutation=True,
            )
            raise
        self._require_completed_postcondition(root, created, command.operation_id)
        return GitRollbackResult(
            operation_id=command.operation_id,
            previous_head=command.expected_head,
            resulting_head=created,
            changed_paths=tuple(change.path for change in preview.changes),
            approval_id=command.approval_id,
            mode=ExecutionMode.LIVE,
        )

    def _require_created_head(self, root: Path, created: str) -> None:
        actual = self._reader.resolve_commit(root, "HEAD")
        if actual != created:
            raise VersionCollaborationError(
                ErrorCode.GIT_CONFLICT,
                "Git HEAD advanced after the rollback compare-and-swap; worktree synchronization was not attempted.",
                details={"rollback_commit": created, "actual_head": actual},
                suggested_actions=("version.status.refresh",),
            )

    def _require_completed_postcondition(
        self, root: Path, created: str, operation_id: str
    ) -> None:
        actual = self._reader.resolve_commit(root, "HEAD")
        if actual != created:
            raise VersionCollaborationError(
                ErrorCode.GIT_CONFLICT,
                "Git HEAD changed while the rollback worktree was synchronizing.",
                details={
                    "operation_id": operation_id,
                    "rollback_commit": created,
                    "actual_head": actual,
                },
                suggested_actions=("version.status.refresh",),
            )
        if self._reader.working_changes(root):
            raise VersionCollaborationError(
                ErrorCode.GIT_DIRTY,
                "Rollback postcondition failed because the index or worktree is not clean at the resulting commit.",
                details={"operation_id": operation_id},
                suggested_actions=("version.status.refresh",),
            )

    def _matches(
        self,
        root: Path,
        commit_id: str,
        command: GitRollbackCommand,
        trailers: dict[str, str],
    ) -> bool:
        expected = {
            "SceneOps-Operation": command.operation_id,
            "SceneOps-Proposal": command.proposal_id,
            "SceneOps-Approval": command.approval_id,
            "SceneOps-Expected-Head": command.expected_head,
            "SceneOps-Target": command.target_commit,
        }
        if any(trailers.get(key) != value for key, value in expected.items()):
            return False
        try:
            parent = self._reader.resolve_commit(root, f"{commit_id}^")
            return (
                parent == command.expected_head
                and self._tree_id(root, commit_id)
                == self._tree_id(root, command.target_commit)
            )
        except VersionCollaborationError:
            return False

    def _require_unchanged_base(self, root: Path, expected_head: str) -> None:
        actual = self._reader.resolve_commit(root, "HEAD")
        if actual != expected_head:
            raise VersionCollaborationError(
                ErrorCode.STALE_BASE,
                "Git HEAD changed after rollback approval.",
                details={
                    "expected_commit": expected_head,
                    "actual_commit": actual,
                },
                suggested_actions=(
                    "review.rollback.propose",
                    "version.status.refresh",
                ),
            )
        if self._reader.working_changes(root):
            raise VersionCollaborationError(
                ErrorCode.GIT_DIRTY,
                "The worktree changed after rollback approval.",
                suggested_actions=("version.status.refresh",),
            )

    def _workspace_changed_from(self, root: Path, revision: str) -> bool:
        checks = (
            ("diff", "--quiet", revision, "--"),
            ("diff", "--cached", "--quiet", revision, "--"),
        )
        if any(
            self._runner.run(
                "rollback_workspace_compare",
                args,
                cwd=root,
                allowed_return_codes=(0, 1),
            ).return_code
            != 0
            for args in checks
        ):
            return True
        untracked = self._runner.run(
            "rollback_untracked_check",
            ("ls-files", "--others", "--exclude-standard"),
            cwd=root,
        ).stdout
        return bool(untracked.strip())

    def _restore_ref(self, root: Path, previous: str, created: str) -> None:
        result = self._runner.run(
            "rollback_ref_compensate",
            ("update-ref", "HEAD", previous, created),
            cwd=root,
            allowed_return_codes=(0, 128),
            mutation=True,
        )
        if result.return_code != 0:
            raise VersionCollaborationError(
                ErrorCode.GIT_CONFLICT,
                "Rollback compensation could not restore the branch ref because it changed again.",
                details={"created_commit": created, "previous_commit": previous},
                suggested_actions=("version.status.refresh",),
            )

    def _require_supported_commit_policy(self, root: Path) -> None:
        signing = self._runner.run(
            "rollback_signing_policy",
            ("config", "--bool", "--get", "commit.gpgSign"),
            cwd=root,
            allowed_return_codes=(0, 1),
        )
        if signing.return_code == 0 and signing.stdout.strip() == "true":
            self._raise_commit_policy("commit.gpgSign is enabled")
        configured = self._runner.run(
            "rollback_hooks_path",
            ("config", "--path", "--get", "core.hooksPath"),
            cwd=root,
            allowed_return_codes=(0, 1),
        )
        if configured.return_code == 0:
            hooks = Path(configured.stdout.strip())
            hooks = hooks if hooks.is_absolute() else root / hooks
        else:
            hooks = Path(
                self._runner.run(
                    "rollback_default_hooks_path",
                    ("rev-parse", "--git-path", "hooks"),
                    cwd=root,
                ).stdout.strip()
            )
            hooks = hooks if hooks.is_absolute() else root / hooks
        active = [name for name in _COMMIT_HOOKS if os.access(hooks / name, os.X_OK)]
        if active:
            self._raise_commit_policy(
                f"active commit hooks require an integration-aware commit path: {', '.join(active)}"
            )

    @staticmethod
    def _raise_commit_policy(reason: str) -> None:
        raise VersionCollaborationError(
            ErrorCode.INVALID_STATE,
            "Atomic rollback cannot bypass the repository's commit security policy.",
            details={"reason": reason},
            suggested_actions=("integration.open",),
        )

    def _tree_id(self, root: Path, commit_id: str) -> str:
        return self._runner.run(
            "rollback_tree_resolve",
            ("rev-parse", "--verify", f"{commit_id}^{{tree}}"),
            cwd=root,
        ).stdout.strip()

    @staticmethod
    def _trailers(message: str) -> dict[str, str]:
        return {
            key: value.strip()
            for line in message.splitlines()
            if ":" in line
            for key, value in (line.split(":", 1),)
            if key.startswith("SceneOps-")
        }

    @staticmethod
    def _commit_message(command: GitRollbackCommand) -> str:
        return (
            f"{command.commit_message}\n\n"
            f"SceneOps-Operation: {command.operation_id}\n"
            f"SceneOps-Proposal: {command.proposal_id}\n"
            f"SceneOps-Approval: {command.approval_id}\n"
            f"SceneOps-Expected-Head: {command.expected_head}\n"
            f"SceneOps-Target: {command.target_commit}"
        )
