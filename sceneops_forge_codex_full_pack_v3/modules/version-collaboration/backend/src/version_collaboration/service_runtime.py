from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ActionContext, Clock, ExecutionMode, IdFactory, VersionReference
from .diff_engine import FourLayerDiffEngine
from .errors import ErrorCode, VersionCollaborationError
from .ports import (
    ApprovalVerifier,
    ChangeSetDraft,
    ChangeSetGateway,
    EventPublisher,
    GitAdapter,
)
from .repository import ReviewRepository
from .review_models import (
    ActivityRecord,
    ApprovalObservation,
    DomainEvent,
    ReviewSession,
)


class ServiceRuntime:
    """Shared dependencies and invariants for the collaboration use cases."""

    def __init__(
        self,
        *,
        repository: ReviewRepository,
        git: GitAdapter,
        project_roots: dict[str, Path],
        change_sets: ChangeSetGateway,
        approvals: ApprovalVerifier,
        events: EventPublisher,
        clock: Clock,
        ids: IdFactory,
        diff_engine: FourLayerDiffEngine,
    ) -> None:
        self.repository = repository
        self.git = git
        self.project_roots = dict(project_roots)
        self.change_sets = change_sets
        self.approvals = approvals
        self.events = events
        self.clock = clock
        self.ids = ids
        self.diff_engine = diff_engine

    def authorize(self, context: ActionContext, *permissions: str) -> None:
        missing = [item for item in permissions if item not in context.permissions]
        if missing:
            raise VersionCollaborationError(
                ErrorCode.PERMISSION_DENIED,
                "The actor does not have the required collaboration permission.",
                details={"missing_permissions": missing},
            )

    def project_root(self, project_id: str) -> Path:
        try:
            return self.project_roots[project_id]
        except KeyError as error:
            raise VersionCollaborationError(
                ErrorCode.NOT_FOUND,
                "No project root is registered for this project.",
                details={"project_id": project_id},
            ) from error

    def require_current_base(
        self, review: ReviewSession, current: VersionReference
    ) -> None:
        expected = review.target_version
        if self.version_identity(current) != self.version_identity(expected):
            self.raise_stale(expected.commit_id, current.commit_id)

    def require_repository_head(
        self, project_id: str, current: VersionReference
    ) -> None:
        state = self.git.inspect(
            project_id,
            current.repository_id,
            self.project_root(project_id),
        )
        if self.version_identity(state.version) != self.version_identity(current):
            self.raise_stale(current.commit_id, state.version.commit_id)

    @staticmethod
    def version_identity(version: VersionReference) -> tuple[str, str, str, str]:
        return (
            version.provider,
            version.repository_id,
            version.object_format,
            version.commit_id,
        )

    @staticmethod
    def require_review_approvable(review: ReviewSession) -> None:
        blocking = tuple(
            conflict for conflict in review.diff.conflicts if conflict.blocking
        )
        if blocking:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "A review with unresolved blocking conflicts cannot be approved or released.",
                details={
                    "review_id": review.review_id,
                    "conflict_codes": [item.code.value for item in blocking],
                },
                suggested_actions=(
                    "review.session.create",
                    "version.status.refresh",
                ),
            )

    def raise_stale(self, expected: str, actual: str) -> None:
        raise VersionCollaborationError(
            ErrorCode.STALE_BASE,
            "The reviewed base changed; re-plan and re-approve the action.",
            details={"expected_commit": expected, "actual_commit": actual},
            suggested_actions=("version.status.refresh", "review.session.create"),
        )

    def require_binary_locks(
        self, project_id: str, changes: tuple[Any, ...], actor_id: str
    ) -> None:
        active_by_path = {
            lock.path: lock for lock in self.repository.list_active_locks(project_id)
        }
        blocked: list[str] = []
        divergent: list[str] = []
        root = self.project_root(project_id)
        for change in changes:
            if not change.binary:
                continue
            lock = active_by_path.get(change.path)
            if lock is None or lock.owner_id != actor_id:
                blocked.append(change.path)
                continue
            remote = self.git.inspect_lfs_lock(root, change.path)
            if (
                remote is None
                or remote.external_lock_id != lock.external_lock_id
                or remote.path != lock.path
            ):
                divergent.append(change.path)
        if divergent:
            raise VersionCollaborationError(
                ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                "The local binary lock projection no longer matches Git LFS.",
                details={"paths": divergent},
                suggested_actions=("integration.open",),
            )
        if blocked:
            raise VersionCollaborationError(
                ErrorCode.LOCK_CONFLICT,
                "Rollback touches binary assets without matching active locks.",
                details={"paths": blocked},
                suggested_actions=("review.lock.acquire",),
            )

    def persist_verified_approval(
        self,
        review: ReviewSession,
        observation: ApprovalObservation,
        context: ActionContext,
    ) -> ApprovalObservation:
        try:
            existing = self.repository.get_approval(observation.approval_id)
        except VersionCollaborationError as error:
            if error.code != ErrorCode.NOT_FOUND:
                raise
        else:
            if existing != observation:
                raise VersionCollaborationError(
                    ErrorCode.DUPLICATE_RECORD,
                    "Approval identity was already observed with different immutable content.",
                    details={"approval_id": observation.approval_id},
                )
            return existing

        self.repository.append_approval(observation)
        self.audit(
            review,
            "review.approval.recorded",
            observation.approval_id,
            "已记录经核心服务验证的审批。",
            context,
            mode=observation.mode,
        )
        return observation

    def rollback_changeset_draft(
        self, review: ReviewSession, preview: Any, rationale: str
    ) -> ChangeSetDraft:
        return ChangeSetDraft(
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            base_version=review.target_version,
            target_objects=tuple(change.path for change in preview.changes),
            previous_values={"head": preview.current_head},
            proposed_values={"restored_from": preview.target_commit},
            rationale=rationale,
            expected_result=(
                "Create a forward commit whose tracked content matches the approved "
                "target revision."
            ),
            impact_scope=f"{len(preview.changes)} version-controlled paths",
            risk=(
                "high" if any(change.binary for change in preview.changes) else "medium"
            ),
            validation_plan=(
                "refresh Git status",
                "run affected tests",
                "inspect four-layer diff",
            ),
            rollback_plan="Create another reviewed and approved inverse ChangeSet.",
            approval_requirements=("review:approve", "version:rollback"),
        )

    def audit(
        self,
        review: ReviewSession,
        event_type: str,
        subject_id: str,
        summary: str,
        context: ActionContext,
        *,
        payload: dict[str, Any] | None = None,
        mode: ExecutionMode | None = None,
    ) -> None:
        now = self.clock.now()
        observed_mode = mode or context.mode
        activity = ActivityRecord(
            activity_id=self.ids.new("activity"),
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            activity_type=event_type,
            actor_id=context.actor.actor_id,
            subject_id=subject_id,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            summary=summary,
            created_at=now,
            mode=observed_mode,
        )
        self.repository.append_activity(activity)
        event = DomainEvent(
            event_id=self.ids.new("event"),
            event_type=event_type,
            occurred_at=now,
            project_id=review.project_id,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            actor={"type": context.actor.actor_type, "id": context.actor.actor_id},
            mode=observed_mode,
            payload={
                "review_id": review.review_id,
                "subject_id": subject_id,
                **(payload or {}),
            },
        )
        self.events.publish(event)
