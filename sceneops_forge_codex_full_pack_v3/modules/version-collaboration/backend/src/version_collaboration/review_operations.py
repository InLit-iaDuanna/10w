from __future__ import annotations

from .base import ActionContext
from .diff_engine import combine_modes
from .errors import ErrorCode, VersionCollaborationError
from .review_models import (
    ActivityRecord,
    ApprovalObservation,
    ApprovalOutcome,
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
    ReviewStatus,
)
from .service_runtime import ServiceRuntime


class ReviewOperations:
    def __init__(self, runtime: ServiceRuntime) -> None:
        self._runtime = runtime

    def create_review(
        self, command: CreateReviewCommand, context: ActionContext
    ) -> ReviewSession:
        rt = self._runtime
        rt.authorize(context, "review:create")
        previous = (
            rt.repository.get_review(command.review_id)
            if command.review_id is not None
            else None
        )
        if previous is not None and (
            previous.review_revision_id
            != command.expected_previous_revision_id
            or previous.project_id != command.project_id
            or previous.target_version.repository_id != command.repository_id
        ):
            raise VersionCollaborationError(
                ErrorCode.STALE_BASE,
                "The review session advanced or its project identity changed.",
                details={
                    "review_id": previous.review_id,
                    "expected_previous_revision_id": command.expected_previous_revision_id,
                    "actual_previous_revision_id": previous.review_revision_id,
                },
                suggested_actions=("review.session.refresh",),
            )
        root = rt.project_root(command.project_id)
        state = rt.git.inspect(command.project_id, command.repository_id, root)
        git_diff = rt.git.compare_versions(
            command.repository_id,
            root,
            command.base_commit,
            command.target_commit,
        )
        now = rt.clock.now()
        diff = rt.diff_engine.build(
            diff_bundle_id=rt.ids.new("diff"),
            git_diff=git_diff,
            repository_state=state,
            semantic_before=command.semantic_before,
            semantic_after=command.semantic_after,
            visual_before=command.visual_before,
            visual_after=command.visual_after,
            behavior_before=command.behavior_before,
            behavior_after=command.behavior_after,
            target_ids=command.target_ids,
            active_locks=self.list_active_locks(command.project_id),
            actor_id=context.actor.actor_id,
            sealed_at=now,
        )
        review = ReviewSession(
            review_id=(previous.review_id if previous else rt.ids.new("review")),
            review_revision_id=rt.ids.new("reviewrev"),
            previous_revision_id=(
                previous.review_revision_id if previous else None
            ),
            revision=(previous.revision + 1 if previous else 1),
            project_id=command.project_id,
            title=command.title,
            base_version=git_diff.base,
            target_version=git_diff.target,
            creator_id=context.actor.actor_id,
            status=ReviewStatus.OPEN,
            diff=diff,
            evidence_ids=command.evidence_ids,
            created_at=(previous.created_at if previous else now),
            updated_at=now,
            mode=combine_modes((context.mode, diff.mode)),
        )
        rt.repository.append_review(
            review, command.expected_previous_revision_id
        )
        rt.audit(
            review,
            (
                "review.revision.published"
                if previous
                else "review.session.created"
            ),
            review.review_revision_id if previous else review.review_id,
            (
                "已发布下一不可变评审版本。"
                if previous
                else "已创建不可变评审版本。"
            ),
            context,
            payload={
                "review_revision_id": review.review_revision_id,
                "diff_bundle_id": diff.diff_bundle_id,
            },
            mode=review.mode,
        )
        return review

    def get_review(self, review_id: str) -> ReviewSession:
        return self._runtime.repository.get_review(review_id)

    def get_review_revision(
        self, review_id: str, review_revision_id: str
    ) -> ReviewSession:
        revision = self._runtime.repository.get_review_revision(
            review_revision_id
        )
        if revision.review_id != review_id:
            raise VersionCollaborationError(
                ErrorCode.NOT_FOUND,
                "The requested immutable revision does not belong to this review.",
                details={
                    "review_id": review_id,
                    "review_revision_id": review_revision_id,
                },
            )
        return revision

    def list_comments(self, review_id: str) -> tuple[ReviewComment, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_comments(review_id)

    def list_activity(self, review_id: str) -> tuple[ActivityRecord, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_activity(review_id)

    def list_approvals(
        self, review_id: str
    ) -> tuple[ApprovalObservation, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_approvals(review_id)

    def list_assignments(self, review_id: str) -> tuple[AssignmentRecord, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_assignments(review_id)

    def list_decisions(self, review_id: str) -> tuple[DecisionRecord, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_decisions(review_id)

    def list_release_links(
        self, review_id: str
    ) -> tuple[ReleaseEvidenceLink, ...]:
        self.get_review(review_id)
        return self._runtime.repository.list_release_links(review_id)

    def list_active_locks(
        self, project_id: str
    ) -> tuple[AssetLockRecord, ...]:
        rt = self._runtime
        root = rt.project_root(project_id)
        records = rt.repository.list_active_locks(project_id)
        for record in records:
            remote = rt.git.inspect_lfs_lock(root, record.path)
            if (
                remote is None
                or remote.external_lock_id != record.external_lock_id
                or remote.path != record.path
            ):
                raise VersionCollaborationError(
                    ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                    "The local lock projection no longer matches Git LFS.",
                    details={"lock_id": record.lock_id, "path": record.path},
                    suggested_actions=("integration.open",),
                )
        return records

    def add_comment(
        self,
        review_id: str,
        body: str,
        anchor: CommentAnchor,
        context: ActionContext,
    ) -> ReviewComment:
        rt = self._runtime
        rt.authorize(context, "review:comment")
        revision = rt.repository.get_review_revision(anchor.review_revision_id)
        if (
            revision.review_id != review_id
            or revision.diff.diff_bundle_id != anchor.diff_bundle_id
        ):
            raise VersionCollaborationError(
                ErrorCode.INVALID_COMMENT_ANCHOR,
                "Comment anchor does not belong to this review revision and diff bundle.",
                details={"review_id": review_id},
            )
        known_versions = (revision.base_version, revision.target_version)
        if not any(
            rt.version_identity(anchor.version) == rt.version_identity(version)
            for version in known_versions
        ):
            raise VersionCollaborationError(
                ErrorCode.INVALID_COMMENT_ANCHOR,
                "Comment anchor must retain an exact reviewed Git version.",
                details={"target_id": anchor.target_id},
            )
        comment = ReviewComment(
            comment_id=rt.ids.new("comment"),
            review_id=review_id,
            author_id=context.actor.actor_id,
            body=body,
            anchor=anchor,
            created_at=rt.clock.now(),
            mode=context.mode,
        )
        rt.repository.append_comment(comment)
        rt.audit(
            revision,
            "review.comment.added",
            comment.comment_id,
            "已添加带版本锚点的评论。",
            context,
        )
        return comment

    def record_assignment(
        self,
        review_id: str,
        reviewer_id: str,
        action: AssignmentAction,
        context: ActionContext,
    ) -> AssignmentRecord:
        rt = self._runtime
        rt.authorize(context, "review:assign")
        review = rt.repository.get_review(review_id)
        assignment = AssignmentRecord(
            assignment_id=rt.ids.new("assignment"),
            review_id=review_id,
            reviewer_id=reviewer_id,
            action=action,
            actor_id=context.actor.actor_id,
            created_at=rt.clock.now(),
            mode=context.mode,
        )
        rt.repository.append_assignment(assignment)
        rt.audit(
            review,
            "review.assignment.recorded",
            assignment.assignment_id,
            "已记录评审分配变更。",
            context,
        )
        return assignment

    def record_decision(
        self,
        review_id: str,
        outcome: DecisionOutcome,
        rationale: str,
        evidence_ids: tuple[str, ...],
        context: ActionContext,
    ) -> DecisionRecord:
        rt = self._runtime
        rt.authorize(context, "review:approve")
        review = rt.repository.get_review(review_id)
        if outcome == DecisionOutcome.ACCEPT and not evidence_ids:
            raise VersionCollaborationError(
                ErrorCode.EVIDENCE_REQUIRED,
                "An accepting decision must reference review evidence.",
                suggested_actions=("review.evidence.open",),
            )
        decision = DecisionRecord(
            decision_id=rt.ids.new("decision"),
            review_id=review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            actor_id=context.actor.actor_id,
            outcome=outcome,
            rationale=rationale,
            evidence_ids=evidence_ids,
            created_at=rt.clock.now(),
            mode=context.mode,
        )
        rt.repository.append_decision(decision)
        rt.audit(
            review,
            "review.decision.recorded",
            decision.decision_id,
            "已记录不可变评审决定。",
            context,
        )
        return decision

    def summarize(
        self, review_id: str, review_revision_id: str | None = None
    ) -> ReviewConversationSummary:
        rt = self._runtime
        review = (
            self.get_review_revision(review_id, review_revision_id)
            if review_revision_id
            else rt.repository.get_review(review_id)
        )
        approvals = tuple(
            item
            for item in rt.repository.list_approvals(review_id)
            if item.review_revision_id == review.review_revision_id
            and item.diff_bundle_id == review.diff.diff_bundle_id
            and item.subject_kind == "review"
            and item.subject_id == review.review_id
            and item.subject_version == review.revision
        )
        decisions = tuple(
            item
            for item in rt.repository.list_decisions(review_id)
            if item.review_revision_id == review.review_revision_id
            and item.diff_bundle_id == review.diff.diff_bundle_id
        )
        status = review.status
        signals = tuple(approvals) + tuple(decisions)
        if signals:
            by_subject = {
                self._signal_id(item): item for item in signals
            }
            latest = next(
                (
                    by_subject[item.subject_id]
                    for item in reversed(rt.repository.list_activity(review_id))
                    if item.subject_id in by_subject
                ),
                max(
                    signals,
                    key=lambda item: (item.created_at, self._signal_id(item)),
                ),
            )
            if isinstance(latest, ApprovalObservation):
                status = (
                    ReviewStatus.APPROVED
                    if latest.outcome == ApprovalOutcome.APPROVED
                    else ReviewStatus.CHANGES_REQUESTED
                )
            elif latest.outcome in {
                DecisionOutcome.REQUEST_CHANGES,
                DecisionOutcome.BLOCK,
            }:
                status = ReviewStatus.CHANGES_REQUESTED
        blocking = tuple(
            conflict.message
            for conflict in review.diff.conflicts
            if conflict.blocking
        )
        layers = (
            f"文件：{len(review.diff.file.changes)} 项，{review.diff.file.mode.value}",
            f"语义：{len(review.diff.semantic.changes)} 项，{review.diff.semantic.state.value}",
            f"视觉：{review.diff.visual.changed_samples} 个样本变化，{review.diff.visual.state.value}",
            f"行为：{len(review.diff.behavior.changes)} 项，{review.diff.behavior.state.value}",
        )
        next_actions = (
            ("解决阻塞冲突", "刷新评审版本")
            if blocking
            else ("检查证据", "记录决定或审批")
        )
        return ReviewConversationSummary(
            review_id=review_id,
            title=review.title,
            status=status,
            mode=review.mode,
            headline=f"评审“{review.title}”包含四层可追溯差异。",
            layer_summaries=layers,
            blocking_conflicts=blocking,
            next_actions=next_actions,
        )

    @staticmethod
    def _signal_id(item: ApprovalObservation | DecisionRecord) -> str:
        return (
            item.approval_id
            if isinstance(item, ApprovalObservation)
            else item.decision_id
        )
