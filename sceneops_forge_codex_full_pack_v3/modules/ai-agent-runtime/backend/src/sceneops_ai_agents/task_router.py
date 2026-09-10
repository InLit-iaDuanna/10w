"""Typed task HTTP routes. Composition root retains local-origin/auth middleware."""
import asyncio
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sceneops_harness import HarnessError
from .task_models import (AgentTaskEvents, AgentTaskList, AgentTaskRecord, AuthorizeAgentTask,
                          PrepareAgentTask, GameOperationRequest, GameProjectExecution, BrowserInteractionRequest)
from .task_models import ContinueProjectDemoRequest, TaskArchiveRequest
from .demo_workbench_models import (DemoContentIndex, DemoContentSave, DemoContentSaved,
    DemoPlayRequest, DemoPlaySession, DemoContinuationAuthorizationRequest, DemoSourceRegistration, DemoSourceRename)
from .blender_content_models import BlenderManualRequest
from .unity_content_models import PrepareUnityAssetTask, UnityContentSnapshot, UnityManualRequest
from .production_models import ProductionEvents, ProductionSnapshot
from .source_editor import CardSourceIndex, CardSourceFile, SaveCardSource


def create_agent_task_router(service):
    router = APIRouter(prefix="/api/agent/tasks", tags=["agent-tasks"])

    def require_service():
        if service is None:
            raise HTTPException(503, "Agent 任务服务未启用。")
        return service

    @router.post("", response_model=AgentTaskRecord)
    async def prepare(body: PrepareAgentTask):
        return require_service().prepare(body)

    from .creation_brief import CreationBrief, SaveCreationBrief, read_brief, save_brief

    @router.get('/{task_id}/creation-brief', response_model=CreationBrief)
    def creation_brief(task_id: str):
        return read_brief(require_service(), task_id)

    @router.put('/{task_id}/creation-brief', response_model=CreationBrief)
    def edit_creation_brief(task_id: str, body: SaveCreationBrief):
        return save_brief(require_service(), task_id, body)

    @router.get("", response_model=AgentTaskList)
    def list_tasks(project_id: str | None = Query(default=None), archived: bool | None = Query(default=None)):
        return AgentTaskList(tasks=require_service().list(project_id, archived))

    @router.put('/{task_id}/archive', response_model=AgentTaskRecord)
    def archive_task(task_id: str, body: TaskArchiveRequest):
        return require_service().archive(task_id, body.archived)

    from .entity_production import OrganizeEntity, EntityProposal, AdoptEntity, ProductionEntity

    @router.get('/{task_id}/production-entities', response_model=list[ProductionEntity])
    def entities(task_id: str):
        from .entity_production import list_entities
        return list_entities(require_service(), task_id)

    @router.post('/{task_id}/production-entities/proposal', response_model=EntityProposal)
    def entity_proposal(task_id: str, body: OrganizeEntity):
        from .entity_production import proposal
        return proposal(require_service(), task_id, body)

    @router.post('/{task_id}/production-entities', response_model=ProductionEntity)
    def organize_entity(task_id: str, body: OrganizeEntity):
        from .entity_production import organize
        return organize(require_service(), task_id, body)

    @router.post('/{task_id}/production-entities/{entity_id}/adopt', response_model=ProductionEntity)
    def adopt_entity(task_id: str, entity_id: str, body: AdoptEntity):
        from .entity_production import adopt
        return adopt(require_service(), task_id, entity_id, body)

    @router.get("/{task_id}", response_model=AgentTaskRecord)
    def task(task_id: str):
        return require_service().get(task_id)

    @router.post("/{task_id}/authorize", response_model=AgentTaskRecord)
    async def authorize(task_id: str, body: AuthorizeAgentTask):
        return require_service().authorize(task_id, body)

    @router.post('/{task_id}/unity-target', response_model=AgentTaskRecord)
    def prepare_unity(task_id: str, body: PrepareUnityAssetTask):
        from .unity_tasks import prepare_unity_task
        return prepare_unity_task(require_service(), task_id, body)

    @router.get('/{task_id}/unity-content', response_model=UnityContentSnapshot)
    async def read_unity(task_id: str):
        from .unity_content import content_snapshot
        return await content_snapshot(require_service(), task_id)

    @router.post('/{task_id}/unity-content', response_model=AgentTaskRecord)
    async def edit_unity(task_id: str, body: UnityManualRequest):
        from .unity_manual import execute_unity_manual
        return await execute_unity_manual(require_service(), task_id, body)

    @router.post("/{task_id}/cancel", response_model=AgentTaskRecord)
    async def cancel(task_id: str):
        return require_service().cancel(task_id)

    @router.post("/{task_id}/resume", response_model=AgentTaskRecord)
    async def resume(task_id: str):
        return await require_service().resume(task_id)

    @router.post("/{task_id}/project-demo/update", response_model=AgentTaskRecord,
                 operation_id="updateProjectDemo")
    async def update_project_demo(task_id: str):
        return require_service().update_project_demo(task_id)

    @router.post("/{task_id}/project-demo/continue", response_model=AgentTaskRecord,
                 operation_id="continueProjectDemo")
    async def continue_project_demo(task_id: str, body: ContinueProjectDemoRequest):
        return require_service().continue_project_demo(task_id, body)

    @router.get('/{task_id}/project-demo/content', response_model=DemoContentIndex)
    def demo_content(task_id: str):
        from .demo_workbench import content_index
        return content_index(require_service(), task_id)

    @router.post('/{task_id}/project-demo/content', response_model=DemoContentSaved)
    def save_demo_content(task_id: str, body: DemoContentSave):
        from .demo_workbench import save_content
        return save_content(require_service(), task_id, body)

    @router.get('/{task_id}/project-demo/source-registrations', response_model=list[DemoSourceRegistration])
    def registered_sources(task_id: str):
        from .demo_workbench import project_task
        from .workspace_sources import source_registrations
        runtime = require_service()
        return source_registrations(runtime, project_task(runtime, task_id))

    @router.post('/{task_id}/project-demo/source-rename', response_model=DemoContentIndex)
    def confirm_rename(task_id: str, body: DemoSourceRename):
        from .demo_workbench import project_task, content_index
        from .workspace_sources import confirm_source_rename
        runtime = require_service()
        task = project_task(runtime, task_id)
        with runtime.records.manual_edit(task):
            confirm_source_rename(runtime, task, body.source_id, body.new_path,
                                  body.expected_version, body.expected_target_version)
            runtime.records.update(task_id, lambda current: None, 'agent.source.rename_confirmed', body.model_dump())
        return content_index(runtime, task_id)

    @router.post('/{task_id}/project-demo/blender', response_model=AgentTaskRecord)
    async def blender_content(task_id: str, body: BlenderManualRequest):
        from .blender_manual import execute_manual
        return await execute_manual(require_service(), task_id, body)

    @router.post('/{task_id}/project-demo/play', response_model=DemoPlaySession)
    async def play_demo_candidate(task_id: str, body: DemoPlayRequest):
        from .demo_workbench import play_candidate
        return await play_candidate(require_service(), task_id, body.candidate_id)

    @router.post('/{task_id}/project-demo/continuation-authorization', response_model=AgentTaskRecord)
    def prepare_demo_continuation(task_id: str, body: DemoContinuationAuthorizationRequest):
        from .demo_continuation import prepare_demo_continuation
        return prepare_demo_continuation(require_service(), task_id, body.request_id, allow_blender_edit=body.allow_blender_edit)

    @router.get('/{task_id}/game', response_model=GameProjectExecution)
    def game_status(task_id: str):
        return require_service().game_status(task_id)

    @router.post('/{task_id}/game/observation/cancel')
    def cancel_observation(task_id: str):
        return require_service().cancel_browser_observation(task_id)

    @router.post('/{task_id}/game/observation/revoke', response_model=AgentTaskRecord)
    def revoke_observation(task_id: str):
        return require_service().revoke_browser_authorization(task_id)

    @router.post('/{task_id}/game', response_model=GameProjectExecution)
    async def game_operation(task_id: str, body: GameOperationRequest):
        return await require_service().game_operation(task_id, body)

    @router.post('/{task_id}/game/interaction', response_model=GameProjectExecution)
    async def interact(task_id: str, body: BrowserInteractionRequest):
        await require_service().observe_game(task_id, interaction=body)
        return require_service().game_status(task_id)

    @router.post('/{task_id}/game/interaction/revoke', response_model=AgentTaskRecord)
    def revoke_interaction(task_id: str):
        return require_service().revoke_browser_authorization(task_id, interaction=True)

    @router.get("/{task_id}/events", response_model=AgentTaskEvents)
    def events(task_id: str, after: int = Query(default=0, ge=0)):
        return require_service().events(task_id, after)

    from .local_server_router import create_local_server_router
    combined = APIRouter()
    combined.include_router(router)
    combined.include_router(create_local_server_router(service))
    return combined


def create_production_router(service):
    router = APIRouter(prefix='/api/agent/projects', tags=['production'])

    def production(project_id):
        if service is None:
            raise HTTPException(503, '生产记录服务未启用。')
        service.workspace.get_project(project_id)
        service.refresh_workspace_changes(project_id)
        return service.production

    def source_service():
        if service is None:
            raise HTTPException(503, '源码服务未启用。')
        return service

    from .native_inputs import NativeInputUpload, NativeInputReference, save_native_input

    @router.post('/{project_id}/inputs', response_model=NativeInputReference)
    def upload_native_input(project_id: str, body: NativeInputUpload):
        return save_native_input(source_service(), project_id, body)

    @router.get('/{project_id}/inputs/file')
    def native_input_file(project_id: str, path: str = Query(min_length=1,max_length=240)):
        from pathlib import Path
        from fastapi.responses import FileResponse
        from .native_inputs import resolve_native_inputs
        active=source_service()
        active.workspace.get_project(project_id)
        workspace=active.workspace.open_project_demo_workspace(project_id)
        reference=resolve_native_inputs(Path(workspace['workspace_root']),[path])[0]
        return FileResponse(reference['absolute_path'],filename=reference['name'])

    @router.get('/{project_id}/cards/{card_id}/source', response_model=CardSourceIndex)
    def card_source_index(project_id: str, card_id: str):
        from .source_editor import source_index
        return source_index(source_service(), project_id, card_id)

    @router.get('/{project_id}/cards/{card_id}/source/file', response_model=CardSourceFile)
    def card_source_file(project_id: str, card_id: str, path: str = Query(min_length=1, max_length=240)):
        from .source_editor import source_file
        return source_file(source_service(), project_id, card_id, path)

    @router.post('/{project_id}/cards/{card_id}/source/file', response_model=AgentTaskRecord)
    async def save_card_source(project_id: str, card_id: str, body: SaveCardSource):
        from .source_editor import save_source
        return await save_source(source_service(), project_id, card_id, body)

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
