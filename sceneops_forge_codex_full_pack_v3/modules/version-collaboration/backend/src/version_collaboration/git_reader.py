from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .base import Clock, ExecutionMode, VersionReference
from .errors import ErrorCode, VersionCollaborationError
from .git_models import (
    GitBranch,
    GitChangeKind,
    GitCommit,
    GitFileChange,
    GitRepositoryState,
    GitVersionDiff,
    LfsPointer,
    validate_relative_path,
)
from .git_runner import GitCommandRunner


_CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


class GitRepositoryReader:
    """Read-only Git projections used by the collaboration adapter."""

    def __init__(self, runner: GitCommandRunner, clock: Clock) -> None:
        self._runner = runner
        self._clock = clock

    def inspect(
        self, project_id: str, repository_id: str, root: Path
    ) -> GitRepositoryState:
        head = self.resolve_commit(root, "HEAD")
        object_format = self.object_format(root)
        branch_output = self._runner.run(
            "current_branch",
            ("symbolic-ref", "--short", "-q", "HEAD"),
            cwd=root,
            allowed_return_codes=(0, 1),
        )
        branch = branch_output.stdout.strip() or None
        changes = self.working_changes(root)
        return GitRepositoryState(
            project_id=project_id,
            version=VersionReference(
                repository_id=repository_id,
                object_format=object_format,
                commit_id=head,
                branch=branch,
            ),
            dirty=bool(changes),
            conflicted=any(
                change.kind == GitChangeKind.CONFLICT for change in changes
            ),
            changes=changes,
            lfs_pointers=self.working_lfs_pointers(root, changes),
            branches=self.branches(root),
            commits=self.commits(root),
            mode=ExecutionMode.LIVE,
            captured_at=self._clock.now(),
        )

    def compare_versions(
        self,
        repository_id: str,
        root: Path,
        base_commit: str,
        target_commit: str,
    ) -> GitVersionDiff:
        base = self.resolve_commit(root, base_commit)
        target = self.resolve_commit(root, target_commit)
        changes = self.committed_changes(root, base, target)
        pointers = tuple(
            pointer
            for change in changes
            if (
                pointer := self.lfs_pointer_at(
                    root,
                    base if change.kind == GitChangeKind.DELETED else target,
                    change.path,
                )
            )
            is not None
        )
        return GitVersionDiff(
            base=VersionReference(
                repository_id=repository_id,
                object_format=self.object_format(root),
                commit_id=base,
            ),
            target=VersionReference(
                repository_id=repository_id,
                object_format=self.object_format(root),
                commit_id=target,
            ),
            changes=changes,
            lfs_pointers=pointers,
            mode=ExecutionMode.LIVE,
        )

    def resolve_commit(self, root: Path, revision: str) -> str:
        if revision != "HEAD":
            object_id = revision[:-1] if revision.endswith("^") else revision
            is_hex = all(
                character in "0123456789abcdefABCDEF" for character in object_id
            )
            if not 7 <= len(object_id) <= 64 or not is_hex:
                raise VersionCollaborationError(
                    ErrorCode.INVALID_STATE,
                    "Revision is not a valid Git object ID.",
                    details={"revision": revision},
                )
        output = self._runner.run(
            "resolve_revision",
            ("rev-parse", "--verify", f"{revision}^{{commit}}"),
            cwd=root,
        )
        return output.stdout.strip()

    def object_format(self, root: Path) -> str:
        value = self._runner.run(
            "object_format", ("rev-parse", "--show-object-format"), cwd=root
        ).stdout.strip()
        if value not in {"sha1", "sha256"}:
            raise VersionCollaborationError(
                ErrorCode.INCOMPATIBLE_SCHEMA,
                "Git reported an unsupported object format.",
                details={"object_format": value},
            )
        return value

    def working_changes(self, root: Path) -> tuple[GitFileChange, ...]:
        output = self._runner.run(
            "working_status",
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
            cwd=root,
        ).stdout
        return self._parse_status(output)

    def committed_changes(
        self, root: Path, base: str, target: str
    ) -> tuple[GitFileChange, ...]:
        names = self._runner.run(
            "file_diff",
            ("diff", "--name-status", "--find-renames", "-z", base, target, "--"),
            cwd=root,
        ).stdout.split("\0")
        stats = self._numstat(root, base, target)
        changes: list[GitFileChange] = []
        index = 0
        while index < len(names) and names[index]:
            status = names[index]
            index += 1
            old_path = None
            if status.startswith(("R", "C")):
                old_path = validate_relative_path(names[index])
                path = validate_relative_path(names[index + 1])
                index += 2
                kind = GitChangeKind.RENAMED
            else:
                path = validate_relative_path(names[index])
                index += 1
                kind = self._diff_kind(status)
            additions, deletions, binary = stats.get(
                path, (None, None, False)
            )
            pointer = self.lfs_pointer_at(
                root,
                base if kind == GitChangeKind.DELETED else target,
                path,
            )
            changes.append(
                GitFileChange(
                    path=path,
                    old_path=old_path,
                    kind=kind,
                    additions=additions,
                    deletions=deletions,
                    binary=binary or pointer is not None,
                )
            )
        return tuple(changes)

    def working_lfs_pointers(
        self, root: Path, changes: tuple[GitFileChange, ...]
    ) -> tuple[LfsPointer, ...]:
        pointers: list[LfsPointer] = []
        for change in changes:
            if change.kind == GitChangeKind.DELETED:
                continue
            candidate = (root / change.path).resolve()
            if candidate != root and root not in candidate.parents:
                continue
            if not candidate.is_file() or candidate.stat().st_size > 1024:
                continue
            try:
                content = candidate.read_text(errors="strict")
            except UnicodeDecodeError:
                continue
            pointer = parse_lfs_pointer(change.path, content)
            if pointer:
                pointers.append(
                    pointer.model_copy(
                        update={"lock_required": self._is_lockable(root, change.path)}
                    )
                )
        return tuple(pointers)

    def lfs_pointer_at(
        self, root: Path, revision: str, path: str
    ) -> LfsPointer | None:
        spec = f"{revision}:{path}"
        size_output = self._runner.run(
            "lfs_pointer_size",
            ("cat-file", "-s", spec),
            cwd=root,
            allowed_return_codes=(0, 128),
        )
        if (
            size_output.return_code != 0
            or int(size_output.stdout.strip()) > 1024
        ):
            return None
        content = self._runner.run(
            "lfs_pointer_read", ("show", spec), cwd=root
        ).stdout
        pointer = parse_lfs_pointer(path, content)
        if pointer is None:
            return None
        return pointer.model_copy(
            update={"lock_required": self._is_lockable(root, path)}
        )

    def branches(self, root: Path) -> tuple[GitBranch, ...]:
        output = self._runner.run(
            "list_branches",
            (
                "for-each-ref",
                "--format=%(refname:short)%09%(objectname)%09%(HEAD)",
                "refs/heads",
            ),
            cwd=root,
        ).stdout
        return tuple(
            GitBranch(name=name, commit_id=commit, current=marker == "*")
            for line in output.splitlines()
            if line
            for name, commit, marker in (line.split("\t", 2),)
        )

    def commits(self, root: Path) -> tuple[GitCommit, ...]:
        output = self._runner.run(
            "list_commits",
            ("log", "--all", "--topo-order", "-n", "200", "--format=%H%x1f%P%x1f%an%x1f%aI%x1f%s%x1e", "HEAD"),
            cwd=root,
        ).stdout
        commits: list[GitCommit] = []
        for record in output.split("\x1e"):
            record = record.strip("\n")
            if not record:
                continue
            commit_id, parents, author, authored_at, subject = record.split("\x1f", 4)
            commits.append(
                GitCommit(
                    parent_ids=tuple(parents.split()),
                    commit_id=commit_id,
                    author=author,
                    authored_at=datetime.fromisoformat(authored_at).astimezone(
                        timezone.utc
                    ),
                    subject=subject,
                )
            )
        return tuple(commits)

    def _parse_status(self, output: str) -> tuple[GitFileChange, ...]:
        fields = output.split("\0")
        changes: list[GitFileChange] = []
        index = 0
        while index < len(fields) and fields[index]:
            entry = fields[index]
            index += 1
            code, path = entry[:2], validate_relative_path(entry[3:])
            old_path = None
            if "R" in code or "C" in code:
                old_path = validate_relative_path(fields[index])
                index += 1
            changes.append(
                GitFileChange(
                    path=path,
                    old_path=old_path,
                    kind=self._status_kind(code),
                    binary=False,
                )
            )
        return tuple(changes)

    def _numstat(
        self, root: Path, base: str, target: str
    ) -> dict[str, tuple[int | None, int | None, bool]]:
        output = self._runner.run(
            "file_numstat",
            ("diff", "--numstat", "-z", base, target, "--"),
            cwd=root,
        ).stdout.split("\0")
        stats: dict[str, tuple[int | None, int | None, bool]] = {}
        index = 0
        while index < len(output) and output[index]:
            additions_text, deletions_text, path = output[index].split("\t", 2)
            index += 1
            if not path:
                validate_relative_path(output[index])
                path = output[index + 1]
                index += 2
            binary = additions_text == "-" or deletions_text == "-"
            stats[validate_relative_path(path)] = (
                None if binary else int(additions_text),
                None if binary else int(deletions_text),
                binary,
            )
        return stats

    def _is_lockable(self, root: Path, path: str) -> bool:
        output = self._runner.run(
            "lfs_lock_attribute", ("check-attr", "lockable", "--", path), cwd=root
        ).stdout.rstrip("\n")
        return output.endswith(": set") or output.endswith(": true")

    @staticmethod
    def _status_kind(code: str) -> GitChangeKind:
        if code in _CONFLICT_CODES:
            return GitChangeKind.CONFLICT
        if code == "??":
            return GitChangeKind.UNTRACKED
        if "R" in code or "C" in code:
            return GitChangeKind.RENAMED
        if "D" in code:
            return GitChangeKind.DELETED
        if "A" in code:
            return GitChangeKind.ADDED
        return GitChangeKind.MODIFIED

    @staticmethod
    def _diff_kind(status: str) -> GitChangeKind:
        return {
            "A": GitChangeKind.ADDED,
            "D": GitChangeKind.DELETED,
            "M": GitChangeKind.MODIFIED,
            "T": GitChangeKind.MODIFIED,
        }.get(status[0], GitChangeKind.MODIFIED)


def parse_lfs_pointer(path: str, content: str) -> LfsPointer | None:
    lines = content.splitlines()
    if len(lines) < 3 or lines[0] != "version https://git-lfs.github.com/spec/v1":
        return None
    if not lines[1].startswith("oid sha256:") or not lines[2].startswith("size "):
        return None
    object_id = lines[1].removeprefix("oid sha256:")
    try:
        size = int(lines[2].removeprefix("size "))
        return LfsPointer(path=path, object_id=object_id, size=size)
    except (ValueError, TypeError):
        return None
