"""FastAPI composition entrypoint for Integration Center."""

import re
from typing import Annotated, Callable, Optional

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse

from observability import CorrelationContext

from .contract_validation import STABLE_ID_PATTERN
from .recovery import RecoveryCoordinator
from .recovery_support import RecoveryError
from .schemas import (
    IntegrationDetails,
    IntegrationHealthSnapshot,
    JudgeModeHealthSummary,
    RecoveryCommandRequest,
    RecoveryResult,
    RestartGuidance,
    WorkerSnapshot,
)
from .service import IntegrationCenterService


def _error(
    status_code: int,
    code: str,
    message: str,
    request_id: Optional[str],
    retryable: bool,
    suggested_actions: list,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": {},
            "request_id": (
                request_id
                if request_id and re.fullmatch(STABLE_ID_PATTERN, request_id)
                else "unavailable"
            ),
            "retryable": retryable,
            "suggested_actions": suggested_actions,
        },
    )


def _context(
    project_id: str,
    correlation_id: str,
    causation_id: str,
    run_id: Optional[str],
    job_id: Optional[str],
) -> CorrelationContext:
    return CorrelationContext(
        project_id=project_id,
        run_id=run_id,
        job_id=job_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def create_router(
    service: IntegrationCenterService,
    recovery: RecoveryCoordinator,
    require_permission: Callable[[str], Callable],
    authorize_project: Callable[[str, str], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/integration-center", tags=["integration-center"])

    @router.get(
        "/integrations",
        response_model=list[IntegrationHealthSnapshot],
        dependencies=[Depends(require_permission("integration:read"))],
    )
    def list_integrations(
        project_id: str = Query(pattern=STABLE_ID_PATTERN),
        correlation_id: str = Query(pattern=STABLE_ID_PATTERN),
        causation_id: str = Query(pattern=STABLE_ID_PATTERN),
        run_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
        job_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
    ):
        authorize_project("integration:read", project_id)
        return service.list_health(_context(project_id, correlation_id, causation_id, run_id, job_id))

    @router.get(
        "/integrations/{integration_id}",
        response_model=IntegrationDetails,
        dependencies=[Depends(require_permission("integration:read"))],
    )
    def integration_details(
        integration_id: str = Path(pattern=STABLE_ID_PATTERN),
        project_id: str = Query(pattern=STABLE_ID_PATTERN),
        correlation_id: str = Query(pattern=STABLE_ID_PATTERN),
        causation_id: str = Query(pattern=STABLE_ID_PATTERN),
        run_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
        job_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
        x_request_id: Optional[str] = Header(default=None),
    ):
        authorize_project("integration:read", project_id)
        try:
            return service.details(
                integration_id,
                _context(project_id, correlation_id, causation_id, run_id, job_id),
            )
        except KeyError:
            return _error(404, "INTEGRATION_NOT_FOUND", "未找到指定集成。", x_request_id, False, ["integration.health.refresh"])

    @router.get(
        "/workers",
        response_model=list[WorkerSnapshot],
        dependencies=[Depends(require_permission("job:read"))],
    )
    def list_workers(project_id: str = Query(pattern=STABLE_ID_PATTERN)):
        authorize_project("job:read", project_id)
        return service.list_workers(project_id)

    @router.get(
        "/workers/{worker_id}/restart-guidance",
        response_model=RestartGuidance,
        dependencies=[Depends(require_permission("job:read"))],
    )
    def restart_guidance(
        worker_id: str = Path(pattern=STABLE_ID_PATTERN),
        project_id: str = Query(pattern=STABLE_ID_PATTERN),
    ):
        authorize_project("job:read", project_id)
        return service.restart_guidance(worker_id)

    @router.get(
        "/judge/health",
        response_model=JudgeModeHealthSummary,
        dependencies=[Depends(require_permission("integration:read"))],
    )
    def judge_health(
        project_id: str = Query(pattern=STABLE_ID_PATTERN),
        correlation_id: str = Query(pattern=STABLE_ID_PATTERN),
        causation_id: str = Query(pattern=STABLE_ID_PATTERN),
        run_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
        job_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
    ):
        authorize_project("integration:read", project_id)
        return service.judge_summary(_context(project_id, correlation_id, causation_id, run_id, job_id))

    def recover(
        action: str,
        job_id: str,
        request: RecoveryCommandRequest,
        request_id: Optional[str],
    ):
        try:
            authorize_project("job:operate", request.context.project_id)
            if action == "timeout":
                return recovery.record_timeout(job_id, request.idempotency_key, request.context)
            if action == "cancel":
                return recovery.cancel(job_id, request.idempotency_key, request.context)
            if request.attempt_id is None:
                return _error(422, "ATTEMPT_ID_REQUIRED", "retry/resume 需要新的 attempt_id。", request_id, False, [])
            if action == "retry":
                return recovery.retry(job_id, request.attempt_id, request.idempotency_key, request.context)
            return recovery.resume(job_id, request.attempt_id, request.idempotency_key, request.context)
        except RecoveryError as error:
            status = 404 if error.code == "JOB_NOT_FOUND" else 409
            return _error(status, error.code, str(error), request_id, False, ["integration.open_logs"])

    @router.post(
        "/jobs/{job_id}/timeout",
        response_model=RecoveryResult,
        dependencies=[Depends(require_permission("job:operate"))],
    )
    def timeout_job(
        job_id: Annotated[str, Path(pattern=STABLE_ID_PATTERN)],
        request: RecoveryCommandRequest,
        x_request_id: Optional[str] = Header(default=None),
    ):
        return recover("timeout", job_id, request, x_request_id)

    @router.post(
        "/jobs/{job_id}/cancel",
        response_model=RecoveryResult,
        dependencies=[Depends(require_permission("job:operate"))],
    )
    def cancel_job(
        job_id: Annotated[str, Path(pattern=STABLE_ID_PATTERN)],
        request: RecoveryCommandRequest,
        x_request_id: Optional[str] = Header(default=None),
    ):
        return recover("cancel", job_id, request, x_request_id)

    @router.post(
        "/jobs/{job_id}/retry",
        response_model=RecoveryResult,
        dependencies=[Depends(require_permission("job:operate"))],
    )
    def retry_job(
        job_id: Annotated[str, Path(pattern=STABLE_ID_PATTERN)],
        request: RecoveryCommandRequest,
        x_request_id: Optional[str] = Header(default=None),
    ):
        return recover("retry", job_id, request, x_request_id)

    @router.post(
        "/jobs/{job_id}/resume",
        response_model=RecoveryResult,
        dependencies=[Depends(require_permission("job:operate"))],
    )
    def resume_job(
        job_id: Annotated[str, Path(pattern=STABLE_ID_PATTERN)],
        request: RecoveryCommandRequest,
        x_request_id: Optional[str] = Header(default=None),
    ):
        return recover("resume", job_id, request, x_request_id)

    return router
