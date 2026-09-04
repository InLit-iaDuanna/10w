"""FastAPI composition entrypoint for observability."""

import re
from typing import Callable, Dict, Iterable, Optional, Protocol

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse

from .diagnostics import DiagnosticBundleRequest, DiagnosticBundleService
from .gateway import CursorExpiredError, DuplicateEventConflict, ObservabilityGateway, SearchFieldNotAllowed
from .schemas import STABLE_ID_PATTERN, EventBatch, ExecutionMode, LogPage, LogQuery, ProgressEvent, StructuredLogEvent


class ObservabilityAccessPort(Protocol):
    """Project and producer authorization supplied by application composition."""

    def authorize_project(self, permission_id: str, project_id: str) -> None:
        ...

    def authorize_producer(
        self,
        project_id: str,
        source_module: str,
        source_tool: Optional[str],
        mode: ExecutionMode,
    ) -> None:
        ...


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


def create_router(
    gateway: ObservabilityGateway,
    require_permission: Callable[[str], Callable],
    access: ObservabilityAccessPort,
    diagnostics: Optional[DiagnosticBundleService] = None,
    health_provider: Optional[Callable[[str], Iterable[Dict]]] = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/observability", tags=["observability"])
    bundle_service = diagnostics or DiagnosticBundleService()

    @router.post(
        "/logs",
        response_model=StructuredLogEvent,
        status_code=201,
        dependencies=[Depends(require_permission("observability:write"))],
    )
    def publish_log(event: StructuredLogEvent, x_request_id: Optional[str] = Header(default=None)):
        try:
            access.authorize_project("observability:write", event.context.project_id)
            access.authorize_producer(
                event.context.project_id,
                event.source_module,
                event.source_tool,
                event.mode,
            )
            return gateway.publish_log(event)
        except DuplicateEventConflict as error:
            return _error(409, "EVENT_ID_CONFLICT", str(error), x_request_id, False, ["event.use_new_id"])
        except SearchFieldNotAllowed as error:
            return _error(422, "LOG_FIELD_NOT_ALLOWED", str(error), x_request_id, False, ["log.remove_field"])

    @router.post(
        "/progress",
        response_model=ProgressEvent,
        status_code=201,
        dependencies=[Depends(require_permission("observability:write"))],
    )
    def publish_progress(event: ProgressEvent, x_request_id: Optional[str] = Header(default=None)):
        try:
            access.authorize_project("observability:write", event.context.project_id)
            access.authorize_producer(
                event.context.project_id,
                event.source_module,
                None,
                event.mode,
            )
            return gateway.publish_progress(event)
        except DuplicateEventConflict as error:
            return _error(409, "EVENT_ID_CONFLICT", str(error), x_request_id, False, ["event.use_new_id"])
        except SearchFieldNotAllowed as error:
            return _error(422, "LOG_FIELD_NOT_ALLOWED", str(error), x_request_id, False, ["log.remove_field"])

    @router.get(
        "/events",
        response_model=EventBatch,
        dependencies=[Depends(require_permission("observability:read"))],
    )
    def reconnect_events(
        project_id: str = Query(pattern=STABLE_ID_PATTERN),
        cursor: Optional[str] = Query(default=None, max_length=200),
        limit: int = Query(default=500, ge=1, le=2000),
        x_request_id: Optional[str] = Header(default=None),
    ):
        try:
            access.authorize_project("observability:read", project_id)
            return gateway.events_after(project_id, cursor, limit)
        except CursorExpiredError as error:
            return _error(
                409,
                "EVENT_CURSOR_EXPIRED",
                str(error),
                x_request_id,
                False,
                ["observability.logs.search", "event.reconnect_from_current"],
            )
        except ValueError as error:
            return _error(422, "EVENT_CURSOR_INVALID", str(error), x_request_id, False, ["event.reconnect_from_current"])

    @router.post(
        "/logs/search",
        response_model=LogPage,
        dependencies=[Depends(require_permission("observability:read"))],
    )
    def search_logs(query: LogQuery, x_request_id: Optional[str] = Header(default=None)):
        try:
            access.authorize_project("observability:read", query.project_id)
            return gateway.query_logs(query)
        except SearchFieldNotAllowed as error:
            return _error(422, "LOG_FIELD_NOT_ALLOWED", str(error), x_request_id, False, ["log.remove_filter"])

    @router.post(
        "/diagnostics",
        dependencies=[Depends(require_permission("observability:export"))],
    )
    def create_diagnostic_bundle(request: DiagnosticBundleRequest) -> Response:
        access.authorize_project("observability:export", request.project_id)
        page = gateway.query_logs(
            LogQuery(
                project_id=request.project_id,
                correlation_id=request.correlation_id,
                limit=2000,
            )
        )
        health_snapshots = health_provider(request.project_id) if health_provider else ()
        result = bundle_service.create(
            request,
            page.items,
            health_snapshots=health_snapshots,
            total_available=page.total,
        )
        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={
                "Content-Disposition": 'attachment; filename="%s"' % result.filename,
                "X-SceneOps-Execution-Mode": result.mode.value,
            },
        )

    return router
