import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .codebuddy import CodeBuddyFailure, complete, model_catalog
from .schemas import AdapterError, ChatRequest, ChatResponse, ModelCatalog

router = APIRouter(prefix='/api/conversation', tags=['conversation'])

@router.get('/models', response_model=ModelCatalog)
async def models():
    return model_catalog()

@router.post('/complete', response_model=ChatResponse, responses={503: {'model': AdapterError}})
async def completion(body: ChatRequest, request: Request):
    task = asyncio.create_task(complete(body))
    try:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                raise asyncio.CancelledError()
            await asyncio.wait({task}, timeout=0.2)
        return await task
    except CodeBuddyFailure as error:
        return JSONResponse(status_code=503, content=AdapterError(code=error.code, message=str(error)).model_dump())
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, CodeBuddyFailure):
            pass
