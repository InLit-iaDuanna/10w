"""Local composition: existing module services with a read-only demo principal."""

import os
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from integration_center import create_demo_workbench, create_workbench_router
from observability import create_router as create_observability_router


def create_app():
    app = FastAPI(title="Integration Ops local workbench", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    token = os.environ.get("INTEGRATION_OPS_TOKEN")
    if not token:
        raise RuntimeError("Start with pnpm dev; the local proxy credential is required.")
    workbench = create_demo_workbench()

    def require_permission(permission):
        def authorize(request: Request):
            supplied = request.headers.get("x-integration-ops-token", "")
            if not secrets.compare_digest(supplied, token):
                raise HTTPException(401, "请通过工作台 Web 入口访问。")
            if permission not in {"integration:read", "observability:read", "observability:export"}:
                raise HTTPException(403, "演示工作台为只读；写入和外部恢复命令未授权。")
        return authorize

    class Access:
        authorize_project = staticmethod(workbench.authorize_project)

        def authorize_producer(self, *args):
            raise HTTPException(403, "演示工作台不接受外部事件生产者。")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse(status_code=422, content={"message": "筛选参数格式不正确，请清除筛选后重试。"})

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse(status_code=500, content={"message": "本地服务暂时不可用，请检查启动终端并重试。"})

    app.include_router(create_workbench_router(workbench, require_permission))
    app.include_router(create_observability_router(workbench.logs, require_permission, Access(),
        health_provider=lambda project: [item.model_dump(mode="json") for item in
            workbench.service.list_health(workbench.context(project), workbench.fixture_time)]))
    return app
