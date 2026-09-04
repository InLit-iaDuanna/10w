"""FastAPI composition for the character-animation public network contract."""

from typing import Callable, Optional

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from .animation_models import PreviewArtifact
from .errors import CharacterAnimationError
from .operation_models import (
    ApiError,
    CharacterInspectionRequest,
    CharacterInspectionResult,
    IntegrationStatusResult,
    PreviewCaptureRequest,
    PreviewComparisonRequest,
    PreviewRegressionResult,
    RetargetPreviewRequest,
    RetargetPreviewResult,
    UnityCharacterMapping,
    UnityMappingExecutionRequest,
    UnityMappingProposalRequest,
    UnityMappingProposalResult,
    VersionComparisonRequest,
    VersionComparisonResult,
    VersionReviewRequest,
    VersionReviewResult,
)
from .service import CharacterAnimationService, CharacterAnimationServiceProtocol


ERROR_RESPONSES = {
    400: {"model": ApiError, "description": "Invalid character-animation request"},
    409: {"model": ApiError, "description": "Approval or version conflict"},
    503: {"model": ApiError, "description": "Optional integration unavailable"},
    422: {"model": ApiError, "description": "Schema validation failed"},
}


class CharacterAnimationRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def route_handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError as error:
                body = await _request_body(request)
                request_id = body.get("request_id", "req_validation")
                response = ApiError(
                    code="REQUEST_VALIDATION_FAILED",
                    message="Character-animation request did not match its schema.",
                    details={"errors": jsonable_encoder(error.errors())},
                    request_id=request_id,
                    retryable=False,
                    suggested_actions=["request.correct"],
                )
                return JSONResponse(status_code=422, content=response.model_dump(mode="json"))

        return route_handler


def create_router(service: Optional[CharacterAnimationServiceProtocol] = None) -> APIRouter:
    active_service = service or CharacterAnimationService()
    router = APIRouter(
        prefix="/api/modules/character-animation",
        tags=["character-animation"],
        route_class=CharacterAnimationRoute,
    )

    @router.get("/integrations", response_model=IntegrationStatusResult)
    def integration_status() -> IntegrationStatusResult:
        return active_service.integration_status()

    @router.post("/inspect", response_model=CharacterInspectionResult, responses=ERROR_RESPONSES)
    def inspect(request: CharacterInspectionRequest):
        return _invoke(request.request_id, lambda: active_service.inspect(request))

    @router.post("/versions/compare", response_model=VersionComparisonResult, responses=ERROR_RESPONSES)
    def compare_versions(request: VersionComparisonRequest):
        return _invoke(request.request_id, lambda: active_service.compare_versions(request))

    @router.post("/versions/review", response_model=VersionReviewResult, responses=ERROR_RESPONSES)
    def review_version(request: VersionReviewRequest):
        return _invoke(request.request_id, lambda: active_service.review_version(request))

    @router.post("/previews/capture", response_model=PreviewArtifact, responses=ERROR_RESPONSES)
    def capture_preview(request: PreviewCaptureRequest):
        return _invoke(request.request_id, lambda: active_service.capture_preview(request))

    @router.post("/previews/retarget", response_model=RetargetPreviewResult, responses=ERROR_RESPONSES)
    def preview_retarget(request: RetargetPreviewRequest):
        return _invoke(request.request_id, lambda: active_service.preview_retarget(request))

    @router.post("/previews/compare", response_model=PreviewRegressionResult, responses=ERROR_RESPONSES)
    def compare_previews(request: PreviewComparisonRequest):
        return _invoke(
            request.request_id,
            lambda: active_service.compare_previews(request.baseline, request.candidate),
        )

    @router.post("/unity-mappings/propose", response_model=UnityMappingProposalResult, responses=ERROR_RESPONSES)
    def propose_mapping(request: UnityMappingProposalRequest):
        return _invoke(request.request_id, lambda: active_service.propose_unity_mapping(request))

    @router.post("/unity-mappings/execute", response_model=UnityCharacterMapping, responses=ERROR_RESPONSES)
    def execute_mapping(request: UnityMappingExecutionRequest):
        return _invoke(request.request_id, lambda: active_service.execute_unity_mapping(request))

    return router


def _invoke(request_id: str, operation: Callable[[], object]):
    try:
        return operation()
    except CharacterAnimationError as error:
        status = _status_for_error(error.code)
        body = ApiError(
            code=error.code,
            message=error.message,
            details=error.details,
            request_id=request_id,
            retryable=error.retryable,
            suggested_actions=error.suggested_actions,
        )
        return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def _status_for_error(code: str) -> int:
    if code == "INTEGRATION_OFFLINE":
        return 503
    if code == "APPROVAL_REQUIRED":
        return 409
    return 400


async def _request_body(request: Request):
    try:
        value = await request.json()
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


router = create_router()
