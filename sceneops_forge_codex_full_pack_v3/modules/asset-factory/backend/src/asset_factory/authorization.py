from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asset_library import ArtifactOutput, AssetVersion, PublicationRequest
from sceneops_blender import BlenderCommand, ProjectPathPolicy, artifact_sha256

from .schemas import AssetChangeSet


class AssetApprovalRecord(BaseModel):
    """Trusted approval evidence populated outside the pipeline request boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(min_length=1)
    change_set_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_version_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: datetime
    change_set: AssetChangeSet
    command_scope: List[Dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def flattened_scope_matches_change_set(self) -> "AssetApprovalRecord":
        if self.change_set.state.value != "approved":
            raise ValueError("approval authority accepts only approved ChangeSets")
        expected = (
            self.change_set.approval_id,
            self.change_set.change_set_id,
            self.change_set.project_id,
            self.change_set.approved_by,
            self.change_set.approved_at,
        )
        actual = (
            self.approval_id,
            self.change_set_id,
            self.project_id,
            self.approved_by,
            self.approved_at,
        )
        if actual != expected:
            raise ValueError("approval record scope does not match its ChangeSet snapshot")
        return self


class AssetApprovalAuthority(Protocol):
    def verify_change_set(
        self,
        change_set: AssetChangeSet,
        asset_id: str,
        asset_version_id: str,
    ) -> List[str]: ...

    def verify(
        self, request: PublicationRequest, candidate: AssetVersion
    ) -> List[str]: ...

    def verify_workflow(
        self,
        change_set: AssetChangeSet,
        pipeline_run_id: str,
        commands: Iterable[BlenderCommand],
    ) -> List[str]: ...


class InMemoryAssetApprovalAuthority:
    """Composition-root authority; API callers cannot add approval records."""

    def __init__(self, records: Iterable[AssetApprovalRecord]) -> None:
        self._records: Dict[str, AssetApprovalRecord] = {}
        for record in records:
            if record.approval_id in self._records:
                raise ValueError("duplicate approval_id: " + record.approval_id)
            self._records[record.approval_id] = record

    def verify_change_set(
        self,
        change_set: AssetChangeSet,
        asset_id: str,
        asset_version_id: str,
    ) -> List[str]:
        if not change_set.approval_id:
            return ["ChangeSet has no approval ID"]
        record = self._records.get(change_set.approval_id)
        if record is None:
            return ["ChangeSet approval is unknown to the authority"]
        reasons = self._mismatches(
            record,
            {
                "project_id": change_set.project_id,
                "asset_id": asset_id,
                "asset_version_id": asset_version_id,
            },
        )
        if record.change_set != change_set:
            reasons.append("approval authority mismatch for ChangeSet contents")
        return reasons

    def verify(
        self, request: PublicationRequest, candidate: AssetVersion
    ) -> List[str]:
        record = self._records.get(request.approval_id)
        if record is None:
            return ["publication approval is unknown to the authority"]
        expected = {
            "change_set_id": request.change_set_id,
            "asset_id": request.asset_id,
            "asset_version_id": candidate.asset_version_id,
            "approved_by": request.approved_by,
        }
        return self._mismatches(record, expected)

    def verify_workflow(
        self,
        change_set: AssetChangeSet,
        pipeline_run_id: str,
        commands: Iterable[BlenderCommand],
    ) -> List[str]:
        if not change_set.approval_id:
            return ["workflow has no approval ID"]
        record = self._records.get(change_set.approval_id)
        if record is None:
            return ["workflow approval is unknown to the authority"]
        actual = canonical_command_scope(commands, pipeline_run_id)
        if record.command_scope != actual:
            return ["approved Blender command scope does not match the workflow"]
        return []

    @staticmethod
    def _mismatches(
        record: AssetApprovalRecord, expected: Dict[str, object]
    ) -> List[str]:
        return [
            "approval authority mismatch for " + field
            for field, value in expected.items()
            if getattr(record, field) != value
        ]


class ProjectRootRegistry(Protocol):
    def resolve(self, project_id: str) -> Path: ...


class InMemoryProjectRootRegistry:
    """Trusted project metadata supplied by the application composition root."""

    def __init__(self, roots: Dict[str, Path]) -> None:
        self._roots = {
            project_id: Path(root).expanduser().resolve(strict=True)
            for project_id, root in roots.items()
        }
        if not self._roots:
            raise ValueError("at least one trusted project root is required")

    def resolve(self, project_id: str) -> Path:
        try:
            return self._roots[project_id]
        except KeyError as error:
            raise LookupError("project root is not registered: " + project_id) from error


class ProjectArtifactVerifier:
    def __init__(self, roots: ProjectRootRegistry) -> None:
        self._roots = roots

    def verify(self, project_id: str, artifact: ArtifactOutput) -> List[str]:
        try:
            policy = ProjectPathPolicy(self._roots.resolve(project_id))
            path = policy.resolve(artifact.project_relative_path, must_exist=True)
            byte_size = path.stat().st_size
            checksum = artifact_sha256(path)
        except (LookupError, OSError, ValueError) as error:
            return ["artifact path was not verified: " + artifact.artifact_id]
        reasons: List[str] = []
        if byte_size != artifact.byte_size:
            reasons.append("artifact byte size does not match: " + artifact.artifact_id)
        if checksum != artifact.sha256:
            reasons.append("artifact checksum does not match: " + artifact.artifact_id)
        return reasons


def canonical_command_scope(
    commands: Iterable[BlenderCommand], pipeline_run_id: str
) -> List[Dict[str, Any]]:
    scopes: List[Dict[str, Any]] = []
    for command in commands:
        payload = command.model_dump(
            mode="json", exclude={"request_id", "authorization", "dry_run"}
        )
        for field in ("source_path", "output_paths"):
            payload[field] = _normalize_run_path(payload.get(field), pipeline_run_id)
        scopes.append(payload)
    return scopes


def _normalize_run_path(value: Any, pipeline_run_id: str) -> Any:
    if isinstance(value, str):
        path = PurePosixPath(value)
        parts = list(path.parts)
        if (
            len(parts) >= 3
            and parts[:2] == [".sceneops", "asset-factory"]
            and parts[2] == pipeline_run_id
        ):
            parts[2] = "{pipeline_run_id}"
            return PurePosixPath(*parts).as_posix()
        if path.parent.name == "review" and path.name == pipeline_run_id + "-turntable.exr":
            return (path.parent / "{pipeline_run_id}-turntable.exr").as_posix()
        return value
    if isinstance(value, list):
        return [_normalize_run_path(item, pipeline_run_id) for item in value]
    return value
