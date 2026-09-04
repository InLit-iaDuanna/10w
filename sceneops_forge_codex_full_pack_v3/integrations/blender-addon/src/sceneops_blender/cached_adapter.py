from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .artifacts import artifact_sha256
from .contracts import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    BlenderResult,
    CapabilityReport,
    ChangePreview,
    ExecutionMode,
    IntegrationHealth,
    PERSISTENT_SCENE_MUTATIONS,
)
from .path_policy import ProjectPathPolicy
from .support import capabilities, preview, utc_now


class VerifiedCacheArtifact(BaseModel):
    """A trusted blob bound to one command side effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=1)
    target: Literal["source", "output"]
    output_index: Optional[int] = Field(None, ge=0, le=7)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    format: Optional[str] = None
    media_type: Optional[str] = None

    @model_validator(mode="after")
    def target_has_the_right_index(self) -> "VerifiedCacheArtifact":
        if self.target == "source" and self.output_index is not None:
            raise ValueError("source cache artifacts cannot have an output index")
        if self.target == "output" and self.output_index is None:
            raise ValueError("output cache artifacts require an output index")
        return self


class VerifiedLiveOperationRecord(BaseModel):
    """Evidence loaded from trusted run storage, never from an API request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_run_id: str = Field(min_length=1)
    cache_key: str = Field(min_length=1)
    live_evidence_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    command_payload: Dict[str, Any]
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    result: BlenderResult
    materializations: List[VerifiedCacheArtifact] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_is_successful_live_output(self) -> "VerifiedLiveOperationRecord":
        if self.result.mode != ExecutionMode.LIVE or not self.result.succeeded:
            raise ValueError("verified cache evidence must be a successful live result")
        targets = [
            (item.target, item.output_index) for item in self.materializations
        ]
        if len(targets) != len(set(targets)):
            raise ValueError("cache materialization targets must be unique")
        expected = _required_materialization_targets(
            self.result.operation, self.command_payload
        )
        if set(targets) != expected:
            raise ValueError("cache evidence does not cover every command side effect")
        if self.result.operation == BlenderOperation.EXPORT_ASSET and any(
            not item.format or not item.media_type for item in self.materializations
        ):
            raise ValueError("cached exports require format and media type evidence")
        return self


class VerifiedLiveResultStore(Protocol):
    def has_verified_live_run(self, source_run_id: str) -> bool: ...

    def get_verified(
        self, source_run_id: str, cache_key: str
    ) -> VerifiedLiveOperationRecord: ...

    def materialize_verified_artifact(
        self,
        source_run_id: str,
        live_evidence_id: str,
        artifact_id: str,
        destination: Path,
    ) -> None: ...


class CachedBlenderAdapter:
    mode = ExecutionMode.CACHED

    def __init__(
        self,
        project_root: Path,
        store: VerifiedLiveResultStore,
        source_run_id: str,
    ) -> None:
        if not source_run_id:
            raise ValueError("cached adapter requires a source live run ID")
        self.paths = ProjectPathPolicy(project_root)
        self.project_root = self.paths.project_root
        self.store = store
        self.source_run_id = source_run_id

    def health_check(self, timeout_seconds: float = 5) -> IntegrationHealth:
        available = self.store.has_verified_live_run(self.source_run_id)
        return IntegrationHealth(
            healthy=available,
            mode=ExecutionMode.CACHED if available else ExecutionMode.BLOCKED,
            version=None,
            code="BLENDER_CACHED_RESULT_READY" if available else "BLENDER_CACHED_RESULT_MISSING",
            message=(
                "Verified result from live run %s is available." % self.source_run_id
                if available
                else "No verified live run is available for the requested cache source."
            ),
            checked_at=utc_now(),
        )

    def capabilities(self) -> CapabilityReport:
        return capabilities()

    def dry_run(self, command: BlenderCommand) -> ChangePreview:
        if not command.dry_run:
            raise BlenderAdapterError("DRY_RUN_REQUIRED", "preview command must set dry_run=true")
        self._validate_command_paths(command)
        return preview(command)

    def execute(self, command: BlenderCommand, timeout_seconds: float, **_: object) -> BlenderResult:
        if command.dry_run:
            raise BlenderAdapterError("DRY_RUN_EXECUTION_FORBIDDEN", "dry-run command cannot execute")
        self._validate_command_paths(command)
        cache_key = _cache_key(command)
        try:
            record = self.store.get_verified(self.source_run_id, cache_key)
        except LookupError as error:
            raise BlenderAdapterError(
                "CACHE_MISS", "operation is not present in verified live-run storage"
            ) from error
        self._verify_record(record, command, cache_key)
        self._materialize(record, command)
        return _cached_result(record, command)

    def _verify_record(
        self,
        record: VerifiedLiveOperationRecord,
        command: BlenderCommand,
        cache_key: str,
    ) -> None:
        if record.source_run_id != self.source_run_id:
            raise BlenderAdapterError("CACHE_PROVENANCE_MISMATCH", "source run ID differs")
        if record.cache_key != cache_key:
            raise BlenderAdapterError("CACHE_PROVENANCE_MISMATCH", "cache key differs")
        if record.command_payload != cache_behavior_payload(command):
            raise BlenderAdapterError(
                "CACHE_INPUT_MISMATCH", "cached command inputs differ from the request"
            )
        if record.result.operation != command.operation:
            raise BlenderAdapterError("CACHE_PROVENANCE_MISMATCH", "operation differs")
        if command.source_path:
            source = self.paths.resolve(command.source_path, must_exist=True)
            if artifact_sha256(source) != record.source_sha256:
                raise BlenderAdapterError("CACHE_INPUT_MISMATCH", "source checksum differs")

    def _materialize(
        self, record: VerifiedLiveOperationRecord, command: BlenderCommand
    ) -> None:
        for artifact in record.materializations:
            destination = self._materialization_path(command, artifact)
            destination.parent.mkdir(parents=True, exist_ok=True)
            replace_target = artifact.target == "source" or (
                command.operation == BlenderOperation.ROLLBACK_SNAPSHOT
                and artifact.target == "output"
            )
            if not replace_target and destination.exists():
                self._verify_materialized_file(destination, artifact)
                continue
            temporary = destination.with_name(
                ".%s.cached.%s" % (destination.name, uuid.uuid4().hex)
            )
            try:
                self.store.materialize_verified_artifact(
                    record.source_run_id,
                    record.live_evidence_id,
                    artifact.artifact_id,
                    temporary,
                )
                self._verify_materialized_file(temporary, artifact)
                if replace_target:
                    os.replace(temporary, destination)
                else:
                    try:
                        with temporary.open("rb") as source, destination.open("xb") as output:
                            shutil.copyfileobj(source, output)
                    except Exception:
                        destination.unlink(missing_ok=True)
                        raise
                    self._verify_materialized_file(destination, artifact)
            except BlenderAdapterError:
                raise
            except Exception as error:
                raise BlenderAdapterError(
                    "CACHE_MATERIALIZATION_FAILED",
                    "verified cached artifact could not be materialized",
                ) from error
            finally:
                temporary.unlink(missing_ok=True)

    def _materialization_path(
        self, command: BlenderCommand, artifact: VerifiedCacheArtifact
    ) -> Path:
        if artifact.target == "source":
            return self.paths.require_asset_factory_working_copy(
                command.source_path or "", must_exist=True
            )
        try:
            relative_path = command.output_paths[artifact.output_index or 0]
        except IndexError as error:
            raise BlenderAdapterError(
                "CACHE_PROVENANCE_INVALID", "cached output index is unavailable"
            ) from error
        return self.paths.resolve(relative_path)

    @staticmethod
    def _verify_materialized_file(
        path: Path, artifact: VerifiedCacheArtifact
    ) -> None:
        try:
            size = path.stat().st_size
            checksum = artifact_sha256(path)
        except OSError as error:
            raise BlenderAdapterError(
                "CACHE_ARTIFACT_MISMATCH", "cached artifact is unavailable"
            ) from error
        if size != artifact.byte_size or checksum != artifact.sha256:
            raise BlenderAdapterError(
                "CACHE_ARTIFACT_MISMATCH", "cached artifact integrity differs"
            )

    def _validate_command_paths(self, command: BlenderCommand) -> None:
        if command.source_path:
            self.paths.resolve(command.source_path, must_exist=True)
        self.paths.validate_all(command.output_paths)
        if command.operation in PERSISTENT_SCENE_MUTATIONS and not command.dry_run:
            self.paths.require_asset_factory_working_copy(command.source_path or "", must_exist=True)
        if command.operation == BlenderOperation.SAVE_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.output_paths[0])
            self.paths.require_asset_factory_working_copy(command.output_paths[1])
        if command.operation == BlenderOperation.ROLLBACK_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.source_path or "")
            self.paths.require_asset_factory_working_copy(command.output_paths[0])


def cache_behavior_payload(command: BlenderCommand) -> Dict[str, Any]:
    payload = command.model_dump(mode="json", exclude={"request_id", "dry_run"})
    payload["source_path"] = _normalize_run_path(payload.get("source_path"))
    payload["output_paths"] = _normalize_run_path(payload.get("output_paths", []))
    return payload


def cache_key_for(command: BlenderCommand) -> str:
    return _cache_key(command)


def _cache_key(command: BlenderCommand) -> str:
    match = re.search(r":([0-9]{2}):([a-z_]+)$", command.request_id)
    if match and match.group(2) == command.operation.value:
        return "%s:%s" % (match.group(1), command.operation.value)
    return command.operation.value


def _normalize_run_path(value: Any) -> Any:
    if isinstance(value, str):
        path = PurePosixPath(value)
        parts = list(path.parts)
        if len(parts) >= 3 and parts[:2] == [".sceneops", "asset-factory"]:
            parts[2] = "{pipeline_run_id}"
            return PurePosixPath(*parts).as_posix()
        if path.parent.name == "review" and path.name.endswith("-turntable.exr"):
            return (path.parent / "{pipeline_run_id}-turntable.exr").as_posix()
        return value
    if isinstance(value, list):
        return [_normalize_run_path(item) for item in value]
    return value


def _required_materialization_targets(
    operation: BlenderOperation, command_payload: Dict[str, Any]
) -> set[tuple[str, Optional[int]]]:
    if operation in PERSISTENT_SCENE_MUTATIONS:
        return {("source", None)}
    output_counts = {
        BlenderOperation.SAVE_SNAPSHOT: 2,
        BlenderOperation.ROLLBACK_SNAPSHOT: 1,
        BlenderOperation.RENDER_AOV: 1,
        BlenderOperation.EXPORT_ASSET: len(command_payload.get("output_paths", [])),
    }
    return {
        ("output", index) for index in range(output_counts.get(operation, 0))
    }


def _cached_result(
    record: VerifiedLiveOperationRecord, command: BlenderCommand
) -> BlenderResult:
    data = dict(record.result.data)
    if command.operation == BlenderOperation.SAVE_SNAPSHOT:
        data.update(
            snapshot_path=command.output_paths[0],
            working_copy_path=command.output_paths[1],
        )
    elif command.operation == BlenderOperation.ROLLBACK_SNAPSHOT:
        data["working_copy_path"] = command.output_paths[0]
    elif command.operation == BlenderOperation.RENDER_AOV:
        data["output_path"] = command.output_paths[0]
    elif command.operation == BlenderOperation.EXPORT_ASSET:
        data["artifacts"] = [
            {
                "artifact_id": item.artifact_id,
                "format": item.format,
                "project_relative_path": command.output_paths[item.output_index or 0],
                "media_type": item.media_type,
                "byte_size": item.byte_size,
                "sha256": item.sha256,
            }
            for item in sorted(
                record.materializations, key=lambda value: value.output_index or 0
            )
        ]
    return record.result.model_copy(
        update={
            "request_id": command.request_id,
            "mode": ExecutionMode.CACHED,
            "data": data,
        },
        deep=True,
    )
