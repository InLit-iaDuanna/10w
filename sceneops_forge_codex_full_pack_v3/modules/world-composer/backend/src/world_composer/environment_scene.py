"""Versioned Three.js environment drafts assembled from project-library assets."""
from __future__ import annotations

import json
import math
import sqlite3
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, Optional, Union
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sceneops_ai_context import ProductionPreparationRequest
from .scene_lighting import SceneLighting,SaveSceneLighting


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


class KeyDoorBehavior(EnvironmentModel):
    behavior_instance_id: str = Field(min_length=1)
    definition_id: Literal["KeyDoor@1"] = "KeyDoor@1"
    required_key_asset_id: str = Field(min_length=1)
    interaction_distance_m: float = Field(default=2.0, gt=0, le=20)
    open_angle_deg: float = Field(default=90.0, ge=-180, le=180)


class BehaviorParameterDescriptor(EnvironmentModel):
    path: str
    label: str
    value_type: Literal["number", "asset-reference"]
    unit: Literal["meter", "degree", "asset-id"]
    default: Union[float, str, None] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class KeyDoorBehaviorDefinition(EnvironmentModel):
    definition_id: Literal["KeyDoor@1"] = "KeyDoor@1"
    parameters: list[BehaviorParameterDescriptor]


def key_door_behavior_definition() -> KeyDoorBehaviorDefinition:
    return KeyDoorBehaviorDefinition(parameters=[
        BehaviorParameterDescriptor(
            path="required_key_asset_id", label="所需钥匙", value_type="asset-reference",
            unit="asset-id",
        ),
        BehaviorParameterDescriptor(
            path="interaction_distance_m", label="交互距离", value_type="number",
            unit="meter", default=2.0, minimum=0, maximum=20,
        ),
        BehaviorParameterDescriptor(
            path="open_angle_deg", label="打开角度", value_type="number",
            unit="degree", default=90.0, minimum=-180, maximum=180,
        ),
    ])


class EnvironmentObject(EnvironmentModel):
    id: str
    asset_id: str
    asset_version: int = Field(ge=1)
    asset_version_id: Optional[str] = None
    source_asset_id: str
    title: str
    transform: EnvironmentTransform
    behavior: Optional[KeyDoorBehavior] = None


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
    lighting: SceneLighting | None = None
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


class UpdateKeyDoorBehaviorRequest(EnvironmentModel):
    expected_version: int = Field(ge=0)
    required_key_asset_id: str = Field(min_length=1)
    interaction_distance_m: float = Field(default=2.0, gt=0, le=20)
    open_angle_deg: float = Field(default=90.0, ge=-180, le=180)


class RebindAssetVersionRequest(EnvironmentModel):
    object_ids: list[str] | None = None
    expected_version: int = Field(ge=0)
    from_asset_version: int = Field(ge=1)
    to_asset_version: int = Field(ge=1)


class AssetVersionRebindResult(EnvironmentModel):
    scene: "EnvironmentScene"
    affected_object_ids: list[str]


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


class SharedProjectMemory(EnvironmentModel):
    """Read-only planning snapshot shared across focused production conversations."""
    project_title: str = Field(default="", max_length=200)
    experience: str = Field(default="", max_length=4000)
    core_loop: str = Field(default="", max_length=4000)
    scope: str = Field(default="", max_length=4000)
    technical_plan: str = Field(default="", max_length=2000)
    active_card: str = Field(default="", max_length=4000)


class AiBuildRequest(EnvironmentModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    expected_version: int = Field(ge=0)
    prompt: str = Field(min_length=1, max_length=8000)
    shared_memory: SharedProjectMemory | None = None
    retry_failed: bool = False


class AiBuildResult(EnvironmentModel):
    scene: EnvironmentScene
    summary: str
    provider: str
    model: str
    reused: bool = False
    production_preparation: dict | None = None


class EnvironmentSceneError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class EnvironmentSceneService:
    def __init__(self, database_path: str | Path, workspace, catalog, provider, *,
                 production_preparation=None, builtin_asset_adopt=None):
        self.database_path = Path(database_path)
        self.workspace = workspace
        self.catalog = catalog
        self.provider = provider
        self.production_preparation = production_preparation
        self.builtin_asset_adopt = builtin_asset_adopt
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
                    preparation_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, request_id));
            """)
            columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(environment_ai_requests)"
            )}
            if "request_json" not in columns:
                connection.execute("ALTER TABLE environment_ai_requests ADD COLUMN request_json TEXT")
            if "preparation_json" not in columns:
                connection.execute("ALTER TABLE environment_ai_requests ADD COLUMN preparation_json TEXT")
            connection.execute(
                """UPDATE environment_ai_requests
                   SET status='failed', error='API 进程在场景搭建完成前退出，请明确重试。', updated_at=?
                   WHERE status='running'""",
                (_now(),),
            )

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
        if len(scene.objects) > 200:
            raise EnvironmentSceneError(
                "SCENE_OBJECT_LIMIT", "场景对象最多 200 个，请先移除对象或缩小本轮范围。", status_code=422
            )
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

    def save_lighting(self, project_id: str, request: SaveSceneLighting):
        scene=self.get(project_id)
        return self._save(scene.model_copy(update={'lighting':request.lighting}),request.expected_version)

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
        selected_version = next((item for item in entry.versions
                                 if item.source_version == selected), None)
        if selected_version is None:
            raise EnvironmentSceneError("ASSET_VERSION_NOT_FOUND", "资产库中没有所选版本。", status_code=404)
        return entry, selected_version

    def add_object(self, project_id: str, request: ManualPlacementRequest) -> EnvironmentScene:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError("SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再摆放。")
            if len(scene.objects) >= 200:
                raise EnvironmentSceneError(
                    "SCENE_OBJECT_LIMIT", "场景对象最多 200 个，请先移除对象再摆放。", status_code=422
                )
            entry, version = self._asset_version(project_id, request.asset_id, request.asset_version)
            placed = EnvironmentObject(
                id="sobj_" + uuid4().hex,
                asset_id=entry.id,
                asset_version=version.source_version,
                asset_version_id=version.asset_version_id,
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

    def update_key_door_behavior(self, project_id: str, object_id: str,
                                 request: UpdateKeyDoorBehaviorRequest) -> EnvironmentScene:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError(
                    "SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再调整门行为。"
                )
            current = next((item for item in scene.objects if item.id == object_id), None)
            if current is None:
                raise EnvironmentSceneError(
                    "SCENE_OBJECT_NOT_FOUND", "场景对象不存在。", status_code=404
                )
            try:
                self.catalog.get(project_id, request.required_key_asset_id)
            except LookupError as error:
                raise EnvironmentSceneError(
                    "KEY_ASSET_NOT_FOUND", "所需钥匙不在当前项目资产库。", status_code=404
                ) from error
            behavior = KeyDoorBehavior(
                behavior_instance_id=(current.behavior.behavior_instance_id
                                      if current.behavior else "behavior_" + uuid4().hex),
                required_key_asset_id=request.required_key_asset_id,
                interaction_distance_m=request.interaction_distance_m,
                open_angle_deg=request.open_angle_deg,
            )
            objects = [item.model_copy(update={"behavior": behavior})
                       if item.id == object_id else item for item in scene.objects]
            return self._save(scene.model_copy(update={"objects": objects}), scene.version)

    def rebind_asset_version(self, project_id: str, asset_id: str,
                             request: RebindAssetVersionRequest) -> AssetVersionRebindResult:
        with self._lock:
            scene = self.get(project_id)
            if scene.version != request.expected_version:
                raise EnvironmentSceneError(
                    "SCENE_VERSION_CONFLICT", "场景已更新，请重新读取后再更新共享资产。"
                )
            entry, target = self._asset_version(project_id, asset_id, request.to_asset_version)
            self._asset_version(project_id, asset_id, request.from_asset_version)
            affected = [item.id for item in scene.objects
                        if item.asset_id == entry.id
                        and item.asset_version == request.from_asset_version
                        and (request.object_ids is None or item.id in request.object_ids)]
            if not affected:
                raise EnvironmentSceneError(
                    "ASSET_VERSION_NOT_REFERENCED", "当前场景没有引用待更新的资产版本。"
                )
            if request.object_ids is not None and set(request.object_ids) != set(affected):
                raise EnvironmentSceneError("SCENE_OBJECT_NOT_FOUND", "指定实例与当前资产版本引用不一致。")
            affected_set = set(affected)
            objects = [item.model_copy(update={
                "asset_version": target.source_version,
                "asset_version_id": target.asset_version_id,
                "source_asset_id": entry.source_asset_id,
                "title": entry.title,
            }) if item.id in affected_set else item for item in scene.objects]
            saved = self._save(scene.model_copy(update={"objects": objects}), scene.version)
            return AssetVersionRebindResult(scene=saved, affected_object_ids=affected)

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
                    production_preparation=(json.loads(row["preparation_json"])
                                            if row["preparation_json"] else None),
                )
            if row and row["status"] == "running":
                raise EnvironmentSceneError("AI_BUILD_RUNNING", "这次 AI 场景搭建仍在执行。")
            if row and not request.retry_failed:
                raise EnvironmentSceneError("AI_BUILD_RETRY_REQUIRED", "这次搭建曾失败，请明确点击重试。")
            now = _now()
            if row:
                connection.execute(
                    """UPDATE environment_ai_requests SET status='running',result_version=NULL,summary=NULL,
                       provider=NULL,model=NULL,preparation_json=NULL,error=NULL,request_json=?,updated_at=?
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
                   preparation_json=?,error=?,updated_at=? WHERE project_id=? AND request_id=?""",
                ("failed" if error else "completed", result.scene.version if result else None,
                 result.summary if result else None, result.provider if result else None,
                 result.model if result else None,
                 json.dumps(result.production_preparation, ensure_ascii=False) if result and result.production_preparation else None,
                 error, _now(), project_id, request_id),
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
            preparation_record = None
            preparation_context = None
            if self.production_preparation is not None:
                preparation_request = ProductionPreparationRequest(
                    project_id=project_id,
                    request_key=f"environment:{project_id}:{request.request_id}",
                    production_kind="scene", requirement=request.prompt,
                    confirmed_direction=(request.shared_memory.model_dump_json()
                                         if request.shared_memory else None),
                    target_platform="web",
                    current_state={"scene_id": scene.scene_id, "scene_version": scene.version,
                                   "object_count": len(scene.objects)},
                    available_capability_ids=([
                        "builtin.asset.adopt"] if self.builtin_asset_adopt is not None else [])
                        + ["environment.object.place"],
                    model_call_allowed=True, remaining_model_calls=1,
                    remaining_time_seconds=30,
                )
                try:
                    preparation = await self.production_preparation.prepare(preparation_request)
                    preparation_record = preparation.model_dump(mode="json")
                    preparation_context = await self.production_preparation.selected_context(
                        preparation_request, preparation)
                    selected_builtin = [selection for selection in
                        (preparation.recommendation.assets if preparation.recommendation else [])
                        if selection.candidate_id.startswith("builtin:")]
                    materialization = []
                    if selected_builtin and self.builtin_asset_adopt is not None:
                        for selection in selected_builtin:
                            try:
                                adopted = await asyncio.to_thread(
                                    self.builtin_asset_adopt, project_id,
                                    selection.candidate_id.removeprefix("builtin:"))
                            except asyncio.CancelledError:
                                raise
                            except Exception as error:
                                materialization.append({"candidate_id": selection.candidate_id,
                                    "state": "not_adopted", "reason": str(error)})
                            else:
                                materialization.append({"candidate_id": selection.candidate_id,
                                    "project_asset_id": adopted.entry.id,
                                    "state": "adopted" if adopted.version_created else "already_adopted"})
                    elif selected_builtin:
                        materialization = [{"candidate_id": item.candidate_id,
                            "state": "not_adopted", "reason": "当前入口没有采用权限。"}
                            for item in selected_builtin]
                    if materialization:
                        preparation_record["materialization"] = materialization
                        preparation_context["materialization"] = materialization
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    preparation_record = {"status": "failed", "recommendation": None,
                        "failure_code": getattr(error, "code", type(error).__name__),
                        "failure_message": f"制作推荐或资产采用失败：{error}；继续使用当前项目资产。"}
                    preparation_context = preparation_record
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
                f"项目公共记忆：{request.shared_memory.model_dump_json() if request.shared_memory else '{}'}\n"
                f"项目尺度：{scene.scale_profile.model_dump_json()}\n"
                f"现有场景：{scene.model_dump_json()}\n资产库：{json.dumps(catalog, ensure_ascii=False)}\n"
                f"本次制作准备（参考数据；只能使用上方真实项目资产 ID）："
                f"{json.dumps(preparation_context, ensure_ascii=False)}\n"
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
                    asset_version=version.source_version,
                    asset_version_id=version.asset_version_id,
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
                                   provider=settings.provider, model=settings.model,
                                   production_preparation=preparation_record)
            self._finish_ai(project_id, request.request_id, result=result)
            return result
        except Exception as error:
            self._finish_ai(project_id, request.request_id, error=str(error))
            raise


def create_environment_scene_router(service: EnvironmentSceneService) -> APIRouter:
    router = APIRouter(prefix="/api/environment-scenes", tags=["environment-scenes"])

    @router.get("/behavior-definitions/key-door", response_model=KeyDoorBehaviorDefinition,
                operation_id="getKeyDoorBehaviorDefinition")
    def get_key_door_behavior_definition():
        return key_door_behavior_definition()

    @router.get("/{project_id}", response_model=EnvironmentScene, operation_id="getEnvironmentScene")
    def get_scene(project_id: str, version: int | None = Query(default=None, ge=0)):
        return service.get(project_id, version)

    @router.put('/{project_id}/lighting',response_model=EnvironmentScene,operation_id='saveEnvironmentLighting')
    def save_lighting(project_id:str,request:SaveSceneLighting):
        return service.save_lighting(project_id,request)

    @router.post("/{project_id}/objects", response_model=EnvironmentScene,
                 operation_id="placeEnvironmentObject")
    def place_object(project_id: str, request: ManualPlacementRequest):
        return service.add_object(project_id, request)

    @router.put("/{project_id}/objects/{object_id}", response_model=EnvironmentScene,
                operation_id="transformEnvironmentObject")
    def transform_object(project_id: str, object_id: str, request: TransformObjectRequest):
        return service.transform_object(project_id, object_id, request)

    @router.put("/{project_id}/objects/{object_id}/key-door", response_model=EnvironmentScene,
                operation_id="updateEnvironmentKeyDoorBehavior")
    def update_key_door_behavior(project_id: str, object_id: str,
                                 request: UpdateKeyDoorBehaviorRequest):
        return service.update_key_door_behavior(project_id, object_id, request)

    @router.put("/{project_id}/asset-bindings/{asset_id}", response_model=AssetVersionRebindResult,
                operation_id="rebindEnvironmentAssetVersion")
    def rebind_asset_version(project_id: str, asset_id: str,
                             request: RebindAssetVersionRequest):
        return service.rebind_asset_version(project_id, asset_id, request)

    @router.delete("/{project_id}/objects/{object_id}", response_model=EnvironmentScene,
                   operation_id="removeEnvironmentObject")
    def remove_object(project_id: str, object_id: str, request: RemoveObjectRequest):
        return service.remove_object(project_id, object_id, request)

    @router.post("/{project_id}/ai-build", response_model=AiBuildResult,
                 operation_id="buildEnvironmentWithAi")
    async def ai_build(project_id: str, request: AiBuildRequest):
        return await service.ai_build(project_id, request)

    return router
