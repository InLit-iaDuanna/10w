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

from sceneops_project_workspace import SqliteWorkspaceRepository, create_workspace_router
from conversation_home import create_ai_router, router as conversation_router
from sceneops_design_ai import create_ai_router as create_design_ai_router
from sceneops_production_planner import PlannerDomainError
from concept_lab import ConceptLabError, concept_lab_error_handler
from version_collaboration import VersionCollaborationError, version_collaboration_exception_handler
from .domains import compose_domains

ROOT = Path(__file__).resolve().parents[2]


class Health(BaseModel):
    status: str = "ready"
    storage: str = "sqlite"
    default_workspace: str = "empty"
    external_execution: str = "not_started"


def create_app() -> FastAPI:
    data_dir = Path(os.environ.get("SCENEOPS_DATA_DIR", str(ROOT / ".local"))).resolve()
    database = data_dir / "sceneops.sqlite3"
    repository = SqliteWorkspaceRepository(database)
    app = FastAPI(title="SceneOps Forge API", version="0.2.0")
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
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse(status_code=415, content={"code": "JSON_REQUIRED", "message": "写入请求必须使用 JSON。"})
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
        return Health()

    app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
    app.add_exception_handler(VersionCollaborationError, version_collaboration_exception_handler)
    domains = compose_domains(app, repository, data_dir)
    app.include_router(create_workspace_router(repository, import_sample=domains.import_sample))
    app.include_router(create_ai_router(database, project_exists=repository.exists))
    app.include_router(conversation_router)
    app.include_router(create_design_ai_router())
    app.state.workspace_repository = repository
    app.state.project_domains = domains
    return app
