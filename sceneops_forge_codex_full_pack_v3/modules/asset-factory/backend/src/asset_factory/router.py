from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException

from .adapter import BlenderAdapterPort
from .errors import PipelineConflictError, PipelineExecutionError, PipelineNotFoundError
from .schemas import PipelineRequest, PipelineRun
from .service import AssetPipelineService


AdapterResolver = Callable[[PipelineRequest], BlenderAdapterPort]


def create_router(
    service: AssetPipelineService, adapter_resolver: AdapterResolver
) -> APIRouter:
    router = APIRouter(prefix="/v1/asset-pipeline", tags=["asset-factory"])

    @router.post("/runs", response_model=PipelineRun)
    def run_pipeline(request: PipelineRequest) -> PipelineRun:
        try:
            return service.run(request, adapter_resolver(request))
        except PipelineConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)},
            )

    @router.get("/runs/{pipeline_run_id}", response_model=PipelineRun)
    def get_pipeline_run(pipeline_run_id: str) -> PipelineRun:
        try:
            return service.get_run(pipeline_run_id)
        except PipelineNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND"})

    @router.post("/runs/{pipeline_run_id}:cancel", status_code=202)
    def cancel_pipeline_run(pipeline_run_id: str) -> dict:
        try:
            service.cancel(pipeline_run_id)
        except PipelineNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND"})
        return {"pipeline_run_id": pipeline_run_id, "cancellation_requested": True}

    @router.post("/runs/{pipeline_run_id}:retry", response_model=PipelineRun)
    def retry_pipeline_run(
        pipeline_run_id: str, request: PipelineRequest
    ) -> PipelineRun:
        try:
            return service.retry(
                pipeline_run_id, request, adapter_resolver(request)
            )
        except PipelineNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND"})
        except PipelineConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "PIPELINE_RETRY_CONFLICT", "message": str(error)},
            )

    @router.post("/runs/{pipeline_run_id}:rollback", response_model=PipelineRun)
    def rollback_pipeline_run(
        pipeline_run_id: str, request: PipelineRequest
    ) -> PipelineRun:
        try:
            return service.rollback(
                pipeline_run_id, request, adapter_resolver(request)
            )
        except PipelineNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND"})
        except (PipelineConflictError, PipelineExecutionError) as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "PIPELINE_ROLLBACK_CONFLICT", "message": str(error)},
            )

    return router
