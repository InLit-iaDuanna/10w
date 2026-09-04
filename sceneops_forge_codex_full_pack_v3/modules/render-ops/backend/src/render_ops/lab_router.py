"""Session-isolated lab routes; no external execution endpoint is registered."""

from threading import RLock
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .lab_contracts import LabState, LabRecipeInput, LabProposalInput, LabCompareInput, LabComparison
from .lab_service import RenderLabService


def create_render_lab_router(*, service_factory=RenderLabService):
    router = APIRouter(prefix="/api/render-lab", tags=["render-lab"])
    sessions = {}
    lock = RLock()

    def session(session_id: UUID, x_render_lab: str = Header()):
        if x_render_lab != "local-workbench":
            raise HTTPException(403, "请通过本地渲染工作台操作。")
        with lock:
            if session_id not in sessions:
                sessions[session_id] = service_factory()
            return sessions[session_id]

    def invoke(service, action):
        with lock:
            try:
                action()
                return service.snapshot()
            except KeyError as exc:
                raise HTTPException(404, str(exc)) from exc
            except PermissionError as exc:
                raise HTTPException(403, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @router.get("/health", operation_id="renderLabHealth")
    def health():
        return {"status": "ok", "mode": "mock", "external_execution": "blocked"}

    @router.get("/{session_id}", response_model=LabState, operation_id="renderLabState")
    def state(service=Depends(session)):
        return invoke(service, lambda: None)

    @router.post("/{session_id}/plan", response_model=LabState, operation_id="renderLabPlan")
    def plan(body: LabRecipeInput, service=Depends(session)):
        return invoke(service, lambda: service.plan(body))

    @router.post("/{session_id}/jobs/{job_id}/actions/{action}", response_model=LabState, operation_id="renderLabJobAction")
    def job_action(job_id: str, action: Literal["load-fixture", "cancel", "retry"], service=Depends(session)):
        return invoke(service, lambda: service.job_action(job_id, action))

    @router.post("/{session_id}/jobs/{job_id}/variants/{variant_id}/approve", response_model=LabState, operation_id="renderLabApproveVariant")
    def approve_variant(job_id: str, variant_id: str, service=Depends(session)):
        return invoke(service, lambda: service.approve_variant(job_id, variant_id))

    @router.post("/{session_id}/jobs/{job_id}/proposals", response_model=LabState, operation_id="renderLabPropose")
    def propose(job_id: str, body: LabProposalInput, service=Depends(session)):
        return invoke(service, lambda: service.propose(job_id, body))

    @router.post("/{session_id}/jobs/{job_id}/proposals/{proposal_id}/approve", response_model=LabState, operation_id="renderLabApproveProposal")
    def approve_proposal(job_id: str, proposal_id: str, service=Depends(session)):
        return invoke(service, lambda: service.approve_proposal(job_id, proposal_id))

    @router.post("/{session_id}/jobs/{job_id}/comparison", response_model=LabComparison, operation_id="renderLabCompare")
    def compare(job_id: str, body: LabCompareInput, service=Depends(session)):
        with lock:
            try:
                return service.compare(job_id, body)
            except (KeyError, ValueError) as exc:
                raise HTTPException(409, str(exc)) from exc

    @router.post("/{session_id}/reset", response_model=LabState, operation_id="renderLabReset")
    def reset(session_id: UUID, service=Depends(session)):
        with lock:
            sessions[session_id] = service_factory()
            return sessions[session_id].snapshot()

    return router
