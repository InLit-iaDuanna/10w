from __future__ import annotations

from pydantic import Field

from .base import FrozenModel, StableId, VersionReference
from .review_models import (
    AssignmentAction,
    CommentAnchor,
    DecisionOutcome,
)


class AddCommentRequest(FrozenModel):
    body: str = Field(min_length=1, max_length=20_000)
    anchor: CommentAnchor


class AssignmentRequest(FrozenModel):
    reviewer_id: StableId
    action: AssignmentAction


class DecisionRequest(FrozenModel):
    outcome: DecisionOutcome
    rationale: str = Field(min_length=1, max_length=10_000)
    evidence_ids: tuple[StableId, ...] = ()


class ObserveApprovalRequest(FrozenModel):
    approval_id: StableId
    subject_kind: str = Field(pattern=r"^(review|changeset|rollback)$")
    subject_id: StableId
    subject_version: int = Field(ge=1)
    current_base: VersionReference


class AcquireLockRequest(FrozenModel):
    review_id: StableId
    project_id: StableId
    repository_id: StableId
    resource_id: StableId
    path: str = Field(min_length=1, max_length=4096)


class ReleaseLockRequest(FrozenModel):
    review_id: StableId
    project_id: StableId
    resource_id: StableId


class ProposeRollbackRequest(FrozenModel):
    review_id: StableId
    target_commit: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    current_base: VersionReference
    rationale: str = Field(min_length=1, max_length=10_000)


class ExecuteRollbackRequest(FrozenModel):
    proposal_id: StableId
    approval_id: StableId
    current_base: VersionReference


class ReleaseLinkRequest(FrozenModel):
    review_id: StableId
    approval_id: StableId
    approved_subject_id: StableId
    approved_subject_version: int = Field(ge=1)
    release_id: StableId
    evidence_ids: tuple[StableId, ...] = ()
