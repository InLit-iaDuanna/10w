"""HTTP boundary for production preparation; host authentication remains authoritative."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from .preparation_models import (
    CandidateDetail, CandidateDetailRequest, CandidateDirectory, CandidateSearchRequest,
    ProductionPreparationRequest, ProductionPreparationResult,
)
from .preparation_repository import PreparationError


class PreparationRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def route(request):
            try:
                return await original(request)
            except PreparationError as error:
                return JSONResponse(status_code=error.status_code,
                    content={"code": error.code, "message": str(error)})
        return route


def create_preparation_router(service) -> APIRouter:
    router = APIRouter(prefix="/api/production-preparation", tags=["production-preparation"],
                       route_class=PreparationRoute)

    @router.post("/prepare", response_model=ProductionPreparationResult)
    async def prepare(body: ProductionPreparationRequest):
        return await service.prepare(body)

    @router.post("/candidates/search", response_model=CandidateDirectory)
    async def search_candidates(body: CandidateSearchRequest):
        return await service.search_candidates(body)

    @router.post("/candidates/detail", response_model=CandidateDetail)
    async def candidate_detail(body: CandidateDetailRequest):
        return await service.candidate_detail(body)

    @router.get("/results/{request_key}", response_model=ProductionPreparationResult)
    def result(request_key: str, project_id: str = Query(min_length=1, max_length=200)):
        return service.result(project_id, request_key)

    return router
