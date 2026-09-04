"""Clock, cancellation, and contained-path primitives for adapters."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class SystemUtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class NeverCancelled:
    @property
    def cancelled(self) -> bool:
        return False


def validated_root(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("configured root cannot be a symlink")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("configured root must be a real directory")
    return resolved


def resolve_regular_file(root: Path, relative_uri: str) -> Path:
    if "\x00" in relative_uri:
        raise ValueError("artifact URI contains a NUL byte")
    relative = Path(relative_uri)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact URI must be a contained relative path")
    candidate = root.joinpath(relative)
    assert_no_symlink_chain(root, candidate)
    resolved = candidate.resolve(strict=True)
    assert_within(root, resolved)
    metadata = resolved.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError("artifact must be a regular non-hardlinked file")
    return resolved


def assert_within(root: Path, path: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ValueError("resolved path escapes its configured root") from exc


def assert_no_symlink_chain(root: Path, path: Path) -> None:
    assert_within(root, path)
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("symlinks are not allowed in release paths")


def ensure_contained_directory(root: Path, *parts: str) -> Path:
    """Create a directory tree without traversing a pre-existing symlink."""

    current = root
    for part in parts:
        if not part or part in {".", ".."} or Path(part).name != part:
            raise ValueError("release directory segments must be simple names")
        current = current / part
        assert_within(root, current)
        try:
            os.mkdir(current, mode=0o750)
        except FileExistsError:
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise ValueError("release directory path must contain real directories")
    return current


def atomic_write_json(
    directory: Path, filename: str, payload: Mapping[str, Any]
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".release-record.", suffix=".json", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / filename)
    finally:
        temporary.unlink(missing_ok=True)
