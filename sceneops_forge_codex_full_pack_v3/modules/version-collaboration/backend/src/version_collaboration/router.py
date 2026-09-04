from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from .api_models import (
    AcquireLockRequest,
    AddCommentRequest,
    AssignmentRequest,
    DecisionRequest,
    ExecuteRollbackRequest,
    ObserveApprovalRequest,
    ProposeRollbackRequest,
    ReleaseLinkRequest,
    ReleaseLockRequest,
)
from .base import ActionContext
from .errors import ErrorCode, VersionCollaborationError
from .git_models import GitRepositoryState
from .review_models import (
    ActivityRecord,
    ApprovalObservation,
    AssetLockRecord,
    AssignmentRecord,
    CreateReviewCommand,
    DecisionRecord,
    ReleaseEvidenceLink,
    ReviewComment,
    ReviewConversationSummary,
    ReviewSession,
    RollbackExecution,
    RollbackProposal,
)
from .service import VersionCollaborationService


ContextProvider = Callable[[Request], ActionContext]


def create_router(
    service: VersionCollaborationService, context_provider: ContextProvider
) -> APIRouter:
    router = APIRouter(prefix="/api/version-collaboration", tags=["version-collaboration"])

    def action_context(request: Request) -> ActionContext:
        return context_provider(request)

    Context = Annotated[ActionContext, Depends(action_context)]

    @router.get("/projects/{project_id}/git")
    def git_status(project_id: str, repository_id: str, context: Context) -> GitRepositoryState:
        service.authorize(context, "review:read")
        return service.git_status(project_id, repository_id)

    @router.post("/reviews", status_code=201)
    def create_review(command: CreateReviewCommand, context: Context) -> ReviewSession:
        return service.create_review(command, context)

    @router.get("/reviews/{review_id}")
    def get_review(review_id: str, context: Context) -> ReviewSession:
        service.authorize(context, "review:read")
        return service.get_review(review_id)

    @router.get("/reviews/{review_id}/revisions/{review_revision_id}")
    def get_review_revision(
        review_id: str, review_revision_id: str, context: Context
    ) -> ReviewSession:
        service.authorize(context, "review:read")
        return service.get_review_revision(review_id, review_revision_id)

    @router.get("/reviews/{review_id}/summary")
    def get_summary(review_id: str, context: Context) -> ReviewConversationSummary:
        service.authorize(context, "review:read")
        return service.summarize(review_id)

    @router.get("/reviews/{review_id}/revisions/{review_revision_id}/summary")
    def get_revision_summary(
        review_id: str, review_revision_id: str, context: Context
    ) -> ReviewConversationSummary:
        service.authorize(context, "review:read")
        return service.summarize(review_id, review_revision_id)

    @router.get("/reviews/{review_id}/activity")
    def get_activity(review_id: str, context: Context) -> tuple[ActivityRecord, ...]:
        service.authorize(context, "review:read")
        return service.list_activity(review_id)

    @router.get("/reviews/{review_id}/comments")
    def get_comments(review_id: str, context: Context) -> tuple[ReviewComment, ...]:
        service.authorize(context, "review:read")
        return service.list_comments(review_id)

    @router.post("/reviews/{review_id}/comments", status_code=201)
    def add_comment(
        review_id: str, body: AddCommentRequest, context: Context
    ) -> ReviewComment:
        return service.add_comment(review_id, body.body, body.anchor, context)

    @router.post("/reviews/{review_id}/assignments", status_code=201)
    def record_assignment(
        review_id: str, body: AssignmentRequest, context: Context
    ) -> AssignmentRecord:
        return service.record_assignment(review_id, body.reviewer_id, body.action, context)

    @router.post("/reviews/{review_id}/decisions", status_code=201)
    def record_decision(
        review_id: str, body: DecisionRequest, context: Context
    ) -> DecisionRecord:
        return service.record_decision(
            review_id, body.outcome, body.rationale, body.evidence_ids, context
        )

    @router.post("/reviews/{review_id}/approvals", status_code=201)
    def observe_approval(
        review_id: str, body: ObserveApprovalRequest, context: Context
    ) -> ApprovalObservation:
        return service.observe_approval(
            review_id=review_id,
            approval_id=body.approval_id,
            subject_kind=body.subject_kind,
            subject_id=body.subject_id,
            subject_version=body.subject_version,
            current_base=body.current_base,
            context=context,
        )

    @router.get("/reviews/{review_id}/approvals")
    def get_approvals(review_id: str, context: Context) -> tuple[ApprovalObservation, ...]:
        service.authorize(context, "review:read")
        return service.list_approvals(review_id)

    @router.get("/reviews/{review_id}/assignments")
    def get_assignments(
        review_id: str, context: Context
    ) -> tuple[AssignmentRecord, ...]:
        service.authorize(context, "review:read")
        return service.list_assignments(review_id)

    @router.get("/reviews/{review_id}/decisions")
    def get_decisions(
        review_id: str, context: Context
    ) -> tuple[DecisionRecord, ...]:
        service.authorize(context, "review:read")
        return service.list_decisions(review_id)

    @router.get("/reviews/{review_id}/release-links")
    def get_release_links(
        review_id: str, context: Context
    ) -> tuple[ReleaseEvidenceLink, ...]:
        service.authorize(context, "review:read")
        return service.list_release_links(review_id)

    @router.get("/projects/{project_id}/locks")
    def get_active_locks(
        project_id: str, context: Context
    ) -> tuple[AssetLockRecord, ...]:
        service.authorize(context, "review:read")
        return service.list_active_locks(project_id)

    @router.post("/locks/acquire", status_code=201)
    def acquire_lock(body: AcquireLockRequest, context: Context) -> AssetLockRecord:
        return service.acquire_asset_lock(
            review_id=body.review_id,
            project_id=body.project_id,
            repository_id=body.repository_id,
            resource_id=body.resource_id,
            path=body.path,
            context=context,
        )

    @router.post("/locks/release", status_code=201)
    def release_lock(body: ReleaseLockRequest, context: Context) -> AssetLockRecord:
        return service.release_asset_lock(
            review_id=body.review_id,
            project_id=body.project_id,
            resource_id=body.resource_id,
            context=context,
        )

    @router.post("/rollbacks/propose", status_code=201)
    def propose_rollback(
        body: ProposeRollbackRequest, context: Context
    ) -> RollbackProposal:
        return service.propose_rollback(
            review_id=body.review_id,
            target_commit=body.target_commit,
            current_base=body.current_base,
            rationale=body.rationale,
            context=context,
        )

    @router.post("/rollbacks/execute", status_code=201)
    def execute_rollback(
        body: ExecuteRollbackRequest, context: Context
    ) -> RollbackExecution:
        return service.execute_rollback(
            proposal_id=body.proposal_id,
            approval_id=body.approval_id,
            current_base=body.current_base,
            context=context,
        )

    @router.post("/release-links", status_code=201)
    def link_release(
        body: ReleaseLinkRequest, context: Context
    ) -> ReleaseEvidenceLink:
        return service.link_release(
            review_id=body.review_id,
            approval_id=body.approval_id,
            approved_subject_id=body.approved_subject_id,
            approved_subject_version=body.approved_subject_version,
            release_id=body.release_id,
            evidence_ids=body.evidence_ids,
            context=context,
        )

    return router


async def version_collaboration_exception_handler(
    request: Request, error: VersionCollaborationError
) -> JSONResponse:
    status = {
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.GIT_OFFLINE: 503,
        ErrorCode.GIT_TIMEOUT: 504,
        ErrorCode.GIT_CANCELLED: 409,
        ErrorCode.PATH_OUTSIDE_PROJECT: 403,
        ErrorCode.PERMISSION_DENIED: 403,
        ErrorCode.INVALID_COMMENT_ANCHOR: 422,
        ErrorCode.INCOMPATIBLE_SCHEMA: 422,
    }.get(error.code, 409)
    request_id = request.headers.get("x-request-id", "request_unavailable")
    return JSONResponse(status_code=status, content=error.as_dict(request_id))
