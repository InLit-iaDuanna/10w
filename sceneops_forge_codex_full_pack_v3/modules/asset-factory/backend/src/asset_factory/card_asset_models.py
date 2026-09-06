"""Typed contracts for card-bound import and model creation workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PrimitivePart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cube", "sphere", "cylinder", "cone"]
    name: str = Field(min_length=1, max_length=80)
    dimensions_m: tuple[float, float, float]
    location_m: tuple[float, float, float]
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("dimensions_m")
    @classmethod
    def validate_dimensions(cls, value: tuple[float, float, float]):
        if any(not 0.001 <= item <= 1000 for item in value):
            raise ValueError("部件尺寸必须在 0.001–1000 米之间。")
        return value

    @field_validator("location_m", "rotation_deg")
    @classmethod
    def validate_finite(cls, value: tuple[float, float, float]):
        if any(not -10000 <= item <= 10000 for item in value):
            raise ValueError("部件变换超出允许范围。")
        return value


class ModelPlanContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    target_extent_m: float = Field(gt=0, le=1000)
    parts: list[PrimitivePart] = Field(min_length=1, max_length=64)


class CardAssetProposal(ModelPlanContent):
    id: str
    asset_id: str
    project_id: str
    card_id: str
    session_id: str
    trigger_message_id: str | None = None
    modeling_block: str | None = Field(default=None, max_length=80)
    reference_id: str | None = None
    provider: str
    model: str
    status: Literal["planned", "generated", "failed"] = "planned"
    created_at: str = Field(default_factory=utc_now)
    error: str | None = None


class CardAssetVersion(BaseModel):
    number: int = Field(ge=1)
    dimensions_m: tuple[float, float, float]
    vertex_count: int = Field(ge=0)
    triangle_count: int = Field(ge=0)
    object_ids: list[str]
    blender_version: str
    blend_path: str
    preview_path: str
    fbx_path: str
    manifest_path: str
    created_at: str = Field(default_factory=utc_now)
    operation: Literal["import", "generate", "normalize"]


class CardAssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    card_id: str
    title: str
    source_type: Literal["import", "generated"]
    status: Literal["processing", "ready", "failed"]
    source_filename: str | None = None
    source_path: str | None = None
    proposal_id: str | None = None
    session_id: str | None = None
    current_version: int = 0
    raw_dimensions_m: tuple[float, float, float] | None = None
    versions: list[CardAssetVersion] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    error: str | None = None
    log_path: str | None = None


class CardAssetReference(BaseModel):
    id: str
    project_id: str
    card_id: str
    filename: str
    path: str
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    created_at: str = Field(default_factory=utc_now)


class CardAssetChange(BaseModel):
    id: str
    project_id: str
    card_id: str
    asset_id: str | None = None
    operation: Literal["import", "generate", "normalize", "reference"]
    status: Literal["approved", "executed", "failed"] = "approved"
    rationale: str
    writes: list[str]
    created_at: str = Field(default_factory=utc_now)
    completed_at: str | None = None
    error: str | None = None


class CardAssetList(BaseModel):
    project_id: str
    card_id: str
    branch: str
    assets: list[CardAssetRecord]
    proposals: list[CardAssetProposal]
    references: list[CardAssetReference]


class ModelPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=160)
    transcript: list[dict[str, str]] = Field(min_length=1, max_length=120)
    reference_id: str | None = None


class LiveModelUpdateRequest(ModelPlanRequest):
    trigger_message_id: str = Field(min_length=1, max_length=160)
    modeling_block: str = Field(min_length=1, max_length=80)
    retry_failed: bool = False


class LiveModelUpdateResult(BaseModel):
    proposal: CardAssetProposal
    asset: CardAssetRecord
    version_created: bool
    reused: bool


class NormalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_extent_m: float = Field(gt=0, le=1000)


class SaveToLibraryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)


class CardAssetError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
