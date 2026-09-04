"""Shared Pydantic records for build and release domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated

from .enums import (
    ApprovalAction,
    ApprovalDecision,
    ExecutionMode,
    GateCategory,
    GateStatus,
)

StableId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{2,127}$"),
]
Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{64}$"),
]
GitCommit = Annotated[
    str,
    StringConstraints(pattern=r"^[a-fA-F0-9]{7,64}$"),
]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UtcModel(DomainModel):
    @field_validator("*", mode="after")
    @classmethod
    def timestamps_must_be_utc(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
                raise ValueError("timestamps must use UTC")
        return value


class ArtifactRef(UtcModel):
    artifact_id: StableId
    project_id: StableId
    game_id: StableId
    build_run_id: StableId
    artifact_type: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    uri: str = Field(min_length=1, max_length=512)
    checksum: Sha256Digest
    size_bytes: int = Field(ge=0)
    source_commit: GitCommit
    mode: ExecutionMode
    origin_live_run_id: Optional[StableId] = None
    origin_live_artifact_id: Optional[StableId] = None
    created_at: datetime

    @model_validator(mode="after")
    def cached_artifact_requires_live_origin(self) -> "ArtifactRef":
        if self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("planned or blocked records cannot claim an artifact")
        origin_fields = (self.origin_live_run_id, self.origin_live_artifact_id)
        if self.mode == ExecutionMode.CACHED and not all(origin_fields):
            raise ValueError("cached artifacts require prior live-run provenance")
        if self.mode != ExecutionMode.CACHED and any(origin_fields):
            raise ValueError("live-origin replay fields are only valid for cached artifacts")
        return self


class VersionBinding(DomainModel):
    version_id: str = Field(min_length=1, max_length=120)
    checksum: Sha256Digest


class GateEvidence(ArtifactRef):
    category: GateCategory
    result: GateStatus
    summary: str = Field(min_length=1, max_length=500)


class Approval(UtcModel):
    approval_id: StableId
    action: ApprovalAction
    target_id: StableId
    scope_fingerprint: Sha256Digest
    role: str = Field(min_length=1, max_length=80)
    actor_id: StableId
    decision: ApprovalDecision
    rationale: str = Field(min_length=1, max_length=500)
    decided_at: datetime


class ApprovedChangeSet(UtcModel):
    change_set_id: StableId
    project_id: StableId
    game_id: StableId
    included_source_commit: GitCommit
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    approved: bool
    approval_ids: List[StableId] = Field(default_factory=list)
    approved_at: Optional[datetime] = None

    @field_validator("approval_ids")
    @classmethod
    def approval_ids_are_unique(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("approval_ids must be unique")
        return value
