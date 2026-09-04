"""Composition only: public module routers, localhost transport policy."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from ui_studio import create_lab_router as ui_router
from audio_studio import create_lab_router as audio_router
from vfx_shader import create_lab_router as vfx_router

app = FastAPI(title="UI、音频与特效 · 本地工作台", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
for factory in (ui_router, audio_router, vfx_router):
    app.include_router(factory())


@app.middleware("http")
async def local_origin(request: Request, call_next):
    allowed = {f"http://127.0.0.1:{os.environ.get('LAB_WEB_PORT', '4315')}",
               f"http://127.0.0.1:{os.environ.get('LAB_API_PORT', '8315')}"}
    if request.headers.get("origin") and request.headers["origin"] not in allowed:
        return JSONResponse({"detail": "仅允许本地工作台来源。"}, status_code=403)
    if request.method == "POST" and request.headers.get("content-type", "").split(";")[0] != "application/json":
        return JSONResponse({"detail": "写入请求必须使用 JSON。"}, status_code=415)
    return await call_next(request)


@app.exception_handler(ValueError)
async def invalid_value(request: Request, error: ValueError):
    return JSONResponse({"detail": str(error)}, status_code=422)


@app.get("/api/health")
def health():
    return {"status": "ready", "storage": "session-memory", "unity": "blocked", "render": "blocked"}
