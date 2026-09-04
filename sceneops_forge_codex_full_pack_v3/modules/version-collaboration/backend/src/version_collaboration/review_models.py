from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from .base import ActionContext, ExecutionMode, FrozenModel, StableId, VersionReference, require_utc
from .diff_models import BehaviorSnapshot, FourLayerDiff, SemanticEntity, VisualCapture
from .git_models import GitRollbackResult, GitVersionDiff, RelativePath, validate_relative_path


class ReviewStatus(str, Enum):
    OPEN = "open"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    CLOSED = "closed"


class ReviewSession(FrozenModel):
    review_id: StableId
    review_revision_id: StableId
    previous_revision_id: Optional[StableId] = None
    revision: int = Field(ge=1)
    project_id: StableId
    title: str = Field(min_length=1, max_length=240)
    base_version: VersionReference
    target_version: VersionReference
    creator_id: StableId
    status: ReviewStatus
    diff: FourLayerDiff
    evidence_ids: tuple[StableId, ...]
    created_at: datetime
    updated_at: datetime
    mode: ExecutionMode

    _created_utc = field_validator("created_at")(require_utc)
    _updated_utc = field_validator("updated_at")(require_utc)


class CreateReviewCommand(FrozenModel):
    review_id: Optional[StableId] = None
    expected_previous_revision_id: Optional[StableId] = None
    project_id: StableId
    repository_id: StableId
    title: str = Field(min_length=1, max_length=240)
    base_commit: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    target_commit: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    semantic_before: Optional[tuple[SemanticEntity, ...]] = None
    semantic_after: Optional[tuple[SemanticEntity, ...]] = None
    visual_before: Optional[VisualCapture] = None
    visual_after: Optional[VisualCapture] = None
    behavior_before: Optional[BehaviorSnapshot] = None
    behavior_after: Optional[BehaviorSnapshot] = None
    target_ids: tuple[StableId, ...] = ()
    evidence_ids: tuple[StableId, ...] = ()

    @model_validator(mode="after")
    def validate_revision_request(self) -> "CreateReviewCommand":
        if (self.review_id is None) != (
            self.expected_previous_revision_id is None
        ):
            raise ValueError(
                "review_id and expected_previous_revision_id must be supplied together"
            )
        return self


class CommentAnchorKind(str, Enum):
    ASSET = "asset"
    SCENE_OBJECT = "scene_object"
    CODE_RANGE = "code_range"
    RENDER = "render"
    BUILD = "build"
    PLAYTEST_STEP = "playtest_step"
    ISSUE = "issue"


class CommentAnchor(FrozenModel):
    kind: CommentAnchorKind
    review_revision_id: StableId
    diff_bundle_id: StableId
    version: VersionReference
    target_id: StableId
    file_path: Optional[RelativePath] = None
    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)

    _validate_path = field_validator("file_path")(lambda value: validate_relative_path(value) if value else value)

    @model_validator(mode="after")
    def validate_code_range(self) -> "CommentAnchor":
        has_range = self.file_path is not None or self.start_line is not None or self.end_line is not None
        if self.kind == CommentAnchorKind.CODE_RANGE:
            if self.file_path is None or self.start_line is None or self.end_line is None:
                raise ValueError("code range anchors require file_path, start_line, and end_line")
            if self.end_line < self.start_line:
                raise ValueError("code range end_line must be at or after start_line")
        elif has_range:
            raise ValueError("only code range anchors may include file and line fields")
        return self


class ReviewComment(FrozenModel):
    comment_id: StableId
    review_id: StableId
    author_id: StableId
    body: str = Field(min_length=1, max_length=20_000)
    anchor: CommentAnchor
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class AssignmentAction(str, Enum):
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


class AssignmentRecord(FrozenModel):
    assignment_id: StableId
    review_id: StableId
    reviewer_id: StableId
    action: AssignmentAction
    actor_id: StableId
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class DecisionOutcome(str, Enum):
    ACCEPT = "accept"
    REQUEST_CHANGES = "request_changes"
    BLOCK = "block"


class DecisionRecord(FrozenModel):
    decision_id: StableId
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    actor_id: StableId
    outcome: DecisionOutcome
    rationale: str = Field(min_length=1, max_length=10_000)
    evidence_ids: tuple[StableId, ...]
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class ApprovalOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalObservation(FrozenModel):
    approval_id: StableId
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    subject_kind: str = Field(pattern=r"^(review|changeset|rollback)$")
    subject_id: StableId
    subject_version: int = Field(ge=1)
    approver_id: StableId
    outcome: ApprovalOutcome
    rationale: str = Field(min_length=1, max_length=10_000)
    base_version: VersionReference
    evidence_ids: tuple[StableId, ...]
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class LockAction(str, Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"


class AssetLockRecord(FrozenModel):
    lock_record_id: StableId
    lock_id: StableId
    external_lock_id: str = Field(min_length=1, max_length=320)
    project_id: StableId
    resource_id: StableId
    path: RelativePath
    branch: str
    owner_id: StableId
    action: LockAction
    base_version: VersionReference
    created_at: datetime
    mode: ExecutionMode

    _path = field_validator("path")(validate_relative_path)
    _utc = field_validator("created_at")(require_utc)


class ChangeSetHistoryEntry(FrozenModel):
    history_id: StableId
    change_set_id: StableId
    change_set_version: int = Field(ge=1)
    review_id: StableId
    revision: int = Field(ge=1)
    state: str = Field(min_length=1, max_length=80)
    base_version: VersionReference
    actor_id: StableId
    evidence_ids: tuple[StableId, ...]
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class ActivityRecord(FrozenModel):
    activity_id: StableId
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    activity_type: str = Field(min_length=1, max_length=160)
    actor_id: StableId
    subject_id: StableId
    correlation_id: StableId
    causation_id: StableId
    summary: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    mode: ExecutionMode

    _utc = field_validator("created_at")(require_utc)


class RollbackProposal(FrozenModel):
    proposal_id: StableId
    operation_id: StableId
    change_set_id: StableId
    change_set_version: int = Field(ge=1)
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    base_version: VersionReference
    target_integration: str = Field(default="git", pattern=r"^git$")
    target_objects: tuple[RelativePath, ...]
    previous_values: dict[str, Any]
    proposed_values: dict[str, Any]
    rationale: str = Field(min_length=1, max_length=10_000)
    expected_result: str = Field(min_length=1, max_length=2000)
    impact_scope: str = Field(min_length=1, max_length=2000)
    risk: str = Field(pattern=r"^(low|medium|high|critical)$")
    validation_plan: tuple[str, ...]
    rollback_plan: str = Field(min_length=1, max_length=2000)
    approval_requirements: tuple[str, ...]
    preview: dict[str, Any]
    created_by: StableId
    created_at: datetime
    mode: ExecutionMode

    _paths = field_validator("target_objects")(
        lambda values: tuple(validate_relative_path(value) for value in values)
    )
    _utc = field_validator("created_at")(require_utc)


class RollbackExecution(FrozenModel):
    execution_id: StableId
    proposal_id: StableId
    review_id: StableId
    approval_id: StableId
    result: GitRollbackResult
    executed_by: StableId
    executed_at: datetime
    mode: ExecutionMode

    _utc = field_validator("executed_at")(require_utc)


class ReleaseEvidenceLink(FrozenModel):
    link_id: StableId
    review_id: StableId
    approved_subject_id: StableId
    approved_subject_version: int = Field(ge=1)
    approval_id: StableId
    release_id: StableId
    evidence_ids: tuple[StableId, ...]
    linked_by: StableId
    linked_at: datetime
    mode: ExecutionMode

    _utc = field_validator("linked_at")(require_utc)


class DomainEvent(FrozenModel):
    event_id: StableId
    event_type: str
    event_version: int = Field(default=1, ge=1)
    occurred_at: datetime
    project_id: StableId
    correlation_id: StableId
    causation_id: StableId
    actor: dict[str, str]
    mode: ExecutionMode
    payload: dict[str, Any]

    _utc = field_validator("occurred_at")(require_utc)


class ReviewConversationSummary(FrozenModel):
    review_id: StableId
    title: str
    status: ReviewStatus
    mode: ExecutionMode
    headline: str
    layer_summaries: tuple[str, ...]
    blocking_conflicts: tuple[str, ...]
    next_actions: tuple[str, ...]


class CreateReviewInputs(FrozenModel):
    command: CreateReviewCommand
    context: ActionContext
    git_diff: GitVersionDiff
