"""Composition only: localhost API for the independently launchable lab."""
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
root=Path(__file__).resolve().parents[3]
for module in ("engine-unity", "build-release"):
    sys.path.insert(0,str(root/"modules"/module/"backend/src"))
from build_release import UnityBuildWorkbenchService, create_workbench_router
app=FastAPI(title="Unity Build Local Workbench",version="0.1.0")
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver"])
@app.middleware("http")
async def local_origin(request: Request, call_next):
    if request.method not in {"GET","HEAD","OPTIONS"}:
        origin=request.headers.get("origin")
        allowed={f"http://127.0.0.1:{os.getenv('WEB_PORT','4317')}", f"http://localhost:{os.getenv('WEB_PORT','4317')}"}
        if origin and origin not in allowed:
            return JSONResponse(status_code=403,content={"detail":"仅接受本地工作台来源。"})
    return await call_next(request)
service=UnityBuildWorkbenchService(Path(os.getenv("UNITY_BUILD_DB",str(Path(__file__).parent/".local/proposals.sqlite"))))
app.include_router(create_workbench_router(service))
