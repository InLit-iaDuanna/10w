"""Independent composition root; all domain handlers live in their modules."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from logic_studio import workbench_router
from world_composer import workbench_router as world_router

app = FastAPI(title="SceneOps World Logic Lab", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
allowed_origins = {
    f"http://{host}:{os.getenv(variable, default)}"
    for host in ("127.0.0.1", "localhost")
    for variable, default in (("WORLD_LOGIC_WEB_PORT", "4314"), ("WORLD_LOGIC_API_PORT", "8314"))
}


@app.middleware("http")
async def local_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in allowed_origins:
        return JSONResponse({"detail": "仅允许本地工作台来源。"}, status_code=403)
    return await call_next(request)


app.include_router(workbench_router, prefix="/api")
app.include_router(world_router, prefix="/api")
