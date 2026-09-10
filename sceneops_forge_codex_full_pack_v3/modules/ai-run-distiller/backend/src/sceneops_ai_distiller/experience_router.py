"""HTTP boundary for the local experience service; host authentication is retained."""
from typing import Literal
from fastapi import APIRouter, Query
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse

from .experience_models import (EntryUpdate, ExperienceEntry, ExperienceRevision,
    ExperienceSettings, ExperienceSettingsUpdate, ExperienceStatus, ExperienceUse,
    LearnRequest, RestoreRequest, ExperienceTopic, ProjectMemoryCollection, MemoryWrite, MemoryEvent, MemoryUndo, MemoryActivity)
from .experience_repository import ExperienceError


class ExperienceRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def route(request):
            try:
                return await original(request)
            except ExperienceError as error:
                return JSONResponse(status_code=error.status_code,
                    content={'code': error.code, 'message': str(error)})
        return route


def create_experience_router(service):
    router = APIRouter(prefix='/api/experience', tags=['experience'], route_class=ExperienceRoute)

    @router.get('/topics', response_model=list[ExperienceTopic])
    def topics():
        return service.topics()

    @router.get('/settings', response_model=ExperienceSettings)
    def settings():
        return service.settings()

    @router.put('/settings', response_model=ExperienceSettings)
    def update_settings(body: ExperienceSettingsUpdate):
        return service.update_settings(body)

    @router.get('/status', response_model=ExperienceStatus)
    def status():
        return service.status()

    @router.get('/entries', response_model=list[ExperienceEntry])
    def entries(project_id: str | None = None, q: str = Query(default='', max_length=1000),
                scope: Literal['all', 'project', 'shared'] = 'all', include_disabled: bool = False):
        return service.entries(project_id, q, scope, include_disabled)

    @router.get('/entries/{entry_id}', response_model=ExperienceEntry)
    def entry(entry_id: str, project_id: str | None = None):
        return service.get_entry(entry_id, project_id)

    @router.get('/entries/{entry_id}/revisions', response_model=list[ExperienceRevision])
    def revisions(entry_id: str, project_id: str | None = None):
        return service.revisions(entry_id, project_id)

    @router.patch('/entries/{entry_id}', response_model=ExperienceEntry)
    def edit(entry_id: str, body: EntryUpdate, project_id: str | None = None):
        return service.update_entry(entry_id, project_id, body)

    @router.post('/entries/{entry_id}/restore', response_model=ExperienceEntry)
    def restore(entry_id: str, body: RestoreRequest, project_id: str | None = None):
        return service.restore(entry_id, project_id, body)

    @router.post('/learn', response_model=ExperienceStatus)
    async def learn(body: LearnRequest):
        return await service.learn(body.project_id, manual=True)

    @router.get('/uses', response_model=list[ExperienceUse])
    def uses(project_id: str | None = None, use_key: str = Query(default='', max_length=1000), exact: bool = False):
        return service.uses(project_id, use_key, exact=exact)

    @router.get('/project-memory', response_model=ProjectMemoryCollection)
    def project_memory(project_id: str | None = None):
        return service.project_memory(project_id)

    @router.post('/memories', response_model=MemoryEvent)
    async def write_memory(body: MemoryWrite):
        return await service.write_memory(body)

    @router.get('/activity', response_model=MemoryActivity)
    def activity(origin_key: str, project_id: str | None = None):
        return service.memory_activity(project_id, origin_key)

    @router.post('/events/{event_id}/undo', response_model=MemoryEvent)
    async def undo(event_id: str, body: MemoryUndo):
        return await service.undo_memory_event(event_id, body)

    return router
