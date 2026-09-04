from __future__ import annotations

from threading import Event

from .base import ActionContext, VersionReference
from .diff_engine import combine_modes
from .errors import ErrorCode, VersionCollaborationError
from .git_models import GitRollbackCommand, RollbackPreview
from .ports import ApprovalBinding
from .review_models import (
    ApprovalObservation,
    ApprovalOutcome,
    ChangeSetHistoryEntry,
    RollbackExecution,
    RollbackProposal,
)
from .service_runtime import ServiceRuntime


class RollbackOperations:
    def __init__(self, runtime: ServiceRuntime) -> None:
        self._runtime = runtime

    def propose_rollback(
        self,
        *,
        review_id: str,
        target_commit: str,
        current_base: VersionReference,
        rationale: str,
        context: ActionContext,
    ) -> RollbackProposal:
        rt = self._runtime
        rt.authorize(context, "version:rollback")
        review = rt.repository.get_review(review_id)
        rt.require_current_base(review, current_base)
        rt.require_repository_head(review.project_id, current_base)
        root = rt.project_root(review.project_id)

        proposal_id = rt.ids.new("rollback")
        command = GitRollbackCommand(
            operation_id=rt.ids.new("operation"),
            proposal_id=proposal_id,
            approval_id="approval_pending",
            expected_head=current_base.commit_id,
            target_commit=target_commit,
            commit_message=f"SceneOps rollback proposal {proposal_id}",
        )
        preview = rt.git.dry_run_rollback(root, command)
        if preview.blocked_reasons:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "Rollback dry-run is blocked.",
                details={"blocked_reasons": list(preview.blocked_reasons)},
                suggested_actions=("version.status.refresh",),
            )
        if not preview.changes:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "Rollback target already matches the current tracked content.",
                details={"target_commit": target_commit},
                suggested_actions=("version.status.refresh",),
            )
        rt.require_binary_locks(
            review.project_id, preview.changes, context.actor.actor_id
        )
        change_set = rt.change_sets.create(
            rt.rollback_changeset_draft(review, preview, rationale)
        )
        now = rt.clock.now()
        proposal = RollbackProposal(
            proposal_id=proposal_id,
            operation_id=command.operation_id,
            change_set_id=change_set.change_set_id,
            change_set_version=change_set.version,
            review_id=review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            base_version=current_base,
            target_objects=tuple(change.path for change in preview.changes),
            previous_values={"head": preview.current_head},
            proposed_values={"restored_from": preview.target_commit},
            rationale=rationale,
            expected_result=(
                "创建一个恢复到所选版本内容的新提交，不改写既有 Git 历史。"
            ),
            impact_scope=f"{len(preview.changes)} 个受版本控制的路径",
            risk=(
                "high" if any(change.binary for change in preview.changes) else "medium"
            ),
            validation_plan=("重新读取 Git 状态", "运行受影响模块测试", "检查四层 diff"),
            rollback_plan="若验证失败，为本次恢复提交创建新的审批回滚提案。",
            approval_requirements=("review:approve", "version:rollback"),
            preview=preview.model_dump(mode="json"),
            created_by=context.actor.actor_id,
            created_at=now,
            mode=combine_modes((context.mode, preview.mode, change_set.mode)),
        )
        rt.repository.append_rollback_proposal(proposal)
        rt.repository.append_changeset_history(
            ChangeSetHistoryEntry(
                history_id=rt.ids.new("changesethistory"),
                change_set_id=change_set.change_set_id,
                change_set_version=change_set.version,
                review_id=review_id,
                revision=1,
                state=change_set.state,
                base_version=current_base,
                actor_id=context.actor.actor_id,
                evidence_ids=review.evidence_ids,
                created_at=now,
                mode=change_set.mode,
            )
        )
        rt.audit(
            review,
            "review.rollback.proposed",
            proposal_id,
            "已创建待审批的回滚 ChangeSet。",
            context,
            mode=proposal.mode,
        )
        return proposal

    def execute_rollback(
        self,
        *,
        proposal_id: str,
        approval_id: str,
        current_base: VersionReference,
        context: ActionContext,
        cancellation: Event | None = None,
    ) -> RollbackExecution:
        rt = self._runtime
        rt.authorize(context, "review:approve", "version:rollback")
        proposal = rt.repository.get_rollback_proposal(proposal_id)
        review = rt.repository.get_review_revision(
            proposal.review_revision_id
        )
        if (
            review.review_id != proposal.review_id
            or review.diff.diff_bundle_id != proposal.diff_bundle_id
        ):
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "The rollback proposal does not match its immutable review revision.",
                details={
                    "proposal_review_revision_id": proposal.review_revision_id,
                    "proposal_diff_bundle_id": proposal.diff_bundle_id,
                },
            )
        rt.require_current_base(review, current_base)
        if rt.version_identity(proposal.base_version) != rt.version_identity(
            current_base
        ):
            rt.raise_stale(
                proposal.base_version.commit_id,
                current_base.commit_id,
            )
        existing = rt.repository.get_rollback_execution(proposal_id)
        if existing is not None:
            if (
                existing.approval_id != approval_id
                or rt.version_identity(proposal.base_version)
                != rt.version_identity(current_base)
            ):
                raise VersionCollaborationError(
                    ErrorCode.DUPLICATE_RECORD,
                    "Rollback was already executed with a different immutable request.",
                    details={"proposal_id": proposal_id},
                )
            return existing
        latest_review = rt.repository.get_review(proposal.review_id)
        if latest_review.review_revision_id != proposal.review_revision_id:
            raise VersionCollaborationError(
                ErrorCode.STALE_BASE,
                "The rollback proposal belongs to a superseded review revision.",
                details={
                    "proposal_review_revision_id": proposal.review_revision_id,
                    "current_review_revision_id": latest_review.review_revision_id,
                },
                suggested_actions=("review.rollback.propose",),
            )
        binding = ApprovalBinding(
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            subject_kind="rollback",
            subject_id=proposal.proposal_id,
            subject_version=proposal.change_set_version,
            base_version=current_base,
        )
        verified = rt.approvals.verify(approval_id, binding)
        if (
            verified.approval_id != approval_id
            or verified.binding != binding
            or verified.outcome != "approved"
        ):
            raise VersionCollaborationError(
                ErrorCode.APPROVAL_REQUIRED,
                "Rollback requires an exact approved binding for this proposal and base.",
                details={"proposal_id": proposal_id, "approval_id": approval_id},
            )
        if not verified.evidence_ids:
            raise VersionCollaborationError(
                ErrorCode.EVIDENCE_REQUIRED,
                "Rollback approval must include evidence.",
                details={"approval_id": approval_id},
            )
        observation = ApprovalObservation(
            approval_id=verified.approval_id,
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            subject_kind=binding.subject_kind,
            subject_id=binding.subject_id,
            subject_version=binding.subject_version,
            approver_id=verified.approver_id,
            outcome=ApprovalOutcome(verified.outcome),
            rationale=verified.rationale,
            base_version=binding.base_version,
            evidence_ids=verified.evidence_ids,
            created_at=verified.approved_at,
            mode=verified.mode,
        )
        rt.persist_verified_approval(review, observation, context)
        approved_preview = RollbackPreview.model_validate(proposal.preview)
        rt.require_binary_locks(
            review.project_id, approved_preview.changes, context.actor.actor_id
        )
        command = GitRollbackCommand(
            operation_id=proposal.operation_id,
            proposal_id=proposal_id,
            approval_id=approval_id,
            expected_head=current_base.commit_id,
            target_commit=proposal.proposed_values["restored_from"],
            commit_message=f"SceneOps approved rollback {proposal_id}",
        )
        with rt.repository.guard_review_revision(
            review.review_id, review.review_revision_id
        ):
            git_result = rt.git.execute_rollback(
                rt.project_root(review.project_id),
                command,
                cancellation=cancellation,
            )
        mode = combine_modes((context.mode, verified.mode, git_result.mode))
        execution = RollbackExecution(
            execution_id=rt.ids.new("rollbackexec"),
            proposal_id=proposal_id,
            review_id=review.review_id,
            approval_id=approval_id,
            result=git_result,
            executed_by=context.actor.actor_id,
            executed_at=rt.clock.now(),
            mode=mode,
        )
        rt.repository.append_rollback_execution(execution)
        rt.repository.append_changeset_history(
            ChangeSetHistoryEntry(
                history_id=rt.ids.new("changesethistory"),
                change_set_id=proposal.change_set_id,
                change_set_version=proposal.change_set_version,
                review_id=review.review_id,
                revision=2,
                state="executed",
                base_version=current_base,
                actor_id=context.actor.actor_id,
                evidence_ids=verified.evidence_ids,
                created_at=execution.executed_at,
                mode=mode,
            )
        )
        rt.audit(
            review,
            "review.rollback.executed",
            execution.execution_id,
            "已执行获批回滚并创建新提交。",
            context,
            mode=execution.mode,
        )
        return execution
