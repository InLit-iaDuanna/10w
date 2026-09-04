"""Compose public module routers with one isolated instance per local project.

The outer routes preserve the original endpoint signatures for OpenAPI. Their
handlers delegate to the corresponding project-bound router, including its own
FastAPI dependencies and response validation. No request can choose another
project's in-memory service by reusing a lab session ID.
"""
from dataclasses import dataclass
from threading import RLock
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute


@dataclass
class ProjectModule:
    router: APIRouter
    import_sample: Callable[[str], None] | None = None


class ProjectRouters:
    def __init__(self, repository):
        self.repository = repository
        self.factories = {}
        self.instances = {}
        self.lock = RLock()

    def get(self, project_id, module_id):
        if not self.repository.exists(project_id):
            raise HTTPException(404, "项目不存在。")
        with self.lock:
            key = (project_id, module_id)
            if key not in self.instances:
                self.instances[key] = self.factories[module_id](project_id)
            return self.instances[key]

    def import_sample(self, project_id, module_id, sample_id):
        if module_id not in self.factories:
            # Pure frontend evidence editors only persist their explicit draft reference.
            return
        instance = self.get(project_id, module_id)
        if instance.import_sample:
            instance.import_sample(sample_id)

    def register(self, module_id, factory, template):
        self.factories[module_id] = factory
        registry = self

        class ProjectRoute(APIRoute):
            def get_route_handler(self):
                async def handle(request: Request):
                    project_id = request.headers.get("x-sceneops-project")
                    if not project_id:
                        raise HTTPException(400, "请先选择项目。")
                    instance = registry.get(project_id, module_id)
                    route = next(route for route in instance.router.routes
                        if isinstance(route, APIRoute) and route.path == self.path and route.methods == self.methods)
                    return await route.get_route_handler()(request)
                return handle

        router = APIRouter(route_class=ProjectRoute)
        for route in template.routes:
            if not isinstance(route, APIRoute):
                continue
            router.add_api_route(route.path, route.endpoint, methods=route.methods,
                response_model=route.response_model, status_code=route.status_code,
                tags=route.tags, dependencies=route.dependencies, summary=route.summary,
                description=route.description, responses=route.responses,
                operation_id=route.operation_id, name=route.name,
                response_model_exclude_none=route.response_model_exclude_none,
                response_model_by_alias=route.response_model_by_alias,
                route_class_override=ProjectRoute)
        return router
