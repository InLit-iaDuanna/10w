"""Single local API composition root for SceneOps Forge."""
import json
import logging
import os
import secrets
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from sceneops_project_workspace import (FolderProjectRequired, ProjectScopeError, SqliteWorkspaceRepository,
                                       create_workspace_router, create_folder_router)
from conversation_home import AIRepository, create_ai_router, router as conversation_router
from sceneops_design_ai import create_ai_router as create_design_ai_router
from sceneops_design_ai import PlanningJourneyService, create_journey_router
from sceneops_production_planner import PlannerDomainError
from concept_lab import ConceptLabError, concept_lab_error_handler
from version_collaboration import VersionCollaborationError, version_collaboration_exception_handler
from sceneops_ai_pipeline import PlanningService, create_router as create_harness_router
from sceneops_ai_provider import ProviderFailure
from sceneops_harness import HarnessError
from sceneops_ai_agents import (AgentTaskService, ExportAgent, create_agent_task_router,
                                create_production_router, production_skill_catalog,
                                production_skill_detail)
from sceneops_ai_context import (PreparationRepository, ProductionPreparationService,
                                 create_preparation_router)
from build_release import ExportService, create_export_router
from observability import Redactor
from sceneops_ai_distiller import ExperienceError, ExperienceService, create_experience_router
from sceneops_ai_provider import ProviderService
from asset_factory import CardAssetError, CardAssetService, BuiltinProjectAssets, create_card_asset_router
from asset_library import (ProjectAssetCatalogService, SqliteProjectAssetRepository,
                           create_project_catalog_router, AdoptBuiltinAsset,
                           BuiltinAssetCatalog, create_builtin_asset_router)
from world_composer import (EnvironmentSceneError, EnvironmentSceneService,
                            create_environment_scene_router)
from vfx_shader import LookdevService, LookdevError, NodeLookdevValidator, LookdevAssetApplication, create_lookdev_router
from .domains import compose_domains
from .export_integration import NativeExportPort
from .production_preparation import (BuiltinAssetCandidates, CapabilityCandidates,
                                     ExperienceCandidates, ProjectAssetCandidates,
                                     SkillCandidates)
from .audit import audit_event, configure_audit_logging

ROOT = Path(__file__).resolve().parents[2]


class Health(BaseModel):
    status: str = "ready"
    storage: str = "sqlite"
    default_workspace: str = "empty"
    external_execution: str = "idle"


class UiAuditEvent(BaseModel):
    timestamp: str
    type: str
    fields: dict[str, object] = Field(default_factory=dict)


class AuditStatus(BaseModel):
    enabled: bool
    stream: str


def create_app() -> FastAPI:
    data_dir = Path(os.environ.get("SCENEOPS_DATA_DIR", str(ROOT / ".local"))).resolve()
    database = data_dir / "sceneops.sqlite3"
    repository = SqliteWorkspaceRepository(database)
    app = FastAPI(title="SceneOps Forge API", version="0.5.0")
    audit_runtime = configure_audit_logging(data_dir)
    app.state.audit_runtime = audit_runtime
    if audit_runtime.active:
        audit_event("audit.enabled", source="api", mode="append-jsonl")
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

    @app.middleware("http")
    async def audit_http(request: Request, call_next):
        request_id = str(uuid4())
        started = time.monotonic()
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        request_body = None
        if content_type == "application/json":
            try:
                raw_body = await request.body()
                request_body = json.loads(raw_body.decode("utf-8")) if raw_body else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                request_body = {"invalid_json": True}
        elif request.method not in {"GET", "HEAD", "OPTIONS"}:
            request_body = {"content_type": content_type or "unknown", "body_captured": False}
        request.state.audit_request_id = request_id
        try:
            response = await call_next(request)
        except BaseException as error:
            audit_event(
                "http.error",
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                request_body=request_body,
                error_type=type(error).__name__,
                error=str(error),
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise
        response.headers["X-SceneOps-Request-ID"] = request_id
        response_type = response.headers.get("content-type", "").split(";", 1)[0]
        response_body = None
        response_bytes = getattr(response, "body", None)
        if response_type == "application/json" and isinstance(response_bytes, bytes):
            try:
                response_body = json.loads(response_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response_body = {"invalid_json": True, "body_captured": False}
        audit_event(
            "http.request",
            request_id=request_id,
            method=request.method,
            route=request.url.path,
            request_body=request_body,
            status_code=response.status_code,
            response_content_type=response_type or "unknown",
            response_size=int(response.headers.get("content-length", "0") or 0),
            response_body=response_body,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return response

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

    @app.exception_handler(ProjectScopeError)
    async def project_scope_error(request, error):
        return JSONResponse(status_code=error.status_code,
            content={"code": error.code, "message": str(error), "retryable": False})

    @app.exception_handler(ProviderFailure)
    async def provider_error(request, error):
        return JSONResponse(status_code=error.status_code, content={"code": error.code, "message": str(error), "retryable": True})

    @app.exception_handler(HarnessError)
    async def harness_error(request, error):
        status = 404 if error.code in {"RECORD_NOT_FOUND", "RUN_NOT_FOUND", "STEP_NOT_FOUND", "TASK_NOT_FOUND"} else 409
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

    @app.get("/api/audit/status", response_model=AuditStatus)
    def audit_status():
        runtime = app.state.audit_runtime
        return AuditStatus(enabled=runtime.active, stream="sceneops-audit.jsonl")

    @app.post("/api/audit/ui-events", status_code=204)
    def audit_ui_event(body: UiAuditEvent, request: Request):
        audit_event(
            "ui.event",
            request_id=getattr(request.state, "audit_request_id", None),
            ui_timestamp=body.timestamp,
            ui_type=body.type,
            ui_fields=body.fields,
        )
        return Response(status_code=204)

    app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
    app.add_exception_handler(VersionCollaborationError, version_collaboration_exception_handler)
    domains = compose_domains(app, repository, data_dir)
    app.include_router(create_workspace_router(repository, import_sample=domains.import_sample))
    app.include_router(create_folder_router(repository))
    provider = ProviderService(database)
    experience = ExperienceService(database, provider, repository.exists, redactor=Redactor())
    app.state.experience = experience
    app.include_router(create_experience_router(experience))
    project_assets = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
    app.include_router(create_project_catalog_router(project_assets))
    builtin_catalog = BuiltinAssetCatalog()
    production_preparation = ProductionPreparationService(
        candidate_providers=[
            BuiltinAssetCandidates(builtin_catalog),
            ProjectAssetCandidates(project_assets),
            ExperienceCandidates(experience),
            SkillCandidates(production_skill_catalog, production_skill_detail),
            CapabilityCandidates(),
        ],
        recommendation_provider=provider,
        repository=PreparationRepository(database),
        context_recorder=experience.record_provided,
    )
    app.include_router(create_preparation_router(production_preparation))
    app.state.production_preparation = production_preparation
    if os.environ.get('SCENEOPS_BUILD_RELEASE_ENABLED', 'true').lower() != 'false':
        def export_project(project_id):
            project = repository.get_folder_project(project_id)
            return {'root_path': project.root_path, 'name': project.name}
        exports = ExportService(data_dir / 'exports', export_project,
            agent_callback=ExportAgent(provider, redact=Redactor().redact_text,
                                       production_preparation=production_preparation),
            redact_text=Redactor().redact_text)
        app.include_router(create_export_router(exports))
        app.state.exports = exports
        async def close_exports():
            import asyncio
            await asyncio.to_thread(exports.close)
        app.add_event_handler('shutdown', close_exports)
    journey = None
    if os.environ.get('SCENEOPS_PLANNING_JOURNEY_ENABLED', 'true').lower() != 'false':
        journey = PlanningJourneyService(database, repository, provider=provider, experience=experience,
                                         production_preparation=production_preparation)
        app.include_router(create_journey_router(journey))
    app.state.planning_journey = journey
    app.include_router(create_ai_router(database, project_exists=repository.exists, experience=experience))
    app.include_router(conversation_router)
    app.include_router(create_design_ai_router())
    environment_scenes = EnvironmentSceneService(database, repository, project_assets, provider,
                                                  production_preparation=production_preparation)
    card_assets = CardAssetService(database, data_dir, repository, provider, catalog=project_assets,
                                   world_context=environment_scenes.asset_generation_context,
                                   production_preparation=production_preparation)
    app.include_router(create_card_asset_router(card_assets))
    app.include_router(create_environment_scene_router(environment_scenes))
    app.state.card_assets = card_assets
    app.state.project_assets = project_assets
    app.state.environment_scenes = environment_scenes
    if os.environ.get('SCENEOPS_VFX_SHADER_ENABLED', 'true').lower() != 'false':
        lookdev = LookdevService(database, repository, project_assets, provider,
            NodeLookdevValidator(ROOT), LookdevAssetApplication(data_dir / 'lookdev-assets', project_assets, environment_scenes),
            record_exchange=AIRepository(database).append_exchange)
        lookdev.recover_turns()
        app.include_router(create_lookdev_router(lookdev))
        app.state.lookdev = lookdev
        @app.exception_handler(LookdevError)
        async def lookdev_error(request, error):
            return JSONResponse(status_code=error.status_code,
                content={'code': error.code, 'message': error.message})

    def resolve_builtin_card(project_id, card_id):
        if journey is None:
            raise HTTPException(409, '请启用策划旅程并选择一个已创建工程的项目。')
        state = journey.get(project_id)
        if state.technical_plan is None or not state.versions:
            raise HTTPException(409, '请先确认策划和技术方案，创建游戏工程后即可采用内置资产。')
        selected = card_id or state.active_card_id or 'world-3d'
        card = next((item for item in state.cards if item.id == selected), None)
        if card is None:
            raise HTTPException(409, '请先进入一张制作卡片，再采用内置资产。')
        return card
    builtin_projects = BuiltinProjectAssets(builtin_catalog, card_assets, project_assets,
                                           repository, resolve_builtin_card)
    def adopt_builtin_for_scene(project_id, asset_id):
        entry = builtin_catalog.entry(asset_id)
        with builtin_catalog.adoption_lock:
            return builtin_projects.adopt(entry, builtin_catalog.file(asset_id, 'glb'),
                AdoptBuiltinAsset(project_id=project_id))
    environment_scenes.builtin_asset_adopt = adopt_builtin_for_scene
    app.include_router(create_builtin_asset_router(builtin_catalog, builtin_projects.adopt))
    app.state.builtin_assets = builtin_catalog
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
            project_demo_context=journey.project_demo_context if journey else None,
            production_card_context=journey.production_card_context if journey else None,
            project_assets=project_assets, environment_scenes=environment_scenes,
            lookdev=getattr(app.state, "lookdev", None),
            builtin_asset_install=builtin_projects.install_pack, experience=experience,
            builtin_asset_install_selected=builtin_projects.install_selected,
            builtin_project_install_selected=builtin_projects.install_selected_in_project,
            project_asset_install_selected=builtin_projects.install_selected_project_assets,
            production_preparation=production_preparation,
            export_context=(app.state.exports.native_context if hasattr(app.state, 'exports') else None))
        if hasattr(app.state, 'exports'):
            app.state.exports.native_agent = NativeExportPort(agent_tasks)
            app.add_event_handler('startup', app.state.exports.native_agent.start)
        app.include_router(create_agent_task_router(agent_tasks))
        app.include_router(create_production_router(agent_tasks))
        app.state.agent_tasks = agent_tasks
        if journey:
            from sceneops_ai_agents import production_snapshot
            journey.production_snapshot = lambda project_id: production_snapshot(agent_tasks, project_id)
        if hasattr(app.state, 'lookdev'):
            def material_applied(project_id, result):
                asset = project_assets.get(project_id, result.asset_id)
                if asset.workspace_id:
                    agent_tasks.game.invalidate_project_workspace(project_id, asset.workspace_id)
            app.state.lookdev.on_applied = material_applied
        app.add_event_handler("shutdown", agent_tasks.close)
    conversation_memory = AIRepository(database)

    def resolve_memory_source(project_id, source_id):
        try:
            source = conversation_memory.memory_source(project_id, source_id)
            if source is None and journey is not None and project_id is not None:
                source = journey.memory_source(project_id, source_id)
            tasks = getattr(app.state, 'agent_tasks', None)
            if source is None and tasks is not None and project_id is not None:
                source = tasks.memory_source(project_id, source_id)
            return source
        except ProjectScopeError as error:
            raise ExperienceError(error.code, error.message, error.status_code) from error

    def read_project_memory(project_id):
        if journey is None:
            return []
        try:
            repository.get_folder_project(project_id)
        except FolderProjectRequired:
            # Legacy conversations have supplemental memory but no planning direction.
            return []
        except ProjectScopeError as error:
            raise ExperienceError(error.code, error.message, error.status_code) from error
        return journey.project_memory(project_id)

    experience.set_memory_providers(resolve_memory_source,
        project_reader=read_project_memory,
        project_writer=journey.update_project_memory if journey else None)
    experience.set_busy_provider(lambda project_id: bool(
        (journey and project_id in journey.busy) or
        (getattr(app.state, 'agent_tasks', None) and
         app.state.agent_tasks.is_project_busy(project_id))))
    app.add_event_handler("startup", experience.start)
    app.add_event_handler("shutdown", experience.close)
    return app
