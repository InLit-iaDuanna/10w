from __future__ import annotations

from typing import Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field, TypeAdapter, ValidationError

from .backpin import BackpinReviewError
from .changesets import ChangeSetProposalError
from .ports import AdapterError
from .regression import RegressionError
from .restoration import RestoreIssueCommand
from .schemas import (
    ChangeSetProposal,
    CancelRunResult,
    Issue,
    JsonScalar,
    PlaytestRun,
    RegressionComparison,
    RunId,
    RunRequest,
    StableId,
    StrictModel,
)
from .service import AIPlaytestService


class ErrorBody(StrictModel):
    code: str
    message: str
    details: Dict[str, JsonScalar] = Field(default_factory=dict)
    request_id: str = Field(min_length=1)
    retryable: bool
    suggested_actions: List[StableId] = Field(min_length=1)


class RegressionRequest(StrictModel):
    comparison_id: StableId
    baseline_run_id: RunId
    candidate_run_id: RunId


class ChangeProposalRequest(StrictModel):
    proposal_id: StableId
    base_version: str = Field(min_length=1)
    target_integration: str = Field(min_length=1)
    previous_values: Dict[str, JsonScalar]
    proposed_values: Dict[str, JsonScalar]
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: str = Field(min_length=1)
    risk: Literal["low", "medium", "high", "critical"]
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_requirements: List[str] = Field(min_length=1)


class BackpinReviewRequest(StrictModel):
    decision: Literal["confirm", "reject"]


class AuthenticatedActorRequiredError(ValueError):
    code = "AUTHENTICATED_ACTOR_REQUIRED"


def create_router(service: AIPlaytestService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/playtests", tags=["ai-playtest"])
    error_responses = {
        401: {"model": ErrorBody},
        404: {"model": ErrorBody},
        409: {"model": ErrorBody},
        503: {"model": ErrorBody},
    }

    @router.post("/runs", response_model=PlaytestRun, responses=error_responses)
    def run_playtest(
        request: RunRequest, http_request: Request
    ) -> PlaytestRun | JSONResponse:
        try:
            return service.run(request)
        except AdapterError as error:
            return _error_response(error, _request_id(http_request))

    @router.post("/runs/{run_id}/cancel", response_model=CancelRunResult)
    def cancel_run(run_id: RunId) -> CancelRunResult:
        return service.cancel(run_id)

    @router.post(
        "/regressions",
        response_model=RegressionComparison,
        responses=error_responses,
    )
    def compare_runs(
        request: RegressionRequest, http_request: Request
    ) -> RegressionComparison | JSONResponse:
        try:
            return service.compare(
                request.comparison_id,
                request.baseline_run_id,
                request.candidate_run_id,
            )
        except (RegressionError, KeyError) as error:
            return _error_response(error, _request_id(http_request))

    @router.get(
        "/issues/{issue_id}/restore",
        response_model=RestoreIssueCommand,
        responses=error_responses,
    )
    def restore_issue(
        issue_id: StableId, http_request: Request
    ) -> RestoreIssueCommand | JSONResponse:
        try:
            return service.restore_issue(issue_id)
        except KeyError as error:
            return _error_response(error, _request_id(http_request))

    @router.post(
        "/issues/{issue_id}/backpin-reviews",
        response_model=Issue,
        responses=error_responses,
    )
    def review_backpin(
        issue_id: StableId,
        request: BackpinReviewRequest,
        http_request: Request,
    ) -> Issue | JSONResponse:
        try:
            return service.review_backpin(
                issue_id, _authenticated_actor_id(http_request), request.decision
            )
        except (AuthenticatedActorRequiredError, BackpinReviewError, KeyError) as error:
            return _error_response(error, _request_id(http_request))

    @router.post(
        "/issues/{issue_id}/change-proposals",
        response_model=ChangeSetProposal,
        responses=error_responses,
    )
    def create_change_proposal(
        issue_id: StableId,
        request: ChangeProposalRequest,
        http_request: Request,
    ) -> ChangeSetProposal | JSONResponse:
        try:
            return service.propose_issue_change(
                issue_id, **request.model_dump(mode="python")
            )
        except (ChangeSetProposalError, KeyError) as error:
            return _error_response(error, _request_id(http_request))

    return router


def _request_id(request: Request) -> str:
    state_id = getattr(request.state, "request_id", None)
    return str(
        state_id
        or request.headers.get("x-request-id")
        or f"request.playtest.{uuid4().hex}"
    )


def _authenticated_actor_id(request: Request) -> str:
    actor_id = getattr(request.state, "actor_id", None)
    try:
        return TypeAdapter(StableId).validate_python(actor_id)
    except ValidationError as error:
        raise AuthenticatedActorRequiredError(
            "backpin review requires an authenticated actor from request state"
        ) from error


def _error_response(error: Exception, request_id: str) -> JSONResponse:
    code = getattr(error, "code", "PLAYTEST_RESOURCE_NOT_FOUND")
    retryable = bool(getattr(error, "retryable", False))
    status = (
        503
        if retryable
        else 401
        if isinstance(error, AuthenticatedActorRequiredError)
        else 404
        if isinstance(error, KeyError)
        else 409
    )
    body = ErrorBody(
        code=code,
        message=str(error),
        request_id=request_id,
        retryable=retryable,
        suggested_actions=["playtest.run"],
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))
