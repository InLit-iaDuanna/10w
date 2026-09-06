"""Versioned Three.js environment drafts assembled from project-library assets."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnvironmentTransform(EnvironmentModel):
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_y_deg: float = 0.0
    scale: float = Field(default=1.0, gt=0.01, le=100)

    @field_validator("position_m")
    @classmethod
    def finite_position(cls, value: tuple[float, float, float]):
        if any(not math.isfinite(item) or abs(item) > 10000 for item in value):
            raise ValueError("场景位置必须是有限值且位于 10000 米范围内。")
        return value

    @field_validator("rotation_y_deg")
    @classmethod
    def finite_rotation(cls, value: float):
        if not math.isfinite(value) or abs(value) > 360000:
            raise ValueError("旋转角度无效。")
        return value


class EnvironmentObject(EnvironmentModel):
    id: str
    asset_id: str
    asset_version: int = Field(ge=1)
    source_asset_id: str
    title: str
    transform: EnvironmentTransform


class EnvironmentMessage(EnvironmentModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: str = Field(default_factory=_now)
    provider: str | None = None
    model: str | None = None


class WorldScaleProfile(EnvironmentModel):
    """Project-wide spatial conventions shared by assets and scene assembly."""
    unit: Literal["meter"] = "meter"
    up_axis: Literal["Y"] = "Y"
    handedness: Literal["right"] = "right"
    grid_step_m: float = Field(default=1.0, gt=0)
    reference_human_height_m: float = Field(default=1.8, gt=0)
    default_object_spacing_m: float = Field(default=3.0, gt=0)


class EnvironmentScene(EnvironmentModel):
    scene_id: str
    project_id: str
    version: int = Field(ge=0)
    objects: list[EnvironmentObject] = Field(default_factory=list, max_length=200)
    history: list[EnvironmentMessage] = Field(default_factory=list, max_length=200)
    scale_profile: WorldScaleProfile = Field(default_factory=WorldScaleProfile)
    mode: Literal["live"] = "live"
    updated_at: str = Field(default_factory=_now)


class ManualPlacementRequest(EnvironmentModel):
    expected_version: int = Field(ge=0)
    asset_id: str = Field(min_length=1)
    asset_version: int | None = Field(default=None, ge=1)
    position_m: tuple[float, float, float] | None = None


class TransformObjectRequest(EnvironmentModel):
    expected_version: int = Field(ge=0)
    transform: EnvironmentTransform


class RemoveObjectRequest(EnvironmentModel):
    expected_version: int = Field(ge=0)


class AiPlacement(EnvironmentModel):
    asset_id: str = Field(min_length=1)
    asset_version: int | None = Field(default=None, ge=1)
    position_m: tuple[float, float, float]
    rotation_y_deg: float = 0.0
    scale: float = Field(default=1.0, gt=0.01, le=100)

    @field_validator("position_m")
    @classmethod
    def finite_position(cls, value: tuple[float, float, float]):
        return EnvironmentTransform(position_m=value).position_m


class AiEnvironmentPlan(EnvironmentModel):
    summary: str = Field(min_length=1, max_length=1200)
    replace_existing: bool = False
    placements: list[AiPlacement] = Field(min_length=1, max_length=64)


class AiBuildRequest(EnvironmentModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    expected_version: int = Field(ge=0)
    prompt: str = Field(min_length=1, max_length=8000)
    retry_failed: bool = False


class AiBuildResult(EnvironmentModel):
    scene: EnvironmentScene
    summary: str
    provider: str
    model: str
    reused: bool = False


class EnvironmentSceneError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class EnvironmentSceneService:
    def __init__(self, database_path: str | Path, workspace, catalog, provider):
        self.database_path = Path(database_path)
        self.workspace = workspace
        self.catalog = catalog
        self.provider = provider
        self._lock = Lock()
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS environment_scene_versions (
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, version));
                CREATE TABLE IF NOT EXISTS environment_ai_requests (
                    project_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    request_json TEXT,
                    status TEXT NOT NULL,
                    result_version INTEGER,
                    summary TEXT,
                    provider TEXT,
                    model TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, request_id));
            """)
            columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(environment_ai_requests)"
            )}
            if "request_json" not in columns:
                connection.execute("ALTER TABLE environment_ai_requests ADD COLUMN request_json TEXT")

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _require_project(self, project_id: str) -> None:
        if not self.workspace.exists(project_id):
            raise EnvironmentSceneError("PROJECT_NOT_FOUND", "当前项目不存在。", status_code=404)

    @staticmethod
    def _empty(project_id: str) -> EnvironmentScene:
        suffix = project_id.removeprefix("prj_")
        return EnvironmentScene(scene_id="scene_" + suffix, project_id=project_id, version=0)

    def get(self, project_id: str, version: int | None = None) -> EnvironmentScene:
        self._require_project(project_id)
        with self._connect() as connection:
            if version is None:
                row = connection.execute(
                    "SELECT payload FROM environment_scene_versions WHERE project_id=? ORDER BY version DESC LIMIT 1",
                    (project_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT payload FROM environment_scene_versions WHERE project_id=? AND version=?",
                    (project_id, version),
                ).fetchone()
        if row is None:
            if version not in (None, 0):
                raise EnvironmentSceneError("SCENE_VERSION_NOT_FOUND", "场景版本不存在。", status_code=404)
            return self._empty(project_id)
        return EnvironmentScene.model_validate_json(row["payload"])

    def asset_generation_context(self, project_id: str) -> dict:
        """Read-only project background supplied to every fresh asset session."""
        scene = self.get(project_id)
        assets = []
        for entry in self.catalog.list(project_id):
            version = next(item for item in entry.versions
                           if item.source_version == entry.current_version)
            assets.append({
                "name": entry.title,
                "dimensions_m": version.dimensions_m,
                "source_type": entry.source_type,
            })
        return {
            "coordinate_system": scene.scale_profile.model_dump(mode="json"),
            "existing_assets": assets,
            "scene_object_count": len(scene.objects),
            "instruction": (
                "这些是项目背景与尺度约定，不是上一个资产的对话记录。"
                "新资产应与它们的量级匹配。"
            ),
        }

    def _save(self, scene: EnvironmentScene, expected_version: int) -> EnvironmentScene:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT MAX(version) AS version FROM environment_scene_versions WHERE project_id=?",
                (scene.project_id,),
            ).fetchone()
            current = int(row["version"] or 0)
            if current != expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已在另一操作中更新，请重新读取。")
            saved = scene.model_copy(update={"version": current + 1, "updated_at": _now()})
            connection.execute(
                "INSERT INTO environment_scene_versions(project_id,version,payload,created_at) VALUES(?,?,?,?)",
                (saved.project_id, saved.version, saved.model_dump_json(), saved.updated_at),
            )
        return saved

    @staticmethod
    def _next_position(count: int) -> tuple[float, float, float]:
        column = count % 5
        row = count // 5
        return ((column - 2) * 3.0, 0.0, -row * 3.0)

    def _asset_version(self, project_id: str, asset_id: str, version: int | None):
        try:
            entry = self.catalog.get(project_id, asset_id)
        except LookupError as error:
            raise EnvironmentSceneError("ASSET_NOT_FOUND", "资产不在当前项目资产库。", status_code=404) from error
        selected = version or entry.current_version
        if not any(item.source_version == selected for item in entry.versions):
            raise EnvironmentSceneError("ASSET_VERSION_NOT_FOUND", "资产库中没有所选版本。", status_code=404)
        return entry, selected

    def add_object(self, project_id: str, request: ManualPlacementRequest) -> EnvironmentScene:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再摆放。")
            entry, version = self._asset_version(project_id, request.asset_id, request.asset_version)
            placed = EnvironmentObject(
                id="sobj_" + uuid4().hex,
                asset_id=entry.id,
                asset_version=version,
                source_asset_id=entry.source_asset_id,
                title=entry.title,
                transform=EnvironmentTransform(
                    position_m=request.position_m or self._next_position(len(scene.objects))
                ),
            )
            return self._save(scene.model_copy(update={"objects": [*scene.objects, placed]}), scene.version)

    def transform_object(self, project_id: str, object_id: str,
                         request: TransformObjectRequest) -> EnvironmentScene:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再调整。")
            if not any(item.id == object_id for item in scene.objects):
                raise EnvironmentSceneError("SCENE_OBJECT_NOT_FOUND", "场景对象不存在。", status_code=404)
            objects = [item.model_copy(update={"transform": request.transform})
                       if item.id == object_id else item for item in scene.objects]
            return self._save(scene.model_copy(update={"objects": objects}), scene.version)

    def remove_object(self, project_id: str, object_id: str,
                      request: RemoveObjectRequest) -> EnvironmentScene:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再移除。")
            objects = [item for item in scene.objects if item.id != object_id]
            if len(objects) == len(scene.objects):
                raise EnvironmentSceneError("SCENE_OBJECT_NOT_FOUND", "场景对象不存在。", status_code=404)
            return self._save(scene.model_copy(update={"objects": objects}), scene.version)

    def _claim_ai(self, project_id: str, request: AiBuildRequest):
        request_json = request.model_dump_json(exclude={"retry_failed"})
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM environment_ai_requests WHERE project_id=? AND request_id=?",
                (project_id, request.request_id),
            ).fetchone()
            if row and (row["request_json"] is None
                        or json.loads(row["request_json"]) != json.loads(request_json)):
                raise EnvironmentSceneError(
                    "AI_BUILD_REQUEST_CONFLICT",
                    "同一请求 ID 不能更改场景目标或基准版本，请重新发起请求。",
                )
            if row and row["status"] == "completed":
                return AiBuildResult(
                    scene=self.get(project_id, row["result_version"]),
                    summary=row["summary"], provider=row["provider"], model=row["model"], reused=True,
                )
            if row and row["status"] == "running":
                raise EnvironmentSceneError("AI_BUILD_RUNNING", "这次 AI 场景搭建仍在执行。")
            if row and not request.retry_failed:
                raise EnvironmentSceneError("AI_BUILD_RETRY_REQUIRED", "这次搭建曾失败，请明确点击重试。")
            now = _now()
            if row:
                connection.execute(
                    """UPDATE environment_ai_requests SET status='running',result_version=NULL,summary=NULL,
                       provider=NULL,model=NULL,error=NULL,request_json=?,updated_at=?
                       WHERE project_id=? AND request_id=?""",
                    (request_json, now, project_id, request.request_id),
                )
            else:
                connection.execute(
                    """INSERT INTO environment_ai_requests(
                           project_id,request_id,request_json,status,updated_at
                       ) VALUES(?,?,?,?,?)""",
                    (project_id, request.request_id, request_json, "running", now),
                )
        return None

    def _finish_ai(self, project_id: str, request_id: str, *, result: AiBuildResult | None = None,
                   error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE environment_ai_requests SET status=?,result_version=?,summary=?,provider=?,model=?,
                   error=?,updated_at=? WHERE project_id=? AND request_id=?""",
                ("failed" if error else "completed", result.scene.version if result else None,
                 result.summary if result else None, result.provider if result else None,
                 result.model if result else None, error, _now(), project_id, request_id),
            )

    async def ai_build(self, project_id: str, request: AiBuildRequest) -> AiBuildResult:
        self._require_project(project_id)
        reused = self._claim_ai(project_id, request)
        if reused:
            return reused
        try:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再让 AI 搭建。")
            assets = self.catalog.list(project_id)
            if not assets:
                raise EnvironmentSceneError("ASSET_LIBRARY_EMPTY", "资产库为空，请先保存至少一个模型。")
            catalog = [{
                "asset_id": item.id,
                "title": item.title,
                "current_version": item.current_version,
                "dimensions_m": next(version.dimensions_m for version in item.versions
                                      if version.source_version == item.current_version),
            } for item in assets]
            prompt = (
                "你是 Three.js 场景搭建规划器。根据用户目标，只使用给定资产库中的 asset_id，"
                "输出真实可执行的摆放清单。坐标单位为米、Y 轴向上；物体通常放在地面 Y=0。"
                "不要生成代码、路径、文件操作或不存在的资产。新目标若是在整体重排场景，"
                "replace_existing=true；若只是增加内容则为 false。最多 64 个对象。\n"
                f"项目尺度：{scene.scale_profile.model_dump_json()}\n"
                f"现有场景：{scene.model_dump_json()}\n资产库：{json.dumps(catalog, ensure_ascii=False)}\n"
                f"用户目标：{request.prompt}"
            )
            settings = self.provider.settings()
            raw = await self.provider.structured(
                prompt, AiEnvironmentPlan.model_json_schema(), purpose="threejs-environment-build"
            )
            plan = AiEnvironmentPlan.model_validate(raw)
            created = []
            for placement in plan.placements:
                entry, version = self._asset_version(project_id, placement.asset_id, placement.asset_version)
                created.append(EnvironmentObject(
                    id="sobj_" + uuid4().hex,
                    asset_id=entry.id,
                    asset_version=version,
                    source_asset_id=entry.source_asset_id,
                    title=entry.title,
                    transform=EnvironmentTransform(
                        position_m=placement.position_m,
                        rotation_y_deg=placement.rotation_y_deg,
                        scale=placement.scale,
                    ),
                ))
            objects = created if plan.replace_existing else [*scene.objects, *created]
            if len(objects) > 200:
                raise EnvironmentSceneError("SCENE_OBJECT_LIMIT", "场景对象超过 200 个，请缩小本轮范围。", status_code=422)
            history = [*scene.history,
                EnvironmentMessage(id="msg_" + uuid4().hex, role="user", text=request.prompt),
                EnvironmentMessage(id="msg_" + uuid4().hex, role="assistant", text=plan.summary,
                                   provider=settings.provider, model=settings.model)]
            saved = self._save(scene.model_copy(update={"objects": objects, "history": history[-200:]}), scene.version)
            result = AiBuildResult(scene=saved, summary=plan.summary,
                                   provider=settings.provider, model=settings.model)
            self._finish_ai(project_id, request.request_id, result=result)
            return result
        except Exception as error:
            self._finish_ai(project_id, request.request_id, error=str(error))
            raise


def create_environment_scene_router(service: EnvironmentSceneService) -> APIRouter:
    router = APIRouter(prefix="/api/environment-scenes", tags=["environment-scenes"])

    @router.get("/{project_id}", response_model=EnvironmentScene, operation_id="getEnvironmentScene")
    def get_scene(project_id: str, version: int | None = Query(default=None, ge=0)):
        return service.get(project_id, version)

    @router.post("/{project_id}/objects", response_model=EnvironmentScene,
                 operation_id="placeEnvironmentObject")
    def place_object(project_id: str, request: ManualPlacementRequest):
        return service.add_object(project_id, request)

    @router.put("/{project_id}/objects/{object_id}", response_model=EnvironmentScene,
                operation_id="transformEnvironmentObject")
    def transform_object(project_id: str, object_id: str, request: TransformObjectRequest):
        return service.transform_object(project_id, object_id, request)

    @router.delete("/{project_id}/objects/{object_id}", response_model=EnvironmentScene,
                   operation_id="removeEnvironmentObject")
    def remove_object(project_id: str, object_id: str, request: RemoveObjectRequest):
        return service.remove_object(project_id, object_id, request)

    @router.post("/{project_id}/ai-build", response_model=AiBuildResult,
                 operation_id="buildEnvironmentWithAi")
    async def ai_build(project_id: str, request: AiBuildRequest):
        return await service.ai_build(project_id, request)

    return router
