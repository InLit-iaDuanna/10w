"""Project-scoped HTTP/SSE transport for export service."""
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from .export_models import (CreateExportRequest, ExportTask, ExportPlatform,
    ExportMessageRequest, ExportVerificationRequest, ExportConsentRequest)


def create_export_router(service):
    router = APIRouter(prefix='/api/projects/{project_id}/exports', tags=['project-exports'])

    def call(fn, *args):
        try:
            return fn(*args)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get('', response_model=list[ExportTask])
    def list_exports(project_id: str):
        return call(service.list, project_id)

    @router.post('', response_model=ExportTask)
    def create_export(project_id: str, request: CreateExportRequest):
        return call(service.create, project_id, request)

    @router.get('/{task_id}', response_model=ExportTask)
    def get_export(project_id: str, task_id: str):
        return call(service.get, project_id, task_id)

    @router.post('/{task_id}/platforms/{platform}/continue', response_model=ExportTask)
    def continue_export(project_id: str, task_id: str, platform: ExportPlatform):
        return call(service.continue_platform, project_id, task_id, platform)

    @router.post('/{task_id}/platforms/{platform}/cancel', response_model=ExportTask)
    def cancel_export(project_id: str, task_id: str, platform: ExportPlatform):
        return call(service.cancel, project_id, task_id, platform)

    @router.post('/{task_id}/platforms/{platform}/verification', response_model=ExportTask)
    def verify_export(project_id: str, task_id: str, platform: ExportPlatform, request: ExportVerificationRequest):
        return call(service.verify, project_id, task_id, platform, request)

    @router.post('/{task_id}/settings', response_model=ExportTask)
    def export_consent(project_id: str, task_id: str, request: ExportConsentRequest):
        return call(service.consent, project_id, task_id, request)

    @router.post('/{task_id}/messages', response_model=ExportTask)
    def message_export(project_id: str, task_id: str, request: ExportMessageRequest):
        return call(service.message, project_id, task_id, request)

    @router.post('/{task_id}/agent/cancel', response_model=ExportTask)
    def cancel_export_agent(project_id: str, task_id: str):
        return call(service.cancel_native, project_id, task_id)

    @router.post('/{task_id}/refresh-source', response_model=ExportTask)
    def refresh_export_source(project_id: str, task_id: str):
        return call(service.refresh_source, project_id, task_id)

    @router.get('/{task_id}/artifacts/{artifact_id}')
    def download_export(project_id: str, task_id: str, artifact_id: str):
        path = call(service.artifact, project_id, task_id, artifact_id)
        return FileResponse(path, filename=path.name, media_type='application/octet-stream')

    @router.get('/{task_id}/events')
    async def export_events(project_id: str, task_id: str, request: Request):
        call(service.get, project_id, task_id)
        async def stream():
            revision = -1
            while not await request.is_disconnected():
                task = service.get(project_id, task_id)
                if revision != task.revision:
                    revision = task.revision
                    yield f'id: {revision}\nevent: snapshot\ndata: {task.model_dump_json()}\n\n'
                else:
                    yield ': keep-alive\n\n'
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    return router
