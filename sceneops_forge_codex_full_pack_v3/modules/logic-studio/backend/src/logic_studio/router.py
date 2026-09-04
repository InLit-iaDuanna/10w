from fastapi import APIRouter, HTTPException

from .models import (
    ApproveChangeSetRequest,
    CodeChangeProposal,
    CodeChangeSet,
    CompileTemplateRequest,
    GameplayGraph,
    GeneratedTestPlan,
    GraphValidationReport,
)
from .service import InvalidGameplayGraph, LogicStudioService


router = APIRouter(prefix="/logic-studio", tags=["logic-studio"])
_service = LogicStudioService()


@router.post("/graphs/validate", response_model=GraphValidationReport)
def validate_graph(graph: GameplayGraph) -> GraphValidationReport:
    return _service.validate_graph(graph)


@router.post("/templates/compile", response_model=GameplayGraph)
def compile_template(request: CompileTemplateRequest) -> GameplayGraph:
    try:
        return _service.compile_template(request)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/graphs/test-plan", response_model=GeneratedTestPlan)
def create_test_plan(graph: GameplayGraph) -> GeneratedTestPlan:
    try:
        return _service.generate_tests(graph)
    except InvalidGameplayGraph as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/code-changes/propose", response_model=CodeChangeSet)
def propose_code_change(proposal: CodeChangeProposal) -> CodeChangeSet:
    try:
        return _service.propose_code_change(proposal)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/code-changes/{change_set_id}/approve",
    response_model=CodeChangeSet,
)
def approve_code_change(
    change_set_id: str, request: ApproveChangeSetRequest
) -> CodeChangeSet:
    if request.change_set.change_set_id != change_set_id:
        raise HTTPException(status_code=409, detail="ChangeSet path and body IDs differ.")
    try:
        return _service.approve_code_change(
            request.change_set,
            approver_id=request.approver_id,
            permissions=request.permissions,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
