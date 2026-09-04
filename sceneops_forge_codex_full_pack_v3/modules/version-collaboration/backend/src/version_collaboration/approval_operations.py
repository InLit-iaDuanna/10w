from __future__ import annotations

from .base import ActionContext, VersionReference
from .errors import ErrorCode, VersionCollaborationError
from .ports import ApprovalBinding
from .review_models import (
    ApprovalObservation,
    ApprovalOutcome,
    ReleaseEvidenceLink,
)
from .service_runtime import ServiceRuntime


class ApprovalOperations:
    def __init__(self, runtime: ServiceRuntime) -> None:
        self._runtime = runtime

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
        rt = self._runtime
        rt.authorize(context, "review:approve")
        review = rt.repository.get_review(review_id)
        rt.require_current_base(review, current_base)
        rt.require_repository_head(review.project_id, current_base)
        if subject_kind == "review" and (
            subject_id != review.review_id or subject_version != review.revision
        ):
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "A review approval must bind the exact review identity and revision.",
                details={
                    "review_id": review.review_id,
                    "revision": review.revision,
                },
            )
        binding = ApprovalBinding(
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version=subject_version,
            base_version=current_base,
        )
        verified = rt.approvals.verify(approval_id, binding)
        if verified.approval_id != approval_id or verified.binding != binding:
            raise VersionCollaborationError(
                ErrorCode.APPROVAL_REQUIRED,
                "Approval does not match the current review, diff, subject, and base version.",
                details={"approval_id": approval_id},
            )
        if verified.outcome == "approved" and not verified.evidence_ids:
            raise VersionCollaborationError(
                ErrorCode.EVIDENCE_REQUIRED,
                "Approval is missing immutable evidence references.",
                details={"approval_id": approval_id},
            )
        if verified.outcome == "approved" and subject_kind == "review":
            rt.require_review_approvable(review)
            rt.require_binary_locks(
                review.project_id,
                review.diff.file.changes,
                review.creator_id,
            )
        observation = ApprovalObservation(
            approval_id=verified.approval_id,
            review_id=review.review_id,
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version=subject_version,
            approver_id=verified.approver_id,
            outcome=ApprovalOutcome(verified.outcome),
            rationale=verified.rationale,
            base_version=current_base,
            evidence_ids=verified.evidence_ids,
            created_at=verified.approved_at,
            mode=verified.mode,
        )
        return rt.persist_verified_approval(review, observation, context)

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
        rt = self._runtime
        rt.authorize(context, "review:approve")
        review = rt.repository.get_review(review_id)
        rt.require_review_approvable(review)
        approval = rt.repository.get_approval(approval_id)
        if (
            approval.review_id != review_id
            or approval.review_revision_id != review.review_revision_id
            or approval.diff_bundle_id != review.diff.diff_bundle_id
            or approval.subject_id != approved_subject_id
            or approval.subject_version != approved_subject_version
            or approval.outcome != ApprovalOutcome.APPROVED
        ):
            raise VersionCollaborationError(
                ErrorCode.APPROVAL_REQUIRED,
                "Release link requires an approved, exact subject version.",
                details={"approved_subject_id": approved_subject_id},
            )
        linked_evidence = tuple(
            dict.fromkeys((*approval.evidence_ids, *evidence_ids))
        )
        if not linked_evidence:
            raise VersionCollaborationError(
                ErrorCode.EVIDENCE_REQUIRED, "Release link requires evidence."
            )
        for existing in rt.repository.list_release_links(review_id):
            if (
                existing.approval_id == approval_id
                and existing.release_id == release_id
                and existing.approved_subject_id == approved_subject_id
                and existing.approved_subject_version == approved_subject_version
            ):
                if existing.evidence_ids != linked_evidence:
                    raise VersionCollaborationError(
                        ErrorCode.DUPLICATE_RECORD,
                        "Release identity is already linked to different evidence.",
                        details={"link_id": existing.link_id},
                    )
                return existing
        link = ReleaseEvidenceLink(
            link_id=rt.ids.new("releaselink"),
            review_id=review_id,
            approved_subject_id=approved_subject_id,
            approved_subject_version=approved_subject_version,
            approval_id=approval_id,
            release_id=release_id,
            evidence_ids=linked_evidence,
            linked_by=context.actor.actor_id,
            linked_at=rt.clock.now(),
            mode=context.mode,
        )
        rt.repository.append_release_link(link)
        rt.audit(
            review,
            "review.release.linked",
            link.link_id,
            "已将获批变更、证据和发布版本建立审计链接。",
            context,
        )
        return link
