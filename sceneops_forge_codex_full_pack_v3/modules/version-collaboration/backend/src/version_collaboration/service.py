from __future__ import annotations

from pathlib import Path
from threading import Event

from .base import (
    ActionContext,
    Clock,
    IdFactory,
    UtcClock,
    UuidIdFactory,
    VersionReference,
)
from .approval_operations import ApprovalOperations
from .diff_engine import FourLayerDiffEngine
from .git_models import GitRepositoryState
from .lock_operations import LockOperations
from .ports import (
    ApprovalVerifier,
    ChangeSetGateway,
    EventPublisher,
    GitAdapter,
)
from .repository import ReviewRepository
from .review_models import (
    ActivityRecord,
    ApprovalObservation,
    AssetLockRecord,
    AssignmentAction,
    AssignmentRecord,
    CommentAnchor,
    CreateReviewCommand,
    DecisionOutcome,
    DecisionRecord,
    ReleaseEvidenceLink,
    ReviewComment,
    ReviewConversationSummary,
    ReviewSession,
    RollbackExecution,
    RollbackProposal,
)
from .review_operations import ReviewOperations
from .rollback_operations import RollbackOperations
from .service_runtime import ServiceRuntime


class VersionCollaborationService:
    """Public facade for version and review collaboration use cases."""

    def __init__(
        self,
        *,
        repository: ReviewRepository,
        git: GitAdapter,
        project_roots: dict[str, Path],
        change_sets: ChangeSetGateway,
        approvals: ApprovalVerifier,
        events: EventPublisher,
        clock: Clock | None = None,
        ids: IdFactory | None = None,
        diff_engine: FourLayerDiffEngine | None = None,
    ) -> None:
        self._runtime = ServiceRuntime(
            repository=repository,
            git=git,
            project_roots=project_roots,
            change_sets=change_sets,
            approvals=approvals,
            events=events,
            clock=clock or UtcClock(),
            ids=ids or UuidIdFactory(),
            diff_engine=diff_engine or FourLayerDiffEngine(),
        )
        self._reviews = ReviewOperations(self._runtime)
        self._approval_operations = ApprovalOperations(self._runtime)
        self._locks = LockOperations(self._runtime)
        self._rollbacks = RollbackOperations(self._runtime)

    def git_status(
        self, project_id: str, repository_id: str
    ) -> GitRepositoryState:
        return self._runtime.git.inspect(
            project_id,
            repository_id,
            self._runtime.project_root(project_id),
        )

    def authorize(self, context: ActionContext, *permissions: str) -> None:
        self._runtime.authorize(context, *permissions)

    def create_review(
        self, command: CreateReviewCommand, context: ActionContext
    ) -> ReviewSession:
        return self._reviews.create_review(command, context)

    def get_review(self, review_id: str) -> ReviewSession:
        return self._reviews.get_review(review_id)

    def get_review_revision(
        self, review_id: str, review_revision_id: str
    ) -> ReviewSession:
        return self._reviews.get_review_revision(review_id, review_revision_id)

    def list_comments(self, review_id: str) -> tuple[ReviewComment, ...]:
        return self._reviews.list_comments(review_id)

    def list_activity(self, review_id: str) -> tuple[ActivityRecord, ...]:
        return self._reviews.list_activity(review_id)

    def list_approvals(self, review_id: str) -> tuple[ApprovalObservation, ...]:
        return self._reviews.list_approvals(review_id)

    def list_assignments(self, review_id: str) -> tuple[AssignmentRecord, ...]:
        return self._reviews.list_assignments(review_id)

    def list_decisions(self, review_id: str) -> tuple[DecisionRecord, ...]:
        return self._reviews.list_decisions(review_id)

    def list_release_links(self, review_id: str) -> tuple[ReleaseEvidenceLink, ...]:
        return self._reviews.list_release_links(review_id)

    def list_active_locks(self, project_id: str) -> tuple[AssetLockRecord, ...]:
        return self._reviews.list_active_locks(project_id)

    def add_comment(
        self,
        review_id: str,
        body: str,
        anchor: CommentAnchor,
        context: ActionContext,
    ) -> ReviewComment:
        return self._reviews.add_comment(review_id, body, anchor, context)

    def record_assignment(
        self,
        review_id: str,
        reviewer_id: str,
        action: AssignmentAction,
        context: ActionContext,
    ) -> AssignmentRecord:
        return self._reviews.record_assignment(
            review_id, reviewer_id, action, context
        )

    def record_decision(
        self,
        review_id: str,
        outcome: DecisionOutcome,
        rationale: str,
        evidence_ids: tuple[str, ...],
        context: ActionContext,
    ) -> DecisionRecord:
        return self._reviews.record_decision(
            review_id, outcome, rationale, evidence_ids, context
        )

    def observe_approval(
        self,
        *,
        review_id: str,
        approval_id: str,
        subject_kind: str,
        subject_id: str,
        subject_version: int,
        current_base: VersionReference,
        context: ActionContext,
    ) -> ApprovalObservation:
        return self._approval_operations.observe_approval(
            review_id=review_id,
            approval_id=approval_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version=subject_version,
            current_base=current_base,
            context=context,
        )

    def acquire_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        repository_id: str,
        resource_id: str,
        path: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        return self._locks.acquire_asset_lock(
            review_id=review_id,
            project_id=project_id,
            repository_id=repository_id,
            resource_id=resource_id,
            path=path,
            context=context,
        )

    def release_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        resource_id: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        return self._locks.release_asset_lock(
            review_id=review_id,
            project_id=project_id,
            resource_id=resource_id,
            context=context,
        )

    def propose_rollback(
        self,
        *,
        review_id: str,
        target_commit: str,
        current_base: VersionReference,
        rationale: str,
        context: ActionContext,
    ) -> RollbackProposal:
        return self._rollbacks.propose_rollback(
            review_id=review_id,
            target_commit=target_commit,
            current_base=current_base,
            rationale=rationale,
            context=context,
        )

    def execute_rollback(
        self,
        *,
        proposal_id: str,
        approval_id: str,
        current_base: VersionReference,
        context: ActionContext,
        cancellation: Event | None = None,
    ) -> RollbackExecution:
        return self._rollbacks.execute_rollback(
            proposal_id=proposal_id,
            approval_id=approval_id,
            current_base=current_base,
            context=context,
            cancellation=cancellation,
        )

    def link_release(
        self,
        *,
        review_id: str,
        approval_id: str,
        approved_subject_id: str,
        approved_subject_version: int,
        release_id: str,
        evidence_ids: tuple[str, ...],
        context: ActionContext,
    ) -> ReleaseEvidenceLink:
        return self._approval_operations.link_release(
            review_id=review_id,
            approval_id=approval_id,
            approved_subject_id=approved_subject_id,
            approved_subject_version=approved_subject_version,
            release_id=release_id,
            evidence_ids=evidence_ids,
            context=context,
        )

    def summarize(
        self, review_id: str, review_revision_id: str | None = None
    ) -> ReviewConversationSummary:
        return self._reviews.summarize(review_id, review_revision_id)
