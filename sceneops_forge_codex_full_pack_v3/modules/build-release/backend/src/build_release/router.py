"""FastAPI routes that validate payloads and delegate to the module service."""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from fastapi import APIRouter, HTTPException

from .errors import BuildReleaseError
from .models_build import BuildManifest
from .models_release import (
    Deployment,
    DeploymentPlan,
    FeedbackLink,
    PatchNote,
    ReleaseCandidate,
    RollbackPlan,
)
from .requests import (
    CandidateApprovalRequest,
    CreateCandidateRequest,
    CreateRollbackPlanRequest,
    DeployRequest,
    EditPatchNoteRequest,
    ExecuteRollbackRequest,
    GeneratePatchNoteRequest,
    PrepareDeploymentRequest,
    RecordBuildRequest,
    RetryDeploymentRequest,
)
from .service import BuildReleaseService

T = TypeVar("T")


def create_router(service: Optional[BuildReleaseService] = None) -> APIRouter:
    router = APIRouter(prefix="/build-release", tags=["build-release"])

    def call(operation: Callable[[], T]) -> T:
        if service is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MODULE_NOT_CONFIGURED",
                    "message": "Build Release service adapters are not configured.",
                    "details": {},
                    "retryable": True,
                    "suggested_actions": ["integration.open"],
                },
            )
        try:
            return operation()
        except BuildReleaseError as error:
            status = 404 if error.code == "NOT_FOUND" else 409
            raise HTTPException(
                status_code=status,
                detail={
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                    "retryable": error.retryable,
                    "suggested_actions": (
                        ["run.retry"] if error.retryable else []
                    ),
                },
            ) from error

    @router.post("/builds", response_model=BuildManifest)
    def record_build(request: RecordBuildRequest) -> BuildManifest:
        return call(lambda: service.record_build(request))

    @router.post("/candidates", response_model=ReleaseCandidate)
    def create_candidate(request: CreateCandidateRequest) -> ReleaseCandidate:
        return call(lambda: service.create_candidate(request))

    @router.post("/candidates/{candidate_id}/approvals", response_model=ReleaseCandidate)
    def approve_candidate(
        candidate_id: str, request: CandidateApprovalRequest
    ) -> ReleaseCandidate:
        if request.candidate_id != candidate_id:
            raise HTTPException(status_code=422, detail="candidate_id path/body mismatch")
        return call(lambda: service.approve_candidate(request))

    @router.get("/candidates/{candidate_id}", response_model=ReleaseCandidate)
    def get_candidate(candidate_id: str) -> ReleaseCandidate:
        return call(lambda: service.repository.get_candidate(candidate_id))

    @router.post("/patch-notes", response_model=PatchNote)
    def generate_patch_note(request: GeneratePatchNoteRequest) -> PatchNote:
        return call(lambda: service.generate_patch_note(request))

    @router.patch("/patch-notes/{patch_note_id}", response_model=PatchNote)
    def edit_patch_note(
        patch_note_id: str, request: EditPatchNoteRequest
    ) -> PatchNote:
        if request.patch_note_id != patch_note_id:
            raise HTTPException(status_code=422, detail="patch_note_id path/body mismatch")
        return call(lambda: service.edit_patch_note(request))

    @router.post("/deployments/prepare", response_model=DeploymentPlan)
    def prepare_deployment(request: PrepareDeploymentRequest) -> DeploymentPlan:
        return call(lambda: service.prepare_deployment(request))

    @router.post("/deployments", response_model=Deployment)
    def deploy(request: DeployRequest) -> Deployment:
        return call(lambda: service.deploy(request))

    @router.post("/deployments/{deployment_id}/retry", response_model=Deployment)
    def retry_deployment(
        deployment_id: str, request: RetryDeploymentRequest
    ) -> Deployment:
        if request.deployment_id != deployment_id:
            raise HTTPException(status_code=422, detail="deployment_id path/body mismatch")
        return call(lambda: service.retry_deployment(request))

    @router.get("/deployments/{deployment_id}", response_model=Deployment)
    def get_deployment(deployment_id: str) -> Deployment:
        return call(lambda: service.repository.get_deployment(deployment_id))

    @router.post("/rollback-plans", response_model=RollbackPlan)
    def create_rollback_plan(request: CreateRollbackPlanRequest) -> RollbackPlan:
        return call(lambda: service.create_rollback_plan(request))

    @router.post("/rollback-plans/{plan_id}/execute", response_model=RollbackPlan)
    def execute_rollback(
        plan_id: str, request: ExecuteRollbackRequest
    ) -> RollbackPlan:
        if request.rollback_plan_id != plan_id:
            raise HTTPException(status_code=422, detail="rollback_plan_id path/body mismatch")
        return call(lambda: service.execute_rollback(request))

    @router.post("/feedback-links", response_model=FeedbackLink)
    def add_feedback_link(link: FeedbackLink) -> FeedbackLink:
        return call(lambda: service.add_feedback_link(link))

    return router
