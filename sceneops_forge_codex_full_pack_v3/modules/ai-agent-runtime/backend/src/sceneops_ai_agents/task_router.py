"""Typed task HTTP routes. Composition root retains local-origin/auth middleware."""
import asyncio
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sceneops_harness import HarnessError
from .task_models import AgentTaskEvents, AgentTaskList, AgentTaskRecord, AuthorizeAgentTask, PrepareAgentTask
from .production_models import ProductionEvents, ProductionSnapshot


def create_agent_task_router(service):
    router = APIRouter(prefix="/api/agent/tasks", tags=["agent-tasks"])

    def require_service():
        if service is None:
            raise HTTPException(503, "Agent 任务服务未启用。")
        return service

    @router.post("", response_model=AgentTaskRecord)
    async def prepare(body: PrepareAgentTask):
        return require_service().prepare(body)

    @router.get("", response_model=AgentTaskList)
    def list_tasks(project_id: str | None = Query(default=None)):
        return AgentTaskList(tasks=require_service().list(project_id))

    @router.get("/{task_id}", response_model=AgentTaskRecord)
    def task(task_id: str):
        return require_service().get(task_id)

    @router.post("/{task_id}/authorize", response_model=AgentTaskRecord)
    async def authorize(task_id: str, body: AuthorizeAgentTask):
        return require_service().authorize(task_id, body)

    @router.post("/{task_id}/cancel", response_model=AgentTaskRecord)
    async def cancel(task_id: str):
        return require_service().cancel(task_id)

    @router.post("/{task_id}/resume", response_model=AgentTaskRecord)
    async def resume(task_id: str):
        return await require_service().resume(task_id)

    @router.get("/{task_id}/events", response_model=AgentTaskEvents)
    def events(task_id: str, after: int = Query(default=0, ge=0)):
        return require_service().events(task_id, after)

    return router


def create_production_router(service):
    router = APIRouter(prefix='/api/agent/projects', tags=['production'])

    def production(project_id):
        if service is None:
            raise HTTPException(503, '生产记录服务未启用。')
        service.workspace.get_project(project_id)
        return service.production

    @router.get('/{project_id}/production', response_model=ProductionSnapshot)
    def snapshot(project_id: str):
        return production(project_id).snapshot(project_id)

    @router.get('/{project_id}/events', response_model=ProductionEvents)
    def events(project_id: str, after: int = Query(default=0, ge=0)):
        return production(project_id).events(project_id, after)

    @router.get('/{project_id}/events/stream')
    async def stream_events(project_id: str, request: Request, after: int = Query(default=0, ge=0)):
        store = production(project_id)
        try:
            cursor = max(after, int(request.headers.get('last-event-id', '0')))
        except ValueError:
            raise HTTPException(422, '事件游标无效。')
        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                page = store.events(project_id, cursor)
                for event in page.events:
                    yield f'id: {event.sequence}\nevent: production\ndata: {event.model_dump_json()}\n\n'
                cursor = page.next_cursor
                if not page.events:
                    yield ': keep-alive\n\n'
                    await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @router.get('/{project_id}/artifacts/{artifact_id}/content')
    def artifact_content(project_id: str, artifact_id: str, version: int | None = Query(default=None, ge=1)):
        stream, artifact = production(project_id).artifact_content(project_id, artifact_id, version)
        def chunks():
            try:
                while chunk := stream.read(65536):
                    yield chunk
            finally:
                stream.close()
        disposition = 'inline' if artifact.kind in ('image', 'audio') else 'attachment'
        return StreamingResponse(chunks(), media_type=artifact.media_type,
            headers={'Content-Disposition': f"{disposition}; filename*=UTF-8''{quote(artifact.name, safe='')}",
                     'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})

    return router
