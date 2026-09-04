from fastapi import APIRouter, HTTPException
from engine_unity import ChangeSet, UnityProposalPreview
from .workbench_models import ProposalInput, LocalProposal, WorkbenchSnapshot
from .workbench_service import UnityBuildWorkbenchService, WorkbenchConflict

def create_workbench_router(service: UnityBuildWorkbenchService):
    router=APIRouter(prefix="/api/unity-build",tags=["unity-build-local"])
    @router.get("/snapshot",response_model=WorkbenchSnapshot)
    def snapshot():
        return service.snapshot()
    @router.put("/proposals/{slug}",response_model=LocalProposal)
    def save(slug: str, request: ProposalInput):
        try:
            return service.save(slug,request)
        except KeyError:
            raise HTTPException(404,"提案不存在")
        except WorkbenchConflict as error:
            raise HTTPException(409,str(error))
        except ValueError as error:
            raise HTTPException(422,str(error))
    @router.post("/preview",response_model=UnityProposalPreview)
    def preview(change_set: ChangeSet):
        try:
            return service.unity.preview(change_set)
        except ValueError as error:
            raise HTTPException(422,str(error))
    return router
