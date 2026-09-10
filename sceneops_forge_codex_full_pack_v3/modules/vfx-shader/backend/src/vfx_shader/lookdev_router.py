"""Native material API; local authentication remains owned by the API host."""
import asyncio
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse
from .lookdev_models import (LookdevDocument, SaveLookdevRequest, LookdevProposalRequest,
                             LookdevProposal, ApplyLookdevRequest, LookdevApplication, FinishLookdevTurnRequest, LookdevTurn, ExportLookdevRequest, LookdevExport)


def create_lookdev_router(service):
    router = APIRouter(prefix='/api/lookdev', tags=['lookdev'])

    @router.get('/{project_id}/documents', response_model=list[LookdevDocument], operation_id='listLookdevDocuments')
    def list_documents(project_id: str, asset_id: str | None = None, scene_instance_id: str | None = None):
        return service.list(project_id, asset_id, scene_instance_id)

    @router.get('/{project_id}/documents/{document_id}', response_model=LookdevDocument, operation_id='getLookdevDocument')
    def get_document(project_id: str, document_id: str, version: int | None = Query(default=None, ge=1)):
        return service.get(project_id, document_id, version)

    @router.post('/{project_id}/documents', response_model=LookdevDocument, operation_id='saveLookdevDocument')
    async def save_document(project_id: str, body: SaveLookdevRequest):
        return await service.save(project_id, body)

    @router.post('/{project_id}/proposals', response_model=LookdevProposal, operation_id='proposeLookdevEdit')
    async def propose(project_id: str, body: LookdevProposalRequest, request: Request):
        task = asyncio.create_task(service.propose(project_id, body))
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.2)
                if await request.is_disconnected():
                    task.cancel()
                    raise asyncio.CancelledError()
            return await task
        finally:
            if not task.done():
                task.cancel()
            if task.cancelled() or (not task.done()):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @router.post('/{project_id}/apply', response_model=LookdevApplication, operation_id='applyLookdev')
    def apply(project_id: str, body: ApplyLookdevRequest):
        return service.apply(project_id, body)

    @router.get('/{project_id}/turns', response_model=list[LookdevTurn], operation_id='listLookdevTurns')
    def turns(project_id: str):
        return service.history(project_id)

    @router.post('/{project_id}/turns/{turn_id}/finish', response_model=LookdevTurn, operation_id='finishLookdevTurn')
    def finish(project_id: str, turn_id: str, body: FinishLookdevTurnRequest):
        return service.finish_turn(project_id, turn_id, body)

    @router.get('/{project_id}/bindings', response_model=list[LookdevApplication], operation_id='listLookdevBindings')
    def bindings(project_id: str):
        return service.bindings(project_id)

    @router.get('/{project_id}/assets/{asset_id}/source', operation_id='downloadLookdevSource')
    def source(project_id: str, asset_id: str, version: int = Query(ge=1)):
        return FileResponse(service.source(project_id, asset_id, version), media_type='model/gltf-binary')

    @router.post('/{project_id}/exports', response_model=LookdevExport, operation_id='exportLookdevDocument')
    async def export(project_id: str, body: ExportLookdevRequest):
        return await service.export(project_id, body)

    @router.get('/{project_id}/exports/{artifact_id}/download', operation_id='downloadLookdevExport')
    def download(project_id: str, artifact_id: str):
        artifact, path = service.export_file(project_id, artifact_id)
        return FileResponse(path, filename=artifact.filename, media_type=artifact.media_type)

    return router
