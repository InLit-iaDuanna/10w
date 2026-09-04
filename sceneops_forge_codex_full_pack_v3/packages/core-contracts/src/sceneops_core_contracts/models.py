"""Version 1 cross-module contracts for SceneOps Forge.

Domain entities deliberately do not belong here. These models contain only the
identity, execution, mutation-safety, provenance, and workbench primitives used
by more than one feature module.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from .ids import (
    ActorId,
    ApprovalId,
    ArtifactId,
    AssetId,
    BranchId,
    BuildId,
    ChangeSetId,
    CommandId,
    ContributionId,
    CorrelationId,
    EventId,
    FeatureId,
    IssueId,
    ModuleId,
    PlaytestRunId,
    ProjectId,
    RenderJobId,
    RunId,
    SceneId,
    SceneObjectId,
    Sha256Checksum,
    StableId,
    TaskId,
)


CONTRACT_VERSION = 1


class CoreContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ActorType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SERVICE = "service"
    SYSTEM = "system"


class StandardErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INTEGRATION_OFFLINE = "INTEGRATION_OFFLINE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    UNAVAILABLE = "UNAVAILABLE"
    INTERNAL = "INTERNAL"


class ActorReference(CoreContract):
    type: ActorType
    id: ActorId
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def id_matches_actor_type(self) -> "ActorReference":
        expected = {
            ActorType.USER: "usr_",
            ActorType.AGENT: "agt_",
            ActorType.SERVICE: "svc_",
            ActorType.SYSTEM: "sys_",
        }[self.type]
        if not self.id.startswith(expected):
            raise ValueError(f"actor id must start with {expected} for type {self.type.value}")
        return self


class StandardError(CoreContract):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    message: str = Field(min_length=1, max_length=1000)
    details: Dict[str, JsonValue] = Field(default_factory=dict)
    request_id: Optional[str] = Field(default=None, pattern=r"^req_[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
    retryable: bool = False
    suggested_actions: List[ContributionId] = Field(default_factory=list)


class ApprovalState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalDecisionValue(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactScope(str, Enum):
    OBJECT = "object"
    MODULE = "module"
    SCENE = "scene"
    PROJECT = "project"
    REPOSITORY = "repository"
    RELEASE = "release"


class ApprovalRequirement(CoreContract):
    permission: str = Field(pattern=r"^[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*$")
    minimum_decisions: int = Field(default=1, ge=1, le=20)
    allowed_actor_types: List[ActorType] = Field(default_factory=lambda: [ActorType.USER])


class ApprovalDecision(CoreContract):
    approval_id: ApprovalId
    change_set_id: ChangeSetId
    decision: ApprovalDecisionValue
    actor: ActorReference
    decided_at: datetime
    comment: Optional[str] = Field(default=None, max_length=2000)

    _validate_decided_at = field_validator("decided_at")(_require_utc)


class ChangeSetTarget(CoreContract):
    module_id: ModuleId
    integration_id: Optional[str] = Field(
        default=None, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
    )
    object_ids: List[StableId] = Field(default_factory=list)


class ChangeSetStatus(str, Enum):
    DRAFT = "draft"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ChangeSet(CoreContract):
    change_set_id: ChangeSetId
    base_version: str = Field(min_length=1, max_length=256)
    target: ChangeSetTarget
    previous_values: Dict[str, JsonValue]
    proposed_values: Dict[str, JsonValue]
    rationale: str = Field(min_length=1, max_length=4000)
    expected_result: str = Field(min_length=1, max_length=4000)
    impact_scope: ImpactScope
    risk: RiskLevel
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_requirements: List[ApprovalRequirement] = Field(default_factory=list)
    dry_run_supported: Literal[True] = True
    destructive: bool = False
    status: ChangeSetStatus = ChangeSetStatus.DRAFT
    created_by: ActorReference
    created_at: datetime

    _validate_created_at = field_validator("created_at")(_require_utc)

    @model_validator(mode="after")
    def enforce_reviewable_mutation(self) -> "ChangeSet":
        if self.previous_values == self.proposed_values:
            raise ValueError("previous_values and proposed_values must differ")
        approval_scopes = {
            ImpactScope.SCENE,
            ImpactScope.PROJECT,
            ImpactScope.REPOSITORY,
            ImpactScope.RELEASE,
        }
        if (self.destructive or self.impact_scope in approval_scopes) and not self.approval_requirements:
            raise ValueError("destructive and broad changes require approval_requirements")
        return self


class AiProvenance(CoreContract):
    provider: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=160)
    workflow_hash: Sha256Checksum
    prompt: str
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    parameters: Dict[str, JsonValue] = Field(default_factory=dict)


class ArtifactProvenance(CoreContract):
    source_project_id: ProjectId
    source_version: str = Field(min_length=1, max_length=256)
    source_commit: Optional[str] = Field(default=None, min_length=7, max_length=128)
    related_sceneops_ids: List[SceneObjectId] = Field(default_factory=list)
    producing_module: ModuleId
    tool_name: str = Field(min_length=1, max_length=160)
    tool_version: str = Field(min_length=1, max_length=160)
    adapter_version: str = Field(min_length=1, max_length=160)
    recipe_version: str = Field(min_length=1, max_length=160)
    creator: ActorReference
    execution_mode: ExecutionMode
    created_at: datetime
    checksum: Sha256Checksum
    approval_state: ApprovalState
    cached_from_run_id: Optional[RunId] = None
    fixture_id: Optional[str] = Field(default=None, min_length=1, max_length=256)
    ai: Optional[AiProvenance] = None

    _validate_created_at = field_validator("created_at")(_require_utc)

    @model_validator(mode="after")
    def require_mode_evidence(self) -> "ArtifactProvenance":
        if self.execution_mode == ExecutionMode.CACHED and self.cached_from_run_id is None:
            raise ValueError("cached provenance requires cached_from_run_id")
        if self.execution_mode == ExecutionMode.MOCK and self.fixture_id is None:
            raise ValueError("mock provenance requires fixture_id")
        return self


class Artifact(CoreContract):
    artifact_id: ArtifactId
    artifact_type: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
    version: str = Field(min_length=1, max_length=160)
    uri: str = Field(min_length=1, max_length=2048)
    provenance: ArtifactProvenance
    metadata: Dict[str, JsonValue] = Field(default_factory=dict)


class CommandEnvelope(CoreContract):
    command_id: CommandId
    command_type: ContributionId
    command_version: int = Field(default=1, ge=1)
    issued_at: datetime
    project_id: Optional[ProjectId] = None
    correlation_id: CorrelationId
    actor: ActorReference
    mode: ExecutionMode
    payload: JsonValue

    _validate_issued_at = field_validator("issued_at")(_require_utc)


class EventEnvelope(CoreContract):
    event_id: EventId
    event_type: ContributionId
    event_version: int = Field(ge=1)
    occurred_at: datetime
    project_id: Optional[ProjectId] = None
    correlation_id: CorrelationId
    causation_id: Optional[CommandId] = None
    actor: ActorReference
    mode: ExecutionMode
    payload: JsonValue

    _validate_occurred_at = field_validator("occurred_at")(_require_utc)


class JobDefinition(CoreContract):
    id: ContributionId
    module_id: ModuleId
    input_schema: str = Field(min_length=1, max_length=512)
    output_schema: str = Field(min_length=1, max_length=512)
    supports_dry_run: Literal[True] = True
    cancellable: bool
    retryable: bool
    resumable: bool


class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class RunRecord(CoreContract):
    run_id: RunId
    job_id: ContributionId
    state: RunState
    mode: ExecutionMode
    attempt: int = Field(default=1, ge=1)
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[StandardError] = None
    artifact_ids: List[ArtifactId] = Field(default_factory=list)

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def validate_timestamps(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else value

    @model_validator(mode="after")
    def validate_terminal_record(self) -> "RunRecord":
        terminal = {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.ROLLED_BACK,
        }
        if self.state in terminal and self.finished_at is None:
            raise ValueError("terminal run state requires finished_at")
        if self.state == RunState.FAILED and self.error is None:
            raise ValueError("failed run requires error")
        if self.mode == ExecutionMode.BLOCKED and self.error is None:
            raise ValueError("blocked execution mode requires error")
        if self.state == RunState.SUCCEEDED and self.error is not None:
            raise ValueError("succeeded run cannot include error")
        return self


class WorkbenchContext(CoreContract):
    project_id: Optional[ProjectId] = None
    branch_id: Optional[BranchId] = None
    scene_id: Optional[SceneId] = None
    selected_scene_object_ids: List[SceneObjectId] = Field(default_factory=list)
    selected_asset_ids: List[AssetId] = Field(default_factory=list)
    active_feature_id: Optional[FeatureId] = None
    active_task_id: Optional[TaskId] = None
    active_change_set_id: Optional[ChangeSetId] = None
    active_render_job_id: Optional[RenderJobId] = None
    active_build_id: Optional[BuildId] = None
    active_playtest_run_id: Optional[PlaytestRunId] = None
    active_issue_id: Optional[IssueId] = None
    camera_pose: Optional[Dict[str, JsonValue]] = None
    timeline_time: Optional[float] = None


PUBLIC_MODELS = (
    ActorReference,
    StandardError,
    ApprovalRequirement,
    ApprovalDecision,
    ChangeSetTarget,
    ChangeSet,
    AiProvenance,
    ArtifactProvenance,
    Artifact,
    CommandEnvelope,
    EventEnvelope,
    JobDefinition,
    RunRecord,
    WorkbenchContext,
)

PUBLIC_ENUMS = (
    ExecutionMode,
    ActorType,
    StandardErrorCode,
    ApprovalState,
    ApprovalDecisionValue,
    RiskLevel,
    ImpactScope,
    ChangeSetStatus,
    RunState,
)
