from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class Workstream(str, Enum):
    DESIGN = "design"
    CONCEPT = "concept"
    ASSET = "asset"
    ANIMATION = "animation"
    WORLD = "world"
    LOGIC = "logic"
    UI = "ui"
    AUDIO = "audio"
    VFX = "vfx"
    RENDER = "render"
    BUILD = "build"
    TEST = "test"


class PlanStatus(str, Enum):
    DRAFT_UNCONFIRMED = "draft_unconfirmed"
    APPROVED = "approved"
    BLOCKED = "blocked"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentKind(str, Enum):
    HUMAN = "human"
    AGENT = "agent"


class EstimateKind(str, Enum):
    PREDICTED = "predicted"
    MEASURED = "measured"


class ApprovalRequirement(str, Enum):
    NONE = "none"
    HUMAN = "human"


class EvidenceOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class MilestoneState(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class BlockerCode(str, Enum):
    MISSING_PREREQUISITE = "missing_prerequisite"
    DEPENDENCY_CYCLE = "dependency_cycle"
    IMPOSSIBLE_MILESTONE_STATE = "impossible_milestone_state"
    UNMET_ACCEPTANCE = "unmet_acceptance"
    APPROVAL_REQUIRED = "approval_required"
    UPSTREAM_INCOMPLETE = "upstream_incomplete"
    FEATURE_SOURCE_UNAVAILABLE = "feature_source_unavailable"
    OPERATIONAL_BLOCKER = "operational_blocker"


class FeatureAcceptanceCriterion(ContractModel):
    criterion_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    workstreams: list[Workstream] = Field(min_length=1)
    required_evidence: list[str] = Field(min_length=1)


class FeatureSpecReference(ContractModel):
    project_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


class FeaturePlanningSnapshot(ContractModel):
    feature_ref: FeatureSpecReference
    source_contract_version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    acceptance_criteria: list[FeatureAcceptanceCriterion] = Field(min_length=1)
    source_mode: ExecutionMode


class Assignment(ContractModel):
    assignment_id: str = Field(min_length=1)
    kind: AssignmentKind
    assignee_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    confirmed: bool = False


class Estimate(ContractModel):
    estimate_id: str = Field(min_length=1)
    kind: EstimateKind
    hours: float = Field(gt=0)
    source: str = Field(min_length=1)
    mode: ExecutionMode
    recorded_at: datetime
    run_id: Optional[str] = None
    originating_live_run_id: Optional[str] = None

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("recorded_at must use UTC")
        return value

    @model_validator(mode="after")
    def validate_provenance(self) -> "Estimate":
        if self.kind == EstimateKind.MEASURED:
            if not self.run_id:
                raise ValueError("measured estimates require run_id")
            if self.mode not in {ExecutionMode.LIVE, ExecutionMode.CACHED}:
                raise ValueError("measured estimates require live or cached run data")
            if self.mode == ExecutionMode.CACHED and not self.originating_live_run_id:
                raise ValueError("cached measured estimates require originating live run provenance")
        if self.kind == EstimateKind.PREDICTED and self.run_id:
            raise ValueError("predicted estimates cannot claim a run_id")
        return self


class TaskInput(ContractModel):
    input_id: str = Field(min_length=1)
    source_kind: str = Field(pattern="^(feature_spec|task_output)$")
    source_id: str = Field(min_length=1)
    required_artifact_type: str = Field(min_length=1)


class TaskOutput(ContractModel):
    output_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    artifact_id: Optional[str] = None


class AcceptanceLink(ContractModel):
    criterion_id: str = Field(min_length=1)
    expected_evidence: list[str] = Field(min_length=1)


class AcceptanceEvidence(ContractModel):
    evidence_id: str = Field(min_length=1)
    criterion_id: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    run_id: Optional[str] = None
    outcome: EvidenceOutcome
    mode: ExecutionMode
    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def captured_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("captured_at must use UTC")
        return value

    @model_validator(mode="after")
    def validate_execution_reference(self) -> "AcceptanceEvidence":
        if self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("planned or blocked output is not acceptance evidence")
        if self.mode in {ExecutionMode.LIVE, ExecutionMode.CACHED} and not self.run_id:
            raise ValueError("live or cached evidence requires run_id provenance")
        return self


class DeliverableLink(ContractModel):
    link_id: str = Field(min_length=1)
    output_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    mode: ExecutionMode

    @model_validator(mode="after")
    def validate_materialized_artifact(self) -> "DeliverableLink":
        if self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("planned or blocked output cannot be linked as a deliverable artifact")
        return self


class Risk(ContractModel):
    risk_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    likelihood: str = Field(pattern="^(low|medium|high)$")
    impact: str = Field(pattern="^(low|medium|high)$")
    mitigation: str = Field(min_length=1)
    state: str = Field(default="open", pattern="^(open|mitigated|accepted)$")


class TaskBlocker(ContractModel):
    blocker_id: str = Field(min_length=1)
    code: BlockerCode
    message: str = Field(min_length=1)
    task_ids: list[str]
    milestone_id: Optional[str] = None
    resolved: bool = False
    resolution_ref_id: Optional[str] = None


class TaskCommentReference(ContractModel):
    comment_id: str = Field(min_length=1)
    comment_thread_id: str = Field(min_length=1)


class ProductionTask(ContractModel):
    task_id: str = Field(min_length=1)
    workstream: Workstream
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.DRAFT
    confirmed: bool = False
    assignment: Assignment
    inputs: list[TaskInput] = Field(min_length=1)
    outputs: list[TaskOutput] = Field(min_length=1)
    acceptance: list[AcceptanceLink] = Field(min_length=1)
    estimates: list[Estimate] = Field(min_length=1)
    approval_requirement: ApprovalRequirement
    recommended_editor_id: str = Field(min_length=1)
    risks: list[Risk] = Field(default_factory=list)
    blockers: list[TaskBlocker] = Field(default_factory=list)
    comment_thread_id: Optional[str] = None
    comments: list[TaskCommentReference] = Field(default_factory=list)
    deliverables: list[DeliverableLink] = Field(default_factory=list)
    evidence: list[AcceptanceEvidence] = Field(default_factory=list)
    approval_ref_ids: list[str] = Field(default_factory=list)


class TaskDependency(ContractModel):
    dependency_id: str = Field(min_length=1)
    predecessor_task_id: str = Field(min_length=1)
    successor_task_id: str = Field(min_length=1)
    required_output_type: str = Field(min_length=1)


class Milestone(ContractModel):
    milestone_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    required_task_ids: list[str] = Field(min_length=1)
    state: MilestoneState = MilestoneState.PLANNED


class ProductionPlan(ContractModel):
    plan_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    feature_revision: int = Field(ge=1)
    feature_title: str = Field(min_length=1)
    plan_version: int = Field(default=1, ge=1)
    source_contract_version: str = Field(min_length=1)
    status: PlanStatus
    execution_mode: ExecutionMode
    feature_source_mode: ExecutionMode
    generated_at: datetime
    change_set_id: Optional[str] = None
    approval_ref_id: Optional[str] = None
    tasks: list[ProductionTask] = Field(min_length=1)
    dependencies: list[TaskDependency]
    milestones: list[Milestone] = Field(min_length=1)
    risks: list[Risk] = Field(default_factory=list)
    blockers: list[TaskBlocker] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def generated_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("generated_at must use UTC")
        return value


class GraphNode(ContractModel):
    task_id: str
    title: str
    workstream: Workstream
    status: TaskStatus
    assignment_kind: AssignmentKind
    assignment_label: str
    estimate_kind: EstimateKind
    estimate_hours: float
    blocked: bool


class GraphEdge(ContractModel):
    dependency_id: str
    source_task_id: str
    target_task_id: str


class CriticalPath(ContractModel):
    task_ids: list[str]
    total_hours: float = Field(ge=0)
    estimate_basis: list[EstimateKind]


class MilestoneReadiness(ContractModel):
    milestone_id: str
    state: MilestoneState
    incomplete_task_ids: list[str]
    blocker_ids: list[str]


class ProductionGraphView(ContractModel):
    plan_id: str
    mode: ExecutionMode
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    critical_path: CriticalPath
    blockers: list[TaskBlocker]
    milestone_readiness: list[MilestoneReadiness]


class ProductionPlanDraftedPayload(ContractModel):
    plan_id: str
    feature_id: str
    feature_revision: int
    task_count: int = Field(ge=1)
    confirmed: bool = False


class ProductionPlanApprovedPayload(ContractModel):
    plan_id: str
    approval_id: str


class PlannerEventPayload(ContractModel):
    event_type: str
    event_version: int = 1
    payload: dict[str, Any]


class CreatePlanCommandRequest(ContractModel):
    feature_ref: FeatureSpecReference


class CreatePlanCommandResponse(ContractModel):
    created: bool
    plan: ProductionPlan
    graph: ProductionGraphView
    event_payloads: list[PlannerEventPayload]


class FeatureChangeImpact(ContractModel):
    feature_id: str
    from_revision: int
    to_revision: int
    changed_criterion_ids: list[str]
    affected_task_ids: list[str]
    reasons: dict[str, list[str]]


class PlannerErrorResponse(ContractModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str
    retryable: bool
    suggested_actions: list[str]
