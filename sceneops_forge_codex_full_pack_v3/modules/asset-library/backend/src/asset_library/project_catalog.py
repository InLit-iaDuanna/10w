"""Project-scoped catalog for real card asset outputs."""
from __future__ import annotations

import sqlite3
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, Optional, Union
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from urllib.parse import quote
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


ModelRotationQuaternion = tuple[float, float, float, float]
MODEL_ROTATION_IDENTITY: ModelRotationQuaternion = (0.0, 0.0, 0.0, 1.0)


def _validate_model_rotation(value: ModelRotationQuaternion) -> ModelRotationQuaternion:
    if any(not math.isfinite(item) for item in value):
        raise ValueError("model rotation must contain finite values")
    length = math.sqrt(sum(item * item for item in value))
    if length < 1e-8:
        raise ValueError("model rotation quaternion cannot be zero")
    if abs(length - 1.0) > 1e-3:
        raise ValueError("model rotation quaternion must be normalized")
    return tuple(item / length for item in value)


_NAME_PREFIXES = (
    "低多边形", "低模", "高模", "卡通", "写实", "风格化", "程式化",
    "三维", "3D", "游戏用", "游戏",
)
_NAME_SUFFIXES = ("模型", "资产", "修订版", "预览版")


def simple_asset_name(value: str) -> str:
    """Return a compact display noun while preserving the source title separately."""
    name = unicodedata.normalize("NFKC", value).strip()
    name = re.split(r"[·•|｜/（(【\[]", name, maxsplit=1)[0].strip()
    changed = True
    while changed:
        changed = False
        for prefix in _NAME_PREFIXES:
            if name.casefold().startswith(prefix.casefold()) and len(name) > len(prefix):
                name = name[len(prefix):].strip(" _-")
                changed = True
                break
    for suffix in _NAME_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)].strip()
            break
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    return (name or "未命名资产")[:24]


def _unique_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    number = 2
    while f"{base} {number}" in used:
        number += 1
    return f"{base} {number}"


class ProjectAssetModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DoorMaterial(ProjectAssetModel):
    color_hex: str = Field(default="#6B4F3A", pattern=r"^#[0-9A-Fa-f]{6}$")
    roughness: float = Field(default=0.75, ge=0, le=1)
    metalness: float = Field(default=0.05, ge=0, le=1)


class DoorRecipe(ProjectAssetModel):
    """Editable source for the first supported procedural asset."""

    kind: Literal["door-v1"] = "door-v1"
    seed: Literal[0] = 0
    width_m: float = Field(default=1.2, ge=0.2, le=10)
    height_m: float = Field(default=2.2, ge=0.5, le=10)
    thickness_m: float = Field(default=0.15, ge=0.02, le=2)
    material: DoorMaterial = Field(default_factory=DoorMaterial)

    @property
    def dimensions_m(self) -> tuple[float, float, float]:
        return (self.width_m, self.height_m, self.thickness_m)


class RecipeParameterDescriptor(ProjectAssetModel):
    path: str
    label: str
    value_type: Literal["number", "color"]
    unit: Literal["meter", "ratio", "hex"]
    default: Union[float, str]
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class DoorRecipeDefinition(ProjectAssetModel):
    kind: Literal["door-v1"] = "door-v1"
    parameters: list[RecipeParameterDescriptor]


def door_recipe_definition() -> DoorRecipeDefinition:
    return DoorRecipeDefinition(parameters=[
        RecipeParameterDescriptor(path="width_m", label="宽度", value_type="number",
                                  unit="meter", default=1.2, minimum=0.2, maximum=10),
        RecipeParameterDescriptor(path="height_m", label="高度", value_type="number",
                                  unit="meter", default=2.2, minimum=0.5, maximum=10),
        RecipeParameterDescriptor(path="thickness_m", label="厚度", value_type="number",
                                  unit="meter", default=0.15, minimum=0.02, maximum=2),
        RecipeParameterDescriptor(path="material.color_hex", label="颜色", value_type="color",
                                  unit="hex", default="#6B4F3A"),
        RecipeParameterDescriptor(path="material.roughness", label="粗糙度", value_type="number",
                                  unit="ratio", default=0.75, minimum=0, maximum=1),
        RecipeParameterDescriptor(path="material.metalness", label="金属度", value_type="number",
                                  unit="ratio", default=0.05, minimum=0, maximum=1),
    ])


class RuntimeArtifactReference(ProjectAssetModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: Literal["render", "collision", "module"]
    project_relative_path: str = Field(min_length=1)
    export_name: Optional[str] = Field(default=None, min_length=1)


class ProjectAssetVersion(ProjectAssetModel):
    source_version: int = Field(ge=1)
    asset_version_id: Optional[str] = Field(default=None, min_length=1)
    source_kind: Literal["file", "procedural", "blender", "glb"] = "file"
    dimensions_m: tuple[float, float, float]
    vertex_count: int = Field(ge=0)
    triangle_count: int = Field(ge=0)
    blend_path: Optional[str] = Field(default=None, min_length=1)
    preview_path: Optional[str] = Field(default=None, min_length=1)
    fbx_path: Optional[str] = Field(default=None, min_length=1)
    recipe: Optional[DoorRecipe] = None
    parent_source_version: Optional[int] = Field(default=None, ge=1)
    geometry_source_version: int | None = Field(default=None, ge=1)
    lookdev_document_id: str | None = None
    lookdev_document_version: int | None = Field(default=None, ge=1)
    node_ids: dict[str, str] = Field(default_factory=dict)
    runtime_artifacts: list[RuntimeArtifactReference] = Field(default_factory=list)
    operation: Literal[
        "import", "generate", "normalize", "calibrate", "recipe-create", "recipe-edit", "blender-edit"
    ]
    model_rotation_quaternion_xyzw: ModelRotationQuaternion = MODEL_ROTATION_IDENTITY
    saved_at: str = Field(default_factory=_now)

    @field_validator("model_rotation_quaternion_xyzw")
    @classmethod
    def validate_rotation(cls, value: ModelRotationQuaternion) -> ModelRotationQuaternion:
        return _validate_model_rotation(value)

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_kind == "file":
            if not all((self.blend_path, self.preview_path, self.fbx_path)):
                raise ValueError("file asset versions require blend, preview, and fbx paths")
            if self.recipe is not None:
                raise ValueError("file asset versions cannot contain a procedural recipe")
        elif self.source_kind == "glb":
            if not self.asset_version_id or not self.preview_path or self.recipe is not None:
                raise ValueError("GLB versions require stable identity and a GLB source")
            if not all(math.isfinite(v) and v >= 0 for v in self.dimensions_m):
                raise ValueError("GLB dimensions must be finite and nonnegative")
            if not any(a.artifact_type == "render" for a in self.runtime_artifacts):
                raise ValueError("GLB versions require an immutable runtime artifact")
        elif self.source_kind == "blender":
            if not self.asset_version_id or not self.blend_path or not self.preview_path:
                raise ValueError("Blender versions require a stable version ID, blend source and GLB")
            if (self.recipe is not None or self.parent_source_version is None
                    or self.parent_source_version >= self.source_version):
                raise ValueError("Blender source must preserve its parent version, not an editable recipe")
            if not all(math.isfinite(v) and v > 0 for v in self.dimensions_m):
                raise ValueError("Blender dimensions must be finite and positive")
            if not any(a.artifact_type == "render" for a in self.runtime_artifacts):
                raise ValueError("Blender source requires its derived runtime artifact")
        else:
            if self.asset_version_id is None:
                raise ValueError("procedural asset versions require a stable asset_version_id")
            if self.recipe is None:
                raise ValueError("procedural asset versions require a recipe")
            if self.dimensions_m != self.recipe.dimensions_m:
                raise ValueError("procedural dimensions must be derived from the recipe")
        return self


class ProjectAssetEntry(ProjectAssetModel):
    id: str
    project_id: str
    card_id: Optional[str] = None
    workspace_id: Optional[str] = None
    source_asset_id: str
    title: str
    source_title: str | None = None
    modeling_session_id: str | None = None
    source_type: Literal["import", "generated"]
    category: Literal["model"] = "model"
    current_version: int = Field(ge=1)
    versions: list[ProjectAssetVersion] = Field(min_length=1)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @model_validator(mode="after")
    def validate_scope(self):
        if not self.card_id and not self.workspace_id:
            raise ValueError("asset entries require card_id or workspace_id")
        return self


class ProjectAssetRegistration(ProjectAssetModel):
    project_id: str = Field(min_length=1)
    card_id: Optional[str] = Field(default=None, min_length=1)
    workspace_id: Optional[str] = Field(default=None, min_length=1)
    source_asset_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    source_type: Literal["import", "generated"]
    modeling_session_id: str | None = Field(default=None, max_length=160)
    version: ProjectAssetVersion
    expected_version: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_scope(self):
        if not self.card_id and not self.workspace_id:
            raise ValueError("asset registrations require card_id or workspace_id")
        return self


class SaveProjectAssetResult(ProjectAssetModel):
    entry: ProjectAssetEntry
    version_created: bool


class RenameProjectAssetRequest(ProjectAssetModel):
    title: str = Field(min_length=1, max_length=24)
    expected_updated_at: str


class UpdateProjectAssetRecipeRequest(ProjectAssetModel):
    expected_version: int = Field(ge=1)
    recipe: DoorRecipe
    runtime_artifacts: list[RuntimeArtifactReference] = Field(default_factory=list)


class SqliteProjectAssetRepository:
    """Durable catalog records; generated files remain in their card Git worktree."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS project_asset_catalog (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_asset_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, source_asset_id));
                CREATE INDEX IF NOT EXISTS project_asset_catalog_scope
                    ON project_asset_catalog(project_id, updated_at);
            """)
        self._migrate_display_names()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate_display_names(self) -> None:
        """Upgrade earlier verbose titles once; original wording remains inspectable."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,payload FROM project_asset_catalog ORDER BY project_id,updated_at,id"
            ).fetchall()
            used_by_project: dict[str, set[str]] = {}
            for row in rows:
                entry = ProjectAssetEntry.model_validate_json(row["payload"])
                used = used_by_project.setdefault(entry.project_id, set())
                title = _unique_name(simple_asset_name(entry.title), used)
                used.add(title)
                source_title = entry.source_title or entry.title
                if title == entry.title and entry.source_title is not None:
                    continue
                migrated = entry.model_copy(update={"title": title, "source_title": source_title})
                connection.execute(
                    "UPDATE project_asset_catalog SET payload=? WHERE id=?",
                    (migrated.model_dump_json(), entry.id),
                )

    def find_source(self, project_id: str, source_asset_id: str) -> ProjectAssetEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM project_asset_catalog WHERE project_id=? AND source_asset_id=?",
                (project_id, source_asset_id),
            ).fetchone()
        return ProjectAssetEntry.model_validate_json(row["payload"]) if row else None

    def get(self, entry_id: str) -> ProjectAssetEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM project_asset_catalog WHERE id=?", (entry_id,)
            ).fetchone()
        return ProjectAssetEntry.model_validate_json(row["payload"]) if row else None

    def list(self, project_id: str) -> list[ProjectAssetEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM project_asset_catalog WHERE project_id=? ORDER BY updated_at DESC,id",
                (project_id,),
            ).fetchall()
        return [ProjectAssetEntry.model_validate_json(row["payload"]) for row in rows]

    def save(self, entry: ProjectAssetEntry, *, expected_current_version: int | None = None) -> None:
        with self._connect() as connection:
            if expected_current_version is not None:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT payload FROM project_asset_catalog WHERE id=?", (entry.id,)).fetchone()
                if row is None or ProjectAssetEntry.model_validate_json(row["payload"]).current_version != expected_current_version:
                    raise ValueError("资产版本已被其他编辑更新，请重新读取。")
            connection.execute(
                """INSERT INTO project_asset_catalog(id,project_id,source_asset_id,payload,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at""",
                (entry.id, entry.project_id, entry.source_asset_id, entry.model_dump_json(), entry.updated_at),
            )


class ProjectAssetCatalogService:
    def __init__(self, repository: SqliteProjectAssetRepository):
        self.repository = repository
        self._lock = Lock()

    def list(self, project_id: str) -> list[ProjectAssetEntry]:
        return self.repository.list(project_id)

    def get(self, project_id: str, entry_id: str) -> ProjectAssetEntry:
        entry = self.repository.get(entry_id)
        if entry is None or entry.project_id != project_id:
            raise LookupError(entry_id)
        return entry

    def rename(self, project_id: str, entry_id: str,
               request: RenameProjectAssetRequest) -> ProjectAssetEntry:
        with self._lock:
            entry = self.get(project_id, entry_id)
            if entry.updated_at != request.expected_updated_at:
                raise ValueError("资产信息已更新，请重新读取后再命名。")
            title = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", request.title)).strip()
            if not title:
                raise ValueError("资产名称不能为空。")
            if any(item.id != entry.id and item.title.casefold() == title.casefold()
                   for item in self.repository.list(project_id)):
                raise ValueError("当前资产库已经使用这个名称。")
            renamed = entry.model_copy(update={"title": title, "updated_at": _now()})
            self.repository.save(renamed)
            return renamed

    def register_version(self, request: ProjectAssetRegistration) -> SaveProjectAssetResult:
        with self._lock:
            existing = self.repository.find_source(request.project_id, request.source_asset_id)
            if existing:
                if (existing.card_id != request.card_id
                        or existing.workspace_id != request.workspace_id
                        or existing.source_type != request.source_type):
                    raise ValueError("资产来源与已有资产库记录不一致。")
                if (request.version.asset_version_id is not None
                        and any(item.asset_version_id == request.version.asset_version_id
                                and item.source_version != request.version.source_version
                                for item in existing.versions)):
                    raise ValueError("资产版本 ID 已被另一版本使用。")
                same = next((item for item in existing.versions
                             if item.source_version == request.version.source_version), None)
                if same:
                    if (same.model_dump(exclude={"saved_at"}) !=
                            request.version.model_dump(exclude={"saved_at"})):
                        raise ValueError("该源版本已登记且内容不一致，不能覆盖资产库版本。")
                    return SaveProjectAssetResult(entry=existing, version_created=False)
                if (request.expected_version is not None
                        and existing.current_version != request.expected_version):
                    raise ValueError("资产版本已更新；新源保留，请重新读取后应用。")
                if request.version.source_version <= existing.current_version:
                    raise ValueError("新版本必须晚于当前版本。")
                updated = existing.model_copy(update={
                    "source_title": request.title,
                    "modeling_session_id": existing.modeling_session_id or request.modeling_session_id,
                    "current_version": request.version.source_version,
                    "versions": [*existing.versions, request.version],
                    "updated_at": _now(),
                })
                self.repository.save(updated, expected_current_version=existing.current_version)
                return SaveProjectAssetResult(entry=updated, version_created=True)
            used = {item.title for item in self.repository.list(request.project_id)}
            entry = ProjectAssetEntry(
                id="libasset_" + uuid4().hex,
                project_id=request.project_id,
                card_id=request.card_id,
                workspace_id=request.workspace_id,
                source_asset_id=request.source_asset_id,
                title=_unique_name(simple_asset_name(request.title), used),
                source_title=request.title,
                modeling_session_id=request.modeling_session_id,
                source_type=request.source_type,
                current_version=request.version.source_version,
                versions=[request.version],
            )
            self.repository.save(entry)
            return SaveProjectAssetResult(entry=entry, version_created=True)

    def update_recipe(self, project_id: str, entry_id: str,
                      request: UpdateProjectAssetRecipeRequest) -> SaveProjectAssetResult:
        with self._lock:
            entry = self.get(project_id, entry_id)
            latest = next(item for item in entry.versions
                          if item.source_version == entry.current_version)
            if latest.source_kind != "procedural":
                raise ValueError("只有程序化资产可以直接编辑配方。")
            if entry.current_version != request.expected_version:
                if (entry.current_version == request.expected_version + 1
                        and latest.operation == "recipe-edit"
                        and latest.recipe == request.recipe
                        and latest.runtime_artifacts == request.runtime_artifacts):
                    return SaveProjectAssetResult(entry=entry, version_created=False)
                raise ValueError("资产版本已更新，请重新读取后再编辑配方。")
            version = ProjectAssetVersion(
                source_version=entry.current_version + 1,
                asset_version_id="aver_" + uuid4().hex,
                source_kind="procedural",
                dimensions_m=request.recipe.dimensions_m,
                vertex_count=24,
                triangle_count=12,
                recipe=request.recipe,
                runtime_artifacts=request.runtime_artifacts,
                operation="recipe-edit",
                model_rotation_quaternion_xyzw=latest.model_rotation_quaternion_xyzw,
            )
            updated = entry.model_copy(update={
                "current_version": version.source_version,
                "versions": [*entry.versions, version],
                "updated_at": _now(),
            })
            self.repository.save(updated, expected_current_version=entry.current_version)
            return SaveProjectAssetResult(entry=updated, version_created=True)


def create_project_catalog_router(service: ProjectAssetCatalogService) -> APIRouter:
    router = APIRouter(prefix="/api/project-assets", tags=["project-asset-library"])

    @router.get("/recipe-definitions/door-v1", response_model=DoorRecipeDefinition,
                operation_id="getDoorRecipeDefinition")
    def get_door_recipe_definition():
        return door_recipe_definition()

    @router.get("", response_model=list[ProjectAssetEntry], operation_id="listProjectAssets")
    def list_assets(project_id: str = Query(..., min_length=1)):
        return service.list(project_id)

    @router.post("/{entry_id}/recipe-versions", response_model=SaveProjectAssetResult,
                 operation_id="updateProjectAssetRecipe")
    def update_recipe(entry_id: str, request: UpdateProjectAssetRecipeRequest,
                      project_id: str = Query(..., min_length=1)):
        try:
            return service.update_recipe(project_id, entry_id, request)
        except LookupError as error:
            raise HTTPException(404, "当前项目没有此资产库记录。") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/{entry_id}/versions/{version}/files/{kind}", operation_id="readProjectAssetFile")
    def read_file(entry_id: str, version: int, kind: Literal["preview", "blend", "fbx"],
                  project_id: str = Query(..., min_length=1)):
        try:
            entry = service.get(project_id, entry_id)
        except LookupError as error:
            raise HTTPException(404, "当前项目没有此资产库记录。") from error
        selected = next((item for item in entry.versions if item.source_version == version), None)
        if selected is None:
            raise HTTPException(404, f"资产 {entry.title} 的 v{version} 不存在。")
        if selected.source_kind == "file":
            return RedirectResponse(f"/api/card-assets/{quote(entry.source_asset_id, safe='')}/files/{kind}?version={version}")
        value = getattr(selected, f"{kind}_path")
        if not value:
            raise HTTPException(404, f"资产 {entry.title} v{version} 没有 {kind} 文件。")
        path = Path(value)
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise HTTPException(404, f"资产 {entry.title} v{version} 的 {kind} 文件不可读取。")
        return FileResponse(path, media_type="model/gltf-binary" if kind == "preview" else "application/octet-stream")

    @router.get("/{entry_id}", response_model=ProjectAssetEntry, operation_id="getProjectAsset")
    def get_asset(entry_id: str, project_id: str = Query(..., min_length=1)):
        try:
            return service.get(project_id, entry_id)
        except LookupError as error:
            raise HTTPException(404, "当前项目没有此资产库记录。") from error

    @router.put("/{entry_id}", response_model=ProjectAssetEntry, operation_id="renameProjectAsset")
    def rename_asset(entry_id: str, request: RenameProjectAssetRequest,
                     project_id: str = Query(..., min_length=1)):
        try:
            return service.rename(project_id, entry_id, request)
        except LookupError as error:
            raise HTTPException(404, "当前项目没有此资产库记录。") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    return router
