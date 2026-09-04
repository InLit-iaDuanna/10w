"""FastAPI composition surface; business behavior stays in UnityEngineService."""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from .contracts import ChangePreview, CommandRequest, CommandResult, ExecutionContext
from .errors import UnityIntegrationError
from .service import UnityEngineService


def create_router(
    service: UnityEngineService,
    context_provider: Callable[[], ExecutionContext],
) -> APIRouter:
    router = APIRouter(prefix="/api/modules/engine-unity", tags=["engine-unity"])

    @router.get("/capabilities")
    def capabilities():
        return service.adapter.capabilities()

    @router.post("/commands/preview", response_model=ChangePreview)
    def preview(
        request: CommandRequest,
        context: ExecutionContext = Depends(context_provider),
    ):
        try:
            return service.preview(request, context)
        except UnityIntegrationError as error:
            return _error_response(error)

    @router.post("/commands/execute", response_model=CommandResult)
    def execute(
        request: CommandRequest,
        context: ExecutionContext = Depends(context_provider),
    ) -> CommandResult:
        return service.execute(request, context)

    return router


def _error_response(error: UnityIntegrationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": error.code.value,
            "message": str(error),
            "details": error.details,
            "retryable": error.retryable,
            "suggested_actions": ["integration.open", "run.retry"]
            if error.retryable
            else [],
        },
    )
