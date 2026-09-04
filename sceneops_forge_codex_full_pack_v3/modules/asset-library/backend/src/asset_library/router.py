from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    AssetRecord,
    AssetSearchFilter,
    AssetVersion,
    ExecutionMode,
    GateStatus,
    PublicationRequest,
    UnityStatus,
)
from .service import AssetLibraryService, AssetNotFoundError, PublicationBlockedError


def create_router(service: AssetLibraryService) -> APIRouter:
    router = APIRouter(prefix="/v1/assets", tags=["asset-library"])

    @router.get("", response_model=List[AssetRecord])
    def search_assets(
        query: str = Query("", max_length=200),
        project_id: Optional[str] = None,
        formats: List[str] = Query(default=[]),
        gate_status: Optional[GateStatus] = None,
        unity_status: Optional[UnityStatus] = None,
        has_uv: Optional[bool] = None,
        rigged: Optional[bool] = None,
        has_animations: Optional[bool] = None,
        has_lod: Optional[bool] = None,
        has_collider: Optional[bool] = None,
        has_ai_provenance: Optional[bool] = None,
        license_name: Optional[str] = None,
        min_triangles: Optional[int] = Query(None, ge=0),
        max_triangles: Optional[int] = Query(None, ge=0),
        execution_modes: List[ExecutionMode] = Query(default=[]),
    ) -> List[AssetRecord]:
        return service.search(
            AssetSearchFilter(
                project_id=project_id,
                query=query,
                formats=formats,
                gate_status=gate_status,
                unity_status=unity_status,
                has_uv=has_uv,
                rigged=rigged,
                has_animations=has_animations,
                has_lod=has_lod,
                has_collider=has_collider,
                has_ai_provenance=has_ai_provenance,
                license_name=license_name,
                min_triangles=min_triangles,
                max_triangles=max_triangles,
                execution_modes=execution_modes,
            )
        )

    @router.get("/{asset_id}", response_model=AssetRecord)
    def get_asset(asset_id: str) -> AssetRecord:
        try:
            return service.get(asset_id)
        except AssetNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "ASSET_NOT_FOUND", "asset_id": str(error)},
            )

    @router.post("/{asset_id}/versions:publish", response_model=AssetVersion)
    def publish_version(asset_id: str, request: PublicationRequest) -> AssetVersion:
        if request.asset_id != asset_id:
            raise HTTPException(status_code=400, detail={"code": "ASSET_ID_MISMATCH"})
        try:
            return service.publish(request)
        except AssetNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "ASSET_NOT_FOUND"})
        except PublicationBlockedError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "ASSET_PUBLICATION_BLOCKED", "reasons": error.reasons},
            )

    return router
