"""FastAPI surface for the card asset workflow."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from .card_asset_models import (CardAssetList, CardAssetProposal, CardAssetRecord,
                                CardAssetReference, LiveModelUpdateRequest,
                                LiveModelUpdateResult, ModelPlanRequest, NormalizeRequest,
                                SaveToLibraryRequest)
from asset_library import SaveProjectAssetResult


IMPORT_EXTENSIONS = {".glb": 100 * 1024 * 1024, ".fbx": 100 * 1024 * 1024}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _filename(request: Request, allowed: set[str]) -> tuple[str, str]:
    value = unquote(request.headers.get("x-sceneops-filename", ""))
    if not value or len(value) > 240 or Path(value).name != value or any(ord(item) < 32 for item in value):
        raise ValueError("文件名无效。")
    extension = Path(value).suffix.casefold()
    if extension not in allowed:
        raise ValueError("文件格式不受支持。")
    return value, extension


async def _receive(request: Request, directory: Path, maximum: int) -> Path:
    descriptor, name = tempfile.mkstemp(prefix="upload_", dir=directory)
    path = Path(name)
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > maximum:
                    raise ValueError(f"文件超过 {maximum // (1024 * 1024)} MiB 限制。")
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if size == 0:
            raise ValueError("不能导入空文件。")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def create_card_asset_router(service) -> APIRouter:
    router = APIRouter(prefix="/api/card-assets", tags=["card-assets"])

    @router.get("", response_model=CardAssetList, operation_id="listCardAssets")
    def list_assets(project_id: str = Query(...), card_id: str = Query(...)):
        return service.list(project_id, card_id)

    @router.post("/{project_id}/{card_id}/imports", response_model=CardAssetRecord, operation_id="importCardAsset")
    async def import_asset(project_id: str, card_id: str, request: Request):
        from asyncio import to_thread
        filename, extension = _filename(request, set(IMPORT_EXTENSIONS))
        session_id = request.headers.get("x-sceneops-modeling-session") or None
        if session_id is not None and (len(session_id) > 160 or not session_id.strip()):
            raise ValueError("建模会话标识无效。")
        staged = await _receive(request, service.staging_root, IMPORT_EXTENSIONS[extension])
        try:
            return await to_thread(service.import_asset, project_id, card_id, staged, filename, session_id)
        finally:
            staged.unlink(missing_ok=True)

    @router.post("/{project_id}/{card_id}/references", response_model=CardAssetReference, operation_id="uploadCardAssetReference")
    async def upload_reference(project_id: str, card_id: str, request: Request):
        from asyncio import to_thread
        filename, extension = _filename(request, set(IMAGE_TYPES))
        staged = await _receive(request, service.staging_root, 10 * 1024 * 1024)
        try:
            return await to_thread(service.add_reference, project_id, card_id, staged, filename, IMAGE_TYPES[extension])
        finally:
            staged.unlink(missing_ok=True)

    @router.post("/{project_id}/{card_id}/plans", response_model=CardAssetProposal, operation_id="planCardAsset")
    async def plan(project_id: str, card_id: str, request: ModelPlanRequest):
        return await service.plan(project_id, card_id, request)

    @router.post("/{project_id}/{card_id}/live-updates", response_model=LiveModelUpdateResult,
                 operation_id="updateLiveCardModel")
    async def live_update(project_id: str, card_id: str, request: LiveModelUpdateRequest):
        return await service.live_update(project_id, card_id, request)

    @router.post("/proposals/{proposal_id}/generate", response_model=CardAssetRecord, operation_id="generateCardAsset")
    async def generate(proposal_id: str):
        from asyncio import to_thread
        return await to_thread(service.generate, proposal_id)

    @router.post("/{asset_id}/normalize", response_model=CardAssetRecord, operation_id="normalizeCardAsset")
    async def normalize(asset_id: str, request: NormalizeRequest):
        from asyncio import to_thread
        return await to_thread(service.normalize, asset_id, request.target_extent_m)

    @router.post("/{asset_id}/library", response_model=SaveProjectAssetResult,
                 operation_id="saveCardAssetToLibrary")
    async def save_to_library(asset_id: str, request: SaveToLibraryRequest):
        from asyncio import to_thread
        return await to_thread(service.save_to_library, asset_id, request.version,
                               request.model_rotation_quaternion_xyzw)

    @router.get("/{asset_id}/files/{kind}", operation_id="readCardAssetFile")
    def file(asset_id: str, kind: str, version: int | None = Query(default=None, ge=1)):
        path, media_type = service.file(asset_id, kind, version)
        return FileResponse(path, media_type=media_type, filename=path.name if kind != "preview" else None)

    return router
