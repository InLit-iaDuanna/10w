"""Single local API composition root for SceneOps Forge."""
import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from sceneops_project_workspace import SqliteWorkspaceRepository, create_workspace_router, create_folder_router
from conversation_home import create_ai_router, router as conversation_router
from sceneops_design_ai import create_ai_router as create_design_ai_router
from sceneops_design_ai import PlanningJourneyService, create_journey_router
from sceneops_production_planner import PlannerDomainError
from concept_lab import ConceptLabError, concept_lab_error_handler
from version_collaboration import VersionCollaborationError, version_collaboration_exception_handler
from sceneops_ai_pipeline import PlanningService, create_router as create_harness_router
from sceneops_ai_provider import ProviderFailure
from sceneops_harness import HarnessError
from sceneops_ai_agents import AgentTaskService, create_agent_task_router, create_production_router
from sceneops_ai_provider import ProviderService
from asset_factory import CardAssetError, CardAssetService, create_card_asset_router
from asset_library import (ProjectAssetCatalogService, SqliteProjectAssetRepository,
                           create_project_catalog_router)
from world_composer import (EnvironmentSceneError, EnvironmentSceneService,
                            create_environment_scene_router)
from .domains import compose_domains

ROOT = Path(__file__).resolve().parents[2]


class Health(BaseModel):
    status: str = "ready"
    storage: str = "sqlite"
    default_workspace: str = "empty"
    external_execution: str = "idle"


def create_app() -> FastAPI:
    data_dir = Path(os.environ.get("SCENEOPS_DATA_DIR", str(ROOT / ".local"))).resolve()
    database = data_dir / "sceneops.sqlite3"
    repository = SqliteWorkspaceRepository(database)
    app = FastAPI(title="SceneOps Forge API", version="0.5.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    token = os.environ.get("SCENEOPS_LOCAL_TOKEN", "")
    web_port = os.environ.get("SCENEOPS_WEB_PORT", "4300")
    api_port = os.environ.get("SCENEOPS_API_PORT", "8300")
    origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (web_port, api_port)}

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse(status_code=403, content={"code": "LOCAL_ORIGIN_REQUIRED", "message": "仅允许当前本地工作台来源。"})
        if request.url.path.startswith(("/api/", "/v1/")) and request.url.path != "/api/health":
            supplied = request.headers.get("x-sceneops-token", "")
            if not token or not secrets.compare_digest(supplied, token):
                return JSONResponse(status_code=401, content={"code": "LOCAL_PROXY_REQUIRED", "message": "请通过 pnpm dev 的 Web 入口访问。"})
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not origin or origin not in origins:
                return JSONResponse(status_code=403, content={"code": "LOCAL_ORIGIN_REQUIRED", "message": "写入只接受当前本地 Web 来源。"})
            content_type = request.headers.get("content-type", "").split(";")[0]
            binary_asset_upload = (request.method == "POST" and content_type == "application/octet-stream"
                                   and request.url.path.startswith("/api/card-assets/")
                                   and request.url.path.endswith(("/imports", "/references")))
            if content_type != "application/json" and not binary_asset_upload:
                return JSONResponse(status_code=415, content={"code": "JSON_REQUIRED", "message": "写入请求必须使用 JSON；模型导入端点只接受二进制文件。"})
        request.state.actor_id = "usr_local_workspace"
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(status_code=error.status_code,
            content={"code": "REQUEST_REJECTED", "message": str(error.detail), "detail": error.detail, "retryable": False})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse(status_code=422, content={"code": "INVALID_REQUEST", "message": "请求格式不正确，请检查输入。", "retryable": False})

    @app.exception_handler(ValueError)
    async def invalid_value(request, error):
        return JSONResponse(status_code=422, content={"code": "INVALID_VALUE", "message": str(error), "retryable": False})

    @app.exception_handler(ProviderFailure)
    async def provider_error(request, error):
        return JSONResponse(status_code=error.status_code, content={"code": error.code, "message": str(error), "retryable": True})

    @app.exception_handler(HarnessError)
    async def harness_error(request, error):
        status = 404 if error.code in {"RECORD_NOT_FOUND", "RUN_NOT_FOUND", "STEP_NOT_FOUND"} else 409
        return JSONResponse(status_code=status, content={"code": error.code, "message": str(error), "retryable": False})

    @app.exception_handler(CardAssetError)
    async def card_asset_error(request, error):
        return JSONResponse(status_code=error.status_code,
            content={"code": error.code, "message": str(error), "retryable": error.status_code >= 500})

    @app.exception_handler(EnvironmentSceneError)
    async def environment_scene_error(request, error):
        return JSONResponse(status_code=error.status_code,
            content={"code": error.code, "message": str(error), "retryable": error.status_code >= 500})

    @app.exception_handler(PlannerDomainError)
    async def planner_error(request, error):
        status = 503 if error.code.endswith("UNAVAILABLE") else 404 if error.code.endswith("NOT_FOUND") else 409
        return JSONResponse(status_code=status, content={"code": error.code, "message": error.message,
            "details": error.details, "retryable": error.retryable, "suggested_actions": error.suggested_actions})

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logging.getLogger("sceneops.api").exception("Request failed: %s", request.url.path)
        return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "message": "本地服务处理失败，请查看启动终端。", "retryable": True})

    @app.get("/api/health", response_model=Health, operation_id="applicationHealth")
    def health():
        tasks = getattr(app.state, "agent_tasks", None)
        return Health(external_execution=tasks.execution_status() if tasks else "idle")

    app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
    app.add_exception_handler(VersionCollaborationError, version_collaboration_exception_handler)
    domains = compose_domains(app, repository, data_dir)
    app.include_router(create_workspace_router(repository, import_sample=domains.import_sample))
    app.include_router(create_folder_router(repository))
    journey = None
    if os.environ.get('SCENEOPS_PLANNING_JOURNEY_ENABLED', 'true').lower() != 'false':
        journey = PlanningJourneyService(database, repository)
        app.include_router(create_journey_router(journey))
    app.state.planning_journey = journey
    app.include_router(create_ai_router(database, project_exists=repository.exists))
    app.include_router(conversation_router)
    app.include_router(create_design_ai_router())
    project_assets = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
    app.include_router(create_project_catalog_router(project_assets))
    provider = ProviderService(database)
    environment_scenes = EnvironmentSceneService(database, repository, project_assets, provider)
    card_assets = CardAssetService(database, data_dir, repository, provider, catalog=project_assets,
                                   world_context=environment_scenes.asset_generation_context)
    app.include_router(create_card_asset_router(card_assets))
    app.include_router(create_environment_scene_router(environment_scenes))
    app.state.card_assets = card_assets
    app.state.project_assets = project_assets
    app.state.environment_scenes = environment_scenes
    app.state.workspace_repository = repository
    app.state.project_domains = domains
    if os.environ.get("SCENEOPS_HARNESS_ENABLED", "true").lower() != "false":
        harness = PlanningService(database, repository)
        app.include_router(create_harness_router(harness))
        app.state.harness = harness
        for project in repository.list_projects():
            harness.runtime.recover_interrupted(project.project_id)
        app.add_event_handler("shutdown", harness.close)
        agent_tasks = AgentTaskService(database, repository, data_dir,
            provider=provider, card_context=journey.development_context if journey else None,
            project_assets=project_assets, environment_scenes=environment_scenes)
        app.include_router(create_agent_task_router(agent_tasks))
        app.include_router(create_production_router(agent_tasks))
        app.state.agent_tasks = agent_tasks
        app.add_event_handler("shutdown", agent_tasks.close)
    return app
