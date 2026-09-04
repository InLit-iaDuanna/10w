"""Base render, recipe, AOV, and job contracts."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactApprovalState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RenderJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AovPass(str, Enum):
    BEAUTY = "beauty"
    DEPTH = "depth"
    NORMAL = "normal"
    ALBEDO = "albedo"
    OBJECT_ID = "object_id"
    MATERIAL_ID = "material_id"


REQUIRED_DETERMINISTIC_PASSES = frozenset(
    {
        AovPass.BEAUTY,
        AovPass.DEPTH,
        AovPass.NORMAL,
        AovPass.ALBEDO,
        AovPass.OBJECT_ID,
    }
)


class RecipeKind(str, Enum):
    ASSET_TURNTABLE = "asset_turntable"
    MATERIAL_VARIANT = "material_variant"
    LIGHTING_VISIBILITY = "lighting_visibility"
    FIXED_CAMERA_REGRESSION = "fixed_camera_regression"
    MARKETING_STILL = "marketing_still"


class WritebackTarget(str, Enum):
    BLENDER = "blender"
    UNITY = "unity"


class WritebackProperty(str, Enum):
    LIGHT_INTENSITY = "light.intensity"
    LIGHT_COLOR = "light.color"
    LIGHT_TEMPERATURE = "light.temperature"
    OBJECT_VISIBILITY = "object.visibility"
    MATERIAL_SCALAR = "material.scalar"
    MATERIAL_COLOR = "material.color"
    PBR_TEXTURE = "material.pbr_texture"
    EXPOSURE = "render.exposure"
    POST_PARAMETER = "render.post_parameter"
    CAMERA_SETTING = "camera.setting"


def require_utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if offset is None or offset != timedelta(0):
        raise ValueError("timestamp must include a UTC offset")
    return value


class ArtifactRef(StrictModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_project_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_commit: Optional[str] = None
    related_sceneops_ids: List[str] = Field(default_factory=list)
    producing_module: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    approval_state: ArtifactApprovalState
    execution_mode: ExecutionMode
    created_at: datetime

    _created_at_utc = field_validator("created_at")(require_utc)

    @field_validator("related_sceneops_ids")
    @classmethod
    def related_ids_are_unique(cls, value: List[str]) -> List[str]:
        if any(not item for item in value) or len(value) != len(set(value)):
            raise ValueError("related_sceneops_ids must be non-empty unique IDs")
        return value

    @field_validator("execution_mode")
    @classmethod
    def artifact_requires_real_or_mock_execution(
        cls, value: ExecutionMode
    ) -> ExecutionMode:
        if value not in {ExecutionMode.LIVE, ExecutionMode.CACHED, ExecutionMode.MOCK}:
            raise ValueError("an artifact cannot be planned or blocked")
        return value


class SceneCameraRef(StrictModel):
    project_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_version: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    camera_version: str = Field(min_length=1)
    scene_object_ids: List[str] = Field(min_length=1)
    coordinate_space: str = Field(min_length=1)
    axis_convention: str = Field(min_length=1)
    distance_unit: Literal["meter"] = "meter"

    @field_validator("scene_object_ids")
    @classmethod
    def unique_object_ids(cls, value: List[str]) -> List[str]:
        if any(not item for item in value):
            raise ValueError("scene_object_ids cannot contain empty values")
        if len(value) != len(set(value)):
            raise ValueError("scene_object_ids must be unique")
        return value


class ProtectedRegion(StrictModel):
    region_id: str = Field(min_length=1)
    object_ids: List[str] = Field(min_length=1)
    mask_artifact_id: str = Field(min_length=1)
    max_changed_ratio: float = Field(ge=0.0, le=1.0)

    @field_validator("object_ids")
    @classmethod
    def region_object_ids_are_unique(cls, value: List[str]) -> List[str]:
        if any(not item for item in value) or len(value) != len(set(value)):
            raise ValueError("protected region object IDs must be unique")
        return value


class RenderBrief(StrictModel):
    brief_id: str = Field(min_length=1)
    scene: SceneCameraRef
    intent: str = Field(min_length=1)
    target_object_ids: List[str] = Field(min_length=1)
    protected_regions: List[ProtectedRegion] = Field(default_factory=list)
    requested_by: str = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(require_utc)

    @model_validator(mode="after")
    def targets_belong_to_scene(self) -> "RenderBrief":
        scene_ids = set(self.scene.scene_object_ids)
        if len(self.target_object_ids) != len(set(self.target_object_ids)):
            raise ValueError("target_object_ids must be unique")
        if not set(self.target_object_ids).issubset(scene_ids):
            raise ValueError("target_object_ids must belong to the versioned scene")
        for region in self.protected_regions:
            if not set(region.object_ids).issubset(scene_ids):
                raise ValueError("protected region object_ids must belong to the scene")
        return self


def validate_recipe_pass_contract(
    kind: RecipeKind,
    required_passes: List[AovPass],
    optional_passes: List[AovPass],
) -> None:
    required = set(required_passes)
    if not REQUIRED_DETERMINISTIC_PASSES.issubset(required):
        missing = sorted(item.value for item in REQUIRED_DETERMINISTIC_PASSES - required)
        raise ValueError("recipe is missing deterministic passes: " + ", ".join(missing))
    if len(required_passes) != len(required):
        raise ValueError("required_passes must be unique")
    if len(optional_passes) != len(set(optional_passes)):
        raise ValueError("optional_passes must be unique")
    if required.intersection(optional_passes):
        raise ValueError("a pass cannot be both required and optional")
    if kind == RecipeKind.MATERIAL_VARIANT and AovPass.MATERIAL_ID not in required:
        raise ValueError("material variants require material_id")


class RenderRecipe(StrictModel):
    recipe_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    kind: RecipeKind
    required_passes: List[AovPass] = Field(min_length=1)
    optional_passes: List[AovPass] = Field(default_factory=list)
    workflow_reference: Optional[str] = None
    workflow_checksum_sha256: Optional[str] = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def deterministic_pass_contract(self) -> "RenderRecipe":
        validate_recipe_pass_contract(
            self.kind, self.required_passes, self.optional_passes
        )
        if bool(self.workflow_reference) != bool(self.workflow_checksum_sha256):
            raise ValueError("workflow reference and checksum must be supplied together")
        return self


class AovArtifact(StrictModel):
    pass_type: AovPass
    scene: SceneCameraRef
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    artifact: ArtifactRef


class RenderCaptureCommand(StrictModel):
    command_id: Literal[
        "blender.render.capture_aov", "unity.render.capture_aov"
    ]
    render_job_id: str = Field(min_length=1)
    scene: SceneCameraRef
    passes: List[AovPass] = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    renderer_version: str = Field(min_length=1)
    samples: int = Field(gt=0)
    execution_mode: Literal["live", "mock"]

    @field_validator("passes")
    @classmethod
    def capture_passes_are_unique(cls, value: List[AovPass]) -> List[AovPass]:
        if len(value) != len(set(value)):
            raise ValueError("capture passes must be unique")
        return value


class PortableRecipeDefinition(StrictModel):
    recipe_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    kind: RecipeKind
    required_passes: List[AovPass] = Field(min_length=1)
    optional_passes: List[AovPass] = Field(default_factory=list)
    portable_parameters: List[str] = Field(default_factory=list)
    execution_requirement: Literal["live_or_cached_real"]

    @model_validator(mode="after")
    def deterministic_pass_contract(self) -> "PortableRecipeDefinition":
        validate_recipe_pass_contract(
            self.kind, self.required_passes, self.optional_passes
        )
        if len(self.portable_parameters) != len(set(self.portable_parameters)):
            raise ValueError("portable_parameters must be unique")
        return self


class PortableRecipeCatalog(StrictModel):
    schema_version: Literal[1]
    recipes: List[PortableRecipeDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_recipe_ids(self) -> "PortableRecipeCatalog":
        ids = [item.recipe_id for item in self.recipes]
        if len(ids) != len(set(ids)):
            raise ValueError("portable recipe IDs must be unique")
        return self


class AovDependencySnapshot(StrictModel):
    recipe_id: str = Field(min_length=1)
    recipe_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    geometry_version: str = Field(min_length=1)
    camera_version: str = Field(min_length=1)
    material_version: str = Field(min_length=1)
    lighting_version: str = Field(min_length=1)
    visibility_version: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    samples: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CachePlan(StrictModel):
    reused_passes: List[AovPass] = Field(default_factory=list)
    capture_passes: List[AovPass] = Field(default_factory=list)
    reasons: Dict[AovPass, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def disjoint(self) -> "CachePlan":
        if set(self.reused_passes).intersection(self.capture_passes):
            raise ValueError("a pass cannot be both reused and captured")
        return self


class JobFailure(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    suggested_actions: List[str] = Field(default_factory=list)


class RenderJob(StrictModel):
    job_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    recipe_version: str = Field(min_length=1)
    scene: SceneCameraRef
    dependency_snapshot: AovDependencySnapshot
    cache_plan: CachePlan
    state: RenderJobState
    execution_mode: ExecutionMode
    attempt: int = Field(default=1, ge=1)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    failure: Optional[JobFailure] = None
    created_at: datetime
    updated_at: datetime

    _created_at_utc = field_validator("created_at")(require_utc)
    _updated_at_utc = field_validator("updated_at")(require_utc)

    @model_validator(mode="after")
    def state_failure_consistency(self) -> "RenderJob":
        if self.state == RenderJobState.FAILED and self.failure is None:
            raise ValueError("failed jobs require structured failure information")
        if self.state != RenderJobState.FAILED and self.failure is not None:
            raise ValueError("only failed jobs may contain failure information")
        if self.execution_mode == ExecutionMode.BLOCKED and self.state != RenderJobState.FAILED:
            raise ValueError("blocked execution mode is valid only for failed jobs")
        if self.state == RenderJobState.SUCCEEDED and self.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.CACHED,
            ExecutionMode.MOCK,
        }:
            raise ValueError("a succeeded job cannot be planned or blocked")
        return self
