from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from .errors import PlannerDomainError
from .fixtures import (
    UnavailableApprovalProvider,
    UnavailableExecutionContextProvider,
    UnavailableFeatureSpecProvider,
    UnavailableRunEvidenceProvider,
)
from .graph import build_graph_view
from .models import CreatePlanCommandRequest, CreatePlanCommandResponse, PlannerErrorResponse, ProductionGraphView, ProductionPlan
from .repository import InMemoryProductionPlanRepository
from .service import ProductionPlannerService
from .ports import PlannerExecutionContextProvider


def create_router(
    service: ProductionPlannerService,
    contexts: PlannerExecutionContextProvider,
) -> APIRouter:
    router = APIRouter(prefix="/v1/production-planner", tags=["production-planner"])

    @router.post(
        "/commands/production.plan.create",
        response_model=CreatePlanCommandResponse,
        responses={409: {"model": PlannerErrorResponse}, 503: {"model": PlannerErrorResponse}},
    )
    def create_plan(request: CreatePlanCommandRequest) -> CreatePlanCommandResponse:
        return service.create_plan(request, contexts.get_context())

    @router.get("/plans/{plan_id}", response_model=ProductionPlan)
    def get_plan(plan_id: str) -> ProductionPlan:
        return service.get_plan(plan_id)

    @router.get("/plans/{plan_id}/graph", response_model=ProductionGraphView)
    def get_graph(plan_id: str) -> ProductionGraphView:
        return build_graph_view(service.get_plan(plan_id))

    return router


def create_app(
    service: ProductionPlannerService | None = None,
    contexts: PlannerExecutionContextProvider | None = None,
) -> FastAPI:
    app = FastAPI(title="SceneOps Forge Production Planner", version="0.1.0")
    planner_service = service or ProductionPlannerService(
        InMemoryProductionPlanRepository(),
        UnavailableFeatureSpecProvider(),
        UnavailableRunEvidenceProvider(),
        UnavailableApprovalProvider(),
    )
    context_provider = contexts or UnavailableExecutionContextProvider()
    app.include_router(create_router(planner_service, context_provider))

    @app.exception_handler(PlannerDomainError)
    async def planner_error_handler(request: Request, error: PlannerDomainError) -> JSONResponse:
        unavailable = error.code.endswith("UNAVAILABLE")
        status_code = 503 if unavailable else 404 if error.code.endswith("NOT_FOUND") else 409
        response = PlannerErrorResponse(
            code=error.code,
            message=error.message,
            details=error.details,
            request_id=request.headers.get("x-request-id", "request:unassigned"),
            retryable=error.retryable,
            suggested_actions=error.suggested_actions,
        )
        return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))

    return app


app = create_app()
