from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from asset_library import (
    AssetObjectIdentity,
    AssetSpec,
    AssetVersion,
    ExecutionMode,
    QualityGate,
    SourceAsset,
)


class ChangeSetState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PipelineState(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ROLLED_BACK = "rolled_back"
    BLOCKED = "blocked"


class StepState(str, Enum):
    QUEUED = "queued"
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ROLLED_BACK = "rolled_back"


class ProcessingStepKind(str, Enum):
    PREFLIGHT = "preflight"
    SNAPSHOT = "snapshot"
    CLEAN = "clean"
    UV_MATERIAL_CHECK = "uv_material_check"
    LOD = "lod"
    COLLIDER = "collider"
    TURNTABLE_AOV = "turntable_aov"
    VALIDATE = "validate"
    EXPORT = "export"
    PUBLISH = "publish"


class AssetChangeSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    change_set_id: str = Field(min_length=1)
    base_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    target_integration: Literal["blender"] = "blender"
    target_object_ids: List[str] = Field(min_length=1, max_length=10_000)
    previous_values: Dict[str, Any]
    proposed_values: Dict[str, Any]
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: List[str] = Field(min_length=1)
    risk: RiskLevel
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_requirements: List[str] = Field(min_length=1)
    state: ChangeSetState = ChangeSetState.PROPOSED
    approval_id: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    @model_validator(mode="after")
    def approved_state_has_evidence(self) -> "AssetChangeSet":
        if self.state == ChangeSetState.APPROVED:
            missing = [key for key in ("approval_id", "approved_by", "approved_at") if not getattr(self, key)]
            if missing:
                raise ValueError("approved ChangeSet is missing: " + ", ".join(missing))
        if len(self.target_object_ids) != len(set(self.target_object_ids)):
            raise ValueError("ChangeSet target object IDs must be unique")
        return self


class RetryPolicy(BaseModel):
    max_attempts: int = Field(3, ge=1, le=5)
    backoff_seconds: float = Field(0, ge=0, le=30)


class PipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline_run_id: str = Field(min_length=1, max_length=160, pattern="^[A-Za-z0-9_.:-]+$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    retry_of_run_id: Optional[str] = None
    spec: AssetSpec
    source: SourceAsset
    source_object_identities: List[AssetObjectIdentity] = Field(
        min_length=1, max_length=10_000
    )
    asset_version_id: str = Field(min_length=1, max_length=160, pattern="^[A-Za-z0-9_.:-]+$")
    asset_version_number: int = Field(gt=0, le=2_000_000_000)
    output_directory: str = Field(min_length=1)
    change_set: AssetChangeSet
    requested_mode: ExecutionMode
    dry_run: bool = False
    timeout_seconds: float = Field(120, gt=0, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    creator: str = Field(min_length=1)

    @field_validator("requested_mode")
    @classmethod
    def requested_mode_is_selectable(cls, value: ExecutionMode) -> ExecutionMode:
        if value in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("requested_mode must be live, cached, or mock")
        return value

    @field_validator("output_directory")
    @classmethod
    def output_directory_is_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/").rstrip("/")
        if (
            not normalized
            or normalized.startswith("/")
            or ".." in normalized.split("/")
            or normalized.split("/", 1)[0] == ".sceneops"
        ):
            raise ValueError("output_directory must be project-relative")
        return normalized

    @model_validator(mode="after")
    def request_relationships_match(self) -> "PipelineRequest":
        if self.spec.asset_id != self.source.asset_id or self.spec.project_id != self.source.project_id:
            raise ValueError("spec and source must reference the same asset/project")
        if self.spec.project_id != self.change_set.project_id:
            raise ValueError("ChangeSet project does not match AssetSpec")
        if self.source.format.casefold() != "blend" or not self.source.project_relative_path.lower().endswith(
            ".blend"
        ):
            raise ValueError("Blender pipeline source must be a .blend asset")
        if self.change_set.base_version != "source:" + self.source.source_version:
            raise ValueError("ChangeSet base version does not match SourceAsset")
        source_id_values = [item.sceneops_id for item in self.source_object_identities]
        source_ids = set(source_id_values)
        if len(source_id_values) != len(source_ids):
            raise ValueError("source object sceneops_id values must be unique")
        if any(
            item.source_asset_id != self.source.source_asset_id
            for item in self.source_object_identities
        ):
            raise ValueError("source object identities belong to another source asset")
        if not set(self.change_set.target_object_ids).issubset(source_ids):
            raise ValueError("ChangeSet targets must be source object sceneops_id values")
        if self.spec.asset_id not in self.change_set.impact_scope:
            raise ValueError("ChangeSet impact scope must include the asset")
        reserved = {self.spec.asset_id, self.source.source_asset_id, self.asset_version_id}
        if source_ids & reserved:
            raise ValueError("asset, source, version, and object identities must be distinct")
        return self


class ProcessingLog(BaseModel):
    timestamp: datetime
    level: str = Field(pattern="^(debug|info|warning|error)$")
    code: str = Field(min_length=1)
    message: str
    step_id: str
    attempt: int = Field(ge=0)


class ProcessingStep(BaseModel):
    step_id: str
    kind: ProcessingStepKind
    state: StepState = StepState.QUEUED
    execution_mode: ExecutionMode
    progress: float = Field(0, ge=0, le=1)
    attempts: int = Field(0, ge=0)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: List[ProcessingLog] = Field(default_factory=list)
    result: Dict[str, Any] = Field(default_factory=dict)
    skip_reason: Optional[str] = None
    error_code: Optional[str] = None


class PipelineRun(BaseModel):
    schema_version: Literal[1] = 1
    pipeline_run_id: str
    idempotency_key: str
    project_id: str
    asset_id: str
    asset_version_id: str
    requested_mode: ExecutionMode
    execution_mode: ExecutionMode
    state: PipelineState
    change_set_id: str
    creator: str
    steps: List[ProcessingStep]
    quality_gates: List[QualityGate] = Field(default_factory=list)
    candidate_version: Optional[AssetVersion] = None
    published_version: Optional[AssetVersion] = None
    rollback_snapshot_path: Optional[str] = None
    working_copy_path: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_of_run_id: Optional[str] = None


class PipelineErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    suggested_actions: List[str]
