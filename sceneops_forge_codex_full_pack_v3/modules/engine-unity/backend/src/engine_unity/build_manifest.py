"""Immutable Unity build provenance manifests."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import ExecutionMode, SourceAssetReference


class ImmutableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BuildArtifact(ImmutableModel):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class BuildTestEvidence(ImmutableModel):
    run_id: str
    status: Literal["passed", "failed", "blocked"]
    mode: ExecutionMode
    results_path: str


class UnityBuildManifest(ImmutableModel):
    schema_version: Literal[1] = 1
    build_id: str = Field(pattern=r"^bld_")
    project_id: str = Field(pattern=r"^prj_")
    profile: str
    execution_mode: ExecutionMode
    unity_version: str
    package_version: str
    source_commit: str
    scenes: List[str]
    source_assets: List[SourceAssetReference]
    settings: Dict[str, Any]
    tests: List[BuildTestEvidence]
    artifacts: List[BuildArtifact]
    produced_at: datetime


def artifact_record(project_root: Path, artifact_path: Path) -> BuildArtifact:
    """Describe a file or directory using a stable content digest.

    Unity standalone builds are directories. Their digest includes each relative path,
    byte count, and file digest in sorted order so a renamed or modified file changes
    the artifact identity.
    """

    artifact = artifact_path.resolve(strict=True)
    if artifact.is_file():
        digest = _file_digest(artifact)
        size = artifact.stat().st_size
    else:
        digest_builder = hashlib.sha256()
        size = 0
        for item in sorted(path for path in artifact.rglob("*") if path.is_file()):
            relative = item.relative_to(artifact).as_posix()
            item_digest = _file_digest(item)
            item_size = item.stat().st_size
            digest_builder.update(relative.encode("utf-8"))
            digest_builder.update(b"\0")
            digest_builder.update(str(item_size).encode("ascii"))
            digest_builder.update(b"\0")
            digest_builder.update(item_digest.encode("ascii"))
            digest_builder.update(b"\n")
            size += item_size
        digest = digest_builder.hexdigest()
    try:
        display_path = artifact.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display_path = str(artifact)
    return BuildArtifact(path=display_path, sha256=digest, size_bytes=size)


def _file_digest(path: Path) -> str:
    builder = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            builder.update(chunk)
    return builder.hexdigest()
