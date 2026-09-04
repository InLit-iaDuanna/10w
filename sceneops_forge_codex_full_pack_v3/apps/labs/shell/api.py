"""Local composition only; conversation behavior belongs to conversation-home."""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from conversation_home import router

app = FastAPI(title='SceneOps Shell API', version='0.1.0')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
app.include_router(router)

@app.middleware('http')
async def local_origin(request: Request, call_next):
    if request.method not in ('GET', 'HEAD'):
        expected = f"http://127.0.0.1:{os.environ.get('LAB_WEB_PORT', '4310')}"
        if request.headers.get('origin') != expected:
            return JSONResponse(status_code=403, content={'mode': 'blocked', 'message': '仅接受当前 localhost 工作台请求。'})
    return await call_next(request)
