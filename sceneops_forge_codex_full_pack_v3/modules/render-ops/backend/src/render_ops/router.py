"""Thin FastAPI surface for Render Ops planning and manifest validation."""

from fastapi import APIRouter

from .schemas import (
    ManifestSummary,
    RenderJob,
    RenderJobPlanRequest,
    RenderManifest,
    summarize_manifest,
)
from .service import RenderOpsService


router = APIRouter(prefix="/api/v1/render", tags=["render-ops"])
service = RenderOpsService()


@router.post("/jobs/plan", response_model=RenderJob, operation_id="planRenderJob")
def plan_render_job(request: RenderJobPlanRequest) -> RenderJob:
    request = RenderJobPlanRequest.model_validate(request.model_dump(mode="python"))
    existing = {item.pass_type: item for item in request.existing_aovs}
    return service.create_job(
        job_id=request.job_id,
        brief=request.brief,
        recipe=request.recipe,
        dependency_snapshot=request.dependency_snapshot,
        existing_aovs=existing,
        previous_snapshot=request.previous_snapshot,
        execution_mode=request.execution_mode,
        created_at=request.requested_at,
    )


@router.post(
    "/manifests/validate",
    response_model=ManifestSummary,
    operation_id="validateRenderManifest",
)
def validate_render_manifest(manifest: RenderManifest) -> ManifestSummary:
    manifest = RenderManifest.model_validate(manifest.model_dump(mode="python"))
    return summarize_manifest(manifest)
