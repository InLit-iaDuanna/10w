"""Typed public contracts for Unity adapter commands and results."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Literal, Mapping, Optional, Set, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ApprovalState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CommandStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"
    PLANNED = "planned"
    BLOCKED = "blocked"


class CommandName(str, Enum):
    PROTOTYPE_COMPOSE = "unity.prototype.compose"
    PROTOTYPE_INSPECT = "unity.prototype.inspect"
    PROTOTYPE_PLAY = "unity.prototype.play"
    PROTOTYPE_CAPTURE = "unity.prototype.capture"
    HEALTH = "unity.health"
    SCAN_PROJECT = "unity.project.scan"
    IMPORT_ASSET = "unity.asset.import"
    MAP_IDENTITY = "unity.identity.map"
    UPSERT_PREFAB = "unity.prefab.upsert"
    INSPECT_GAME_OBJECT = "unity.game_object.inspect"
    SET_COMPONENT_PROPERTY = "unity.component_property.set"
    UPSERT_COLLIDER = "unity.collider.upsert"
    RUN_NAVMESH = "unity.navmesh.run"
    ENTER_PLAY = "unity.play.enter"
    EXIT_PLAY = "unity.play.exit"
    CAPTURE = "unity.capture"
    READ_CONSOLE = "unity.console.read"
    RUN_TESTS = "unity.tests.run"
    SNAPSHOT_PROFILER = "unity.profiler.snapshot"
    RUN_BUILD = "unity.build.run"


class ChangeSet(StrictModel):
    change_set_id: str = Field(pattern=r"^chg_[A-Za-z0-9_.-]+$")
    base_version: str = Field(min_length=1)
    target_integration: Literal["unity"] = "unity"
    command: CommandName
    target_object_ids: List[str] = Field(min_length=1)
    previous_values: Dict[str, Any]
    proposed_values: Dict[str, Any]
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: str = Field(min_length=1)
    risk: Literal["low", "medium", "high", "critical"]
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_state: ApprovalState

    @field_validator("target_object_ids")
    @classmethod
    def validate_target_ids(cls, values: List[str]) -> List[str]:
        if len(values) != len(set(values)):
            raise ValueError("ChangeSet target IDs must be unique")
        if any(
            not value
            or any(character.isspace() for character in value)
            or any(character in value for character in ("/", "\\", "|"))
            for value in values
        ):
            raise ValueError("ChangeSet targets must be stable IDs, not names or paths")
        return values


class EmptyPayload(StrictModel):
    pass


class ScanProjectPayload(StrictModel):
    include_packages: bool = False


class ImportAssetPayload(StrictModel):
    source_asset_id: str = Field(pattern=r"^ast_[A-Za-z0-9_.-]+$")
    source_asset_version_id: str = Field(pattern=r"^astv_[A-Za-z0-9_.-]+$")
    source_path: str = Field(min_length=1)
    destination_asset_path: str = Field(pattern=r"^Assets/")
    manifest_path: str = Field(pattern=r"^Assets/")
    import_scale: float = Field(default=1.0, gt=0, le=1000)
    material_mode: Literal["import", "external", "none"] = "import"
    generate_colliders: bool = False
    lod_screen_percentages: List[float] = Field(default_factory=list, max_length=8)
    destination_scene_path: str = ""
    sceneops_id: str = ""
    scene_instance_id: str = ""

    @model_validator(mode="after")
    def validate_import_files(self) -> "ImportAssetPayload":
        if self.destination_scene_path:
            if self.destination_scene_path != "Assets/SceneOpsAgent.unity":
                raise ValueError("Agent placement uses the dedicated SceneOpsAgent scene only")
            if not self.sceneops_id or not self.scene_instance_id:
                raise ValueError("Agent placement requires source and scene-instance identities")
        allowed = {".3ds", ".dae", ".dxf", ".fbx", ".obj"}
        source_extension = Path(self.source_path).suffix.lower()
        destination_extension = Path(self.destination_asset_path).suffix.lower()
        if source_extension not in allowed or destination_extension not in allowed:
            raise ValueError(
                "Unity model import accepts only .3ds, .dae, .dxf, .fbx, and .obj"
            )
        if source_extension != destination_extension:
            raise ValueError("source and destination model extensions must match")
        if not self.manifest_path.lower().endswith(".sceneops-unity.json"):
            raise ValueError("manifest_path must end with .sceneops-unity.json")
        return self

    @field_validator("lod_screen_percentages")
    @classmethod
    def validate_lods(cls, values: List[float]) -> List[float]:
        if any(value <= 0 or value > 1 for value in values):
            raise ValueError("LOD screen percentages must be within (0, 1]")
        if values != sorted(values, reverse=True):
            raise ValueError("LOD screen percentages must be descending")
        return values


class MapIdentityPayload(StrictModel):
    source_asset_id: str = Field(pattern=r"^ast_")
    source_asset_version_id: str = Field(pattern=r"^astv_")
    source_object_id: str = Field(min_length=1)
    sceneops_id: str = Field(pattern=r"^sobj_")
    unity_asset_guid: str = Field(min_length=1)
    prefab_id: Optional[str] = Field(default=None, pattern=r"^prefab_")
    scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")
    unity_global_object_id: Optional[str] = Field(default=None, min_length=1, max_length=512)
    relationship: Literal["import", "rename", "copy", "prefab_instance"]
    display_name: str = ""
    copied_from_scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")

    @model_validator(mode="after")
    def validate_relationship(self) -> "MapIdentityPayload":
        if self.relationship == "import" and self.scene_instance_id:
            raise ValueError("import maps an asset or Prefab and cannot assign a scene_instance_id")
        if self.relationship in {"copy", "prefab_instance"} and not self.scene_instance_id:
            raise ValueError("copy and prefab_instance require scene_instance_id")
        if self.relationship in {"copy", "prefab_instance"} and not self.unity_global_object_id:
            raise ValueError("copy and prefab_instance require unity_global_object_id")
        if self.relationship == "prefab_instance" and not self.prefab_id:
            raise ValueError("prefab_instance requires prefab_id")
        if self.relationship == "copy" and not self.copied_from_scene_instance_id:
            raise ValueError("copy requires copied_from_scene_instance_id")
        if (
            self.relationship == "copy"
            and self.scene_instance_id == self.copied_from_scene_instance_id
        ):
            raise ValueError("a copy must receive a new scene_instance_id")
        return self


class UpsertPrefabPayload(StrictModel):
    source_asset_guid: str = Field(min_length=1)
    prefab_asset_path: str = Field(pattern=r"^Assets/.*\.prefab$")
    sceneops_id: str = Field(pattern=r"^sobj_")
    prefab_id: str = Field(pattern=r"^prefab_")
    source_asset_id: str = Field(pattern=r"^ast_")
    source_asset_version_id: str = Field(pattern=r"^astv_")
    component_types: List[str] = Field(default_factory=list)
    lod_screen_percentages: List[float] = Field(default_factory=list, max_length=8)

    @field_validator("lod_screen_percentages")
    @classmethod
    def validate_lods(cls, values: List[float]) -> List[float]:
        return ImportAssetPayload.validate_lods(values)


class InspectGameObjectPayload(StrictModel):
    sceneops_id: str = Field(pattern=r"^sobj_")
    scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")


class SetComponentPropertyPayload(StrictModel):
    sceneops_id: str = Field(pattern=r"^sobj_")
    scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")
    component_type: str = Field(min_length=1)
    property_path: str = Field(min_length=1)
    value: Any


class UpsertColliderPayload(StrictModel):
    sceneops_id: str = Field(pattern=r"^sobj_")
    scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")
    collider_type: Literal["BoxCollider", "SphereCollider", "CapsuleCollider", "MeshCollider"]
    is_trigger: bool = False
    center_meters: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    size_meters: List[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0], min_length=3, max_length=3)

    @field_validator("size_meters")
    @classmethod
    def positive_size(cls, values: List[float]) -> List[float]:
        if any(value <= 0 for value in values):
            raise ValueError("collider size must be positive")
        return values


class NavMeshPayload(StrictModel):
    scene_id: str = Field(pattern=r"^scene_[A-Za-z0-9_.-]+$")
    operation: Literal["validate", "bake", "clear"]
    scene_asset_path: str = Field(pattern=r"^Assets/.*\.unity$")
    agent_type_id: int = 0


class PlayPayload(StrictModel):
    scene_asset_path: Optional[str] = Field(default=None, pattern=r"^Assets/.*\.unity$")


class CapturePayload(StrictModel):
    output_path: str = Field(pattern=r"^(Artifacts|Builds)/")
    width: int = Field(default=1280, ge=64, le=8192)
    height: int = Field(default=720, ge=64, le=8192)


class ReadConsolePayload(StrictModel):
    minimum_level: Literal["info", "warning", "error"] = "info"
    max_entries: int = Field(default=500, ge=1, le=5000)


class RunTestsPayload(StrictModel):
    test_mode: Literal["EditMode", "PlayMode"]
    test_filter: Optional[str] = Field(default=None, max_length=256)
    results_path: str = Field(default="Artifacts/TestResults.xml", pattern=r"^Artifacts/")


class ProfilerPayload(StrictModel):
    output_path: str = Field(default="Artifacts/ProfilerSnapshot.json", pattern=r"^Artifacts/")
    sample_frames: int = Field(default=1, ge=1, le=300)


class SourceAssetReference(StrictModel):
    source_asset_id: str = Field(pattern=r"^ast_[A-Za-z0-9_.-]+$")
    source_asset_version_id: str = Field(pattern=r"^astv_[A-Za-z0-9_.-]+$")


class BuildPayload(StrictModel):
    build_id: str = Field(pattern=r"^bld_")
    profile: str = Field(min_length=1, max_length=120)
    target: Literal["StandaloneOSX", "StandaloneWindows64", "StandaloneLinux64", "WebGL"]
    output_path: str = Field(pattern=r"^Builds/")
    scenes: List[str] = Field(min_length=1)
    development: bool = False
    source_commit: str = Field(min_length=1)
    source_assets: List[SourceAssetReference] = Field(default_factory=list)
    required_test_runs: List[str] = Field(default_factory=list)

    @field_validator("scenes")
    @classmethod
    def validate_scenes(cls, values: List[str]) -> List[str]:
        if any(not path.startswith("Assets/") or not path.endswith(".unity") for path in values):
            raise ValueError("build scenes must be Unity project-relative .unity paths")
        return values


from .prototype_contracts import PrototypeSpec, PrototypePlayPayload

PAYLOAD_MODELS: Mapping[CommandName, Type[StrictModel]] = {
    CommandName.PROTOTYPE_COMPOSE: PrototypeSpec,
    CommandName.PROTOTYPE_INSPECT: EmptyPayload,
    CommandName.PROTOTYPE_PLAY: PrototypePlayPayload,
    CommandName.PROTOTYPE_CAPTURE: PrototypePlayPayload,
    CommandName.HEALTH: EmptyPayload,
    CommandName.SCAN_PROJECT: ScanProjectPayload,
    CommandName.IMPORT_ASSET: ImportAssetPayload,
    CommandName.MAP_IDENTITY: MapIdentityPayload,
    CommandName.UPSERT_PREFAB: UpsertPrefabPayload,
    CommandName.INSPECT_GAME_OBJECT: InspectGameObjectPayload,
    CommandName.SET_COMPONENT_PROPERTY: SetComponentPropertyPayload,
    CommandName.UPSERT_COLLIDER: UpsertColliderPayload,
    CommandName.RUN_NAVMESH: NavMeshPayload,
    CommandName.ENTER_PLAY: PlayPayload,
    CommandName.EXIT_PLAY: EmptyPayload,
    CommandName.CAPTURE: CapturePayload,
    CommandName.READ_CONSOLE: ReadConsolePayload,
    CommandName.RUN_TESTS: RunTestsPayload,
    CommandName.SNAPSHOT_PROFILER: ProfilerPayload,
    CommandName.RUN_BUILD: BuildPayload,
}


class CommandRequest(StrictModel):
    request_id: str = Field(pattern=r"^req_[A-Za-z0-9_.-]+$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    command: CommandName
    project_id: str = Field(pattern=r"^prj_")
    project_root: str = Field(min_length=1)
    base_version: str = Field(min_length=1)
    mode: ExecutionMode
    payload: Dict[str, Any] = Field(default_factory=dict)
    change_set: Optional[ChangeSet] = None
    timeout_seconds: float = Field(default=120.0, gt=0, le=7200)
    max_attempts: int = Field(default=1, ge=1, le=3)
    cache_key: Optional[str] = Field(default=None, max_length=200)

    def typed_payload(self) -> StrictModel:
        return PAYLOAD_MODELS[self.command].model_validate(self.payload)


class ExecutionContext(StrictModel):
    configured_project_roots: List[str] = Field(min_length=1)
    permissions: Set[str]
    current_base_version: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    approved_change_sets: Dict[str, ChangeSet] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_approval_registry(self) -> "ExecutionContext":
        for change_set_id, change_set in self.approved_change_sets.items():
            if change_set_id != change_set.change_set_id:
                raise ValueError("approved ChangeSet registry key must match change_set_id")
            if change_set.approval_state is not ApprovalState.APPROVED:
                raise ValueError("approved ChangeSet registry may contain only approved records")
        return self


class StructuredLog(StrictModel):
    level: Literal["debug", "info", "warning", "error"]
    code: str
    message: str
    occurred_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def now(
        cls,
        level: Literal["debug", "info", "warning", "error"],
        code: str,
        message: str,
        **details: Any,
    ) -> "StructuredLog":
        return cls(
            level=level,
            code=code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
            details=details,
        )


class ResultError(StrictModel):
    code: str
    message: str
    retryable: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class CommandResult(StrictModel):
    request_id: str
    command: CommandName
    status: CommandStatus
    mode: ExecutionMode
    attempts: int = Field(default=1, ge=0)
    data: Dict[str, Any] = Field(default_factory=dict)
    logs: List[StructuredLog] = Field(default_factory=list)
    error: Optional[ResultError] = None
    cached_from_request_id: Optional[str] = None


class ChangePreview(StrictModel):
    request_id: str
    command: CommandName
    mode: Literal[ExecutionMode.PLANNED] = ExecutionMode.PLANNED
    mutating: bool
    approval_required: bool
    resolved_project_root: str
    target_paths: List[str]
    proposed_values: Dict[str, Any]
    validation_steps: List[str]


class CapabilityReport(StrictModel):
    integration_id: Literal["unity"] = "unity"
    adapter_version: str
    minimum_unity_version: str
    maximum_unity_major: int
    pinned_unity_version: str
    command_allowlist: List[CommandName]
    arbitrary_csharp_execution: Literal[False] = False
    supports_dry_run: Literal[True] = True
    supports_cancellation: Literal[True] = True
    supports_retry: Literal[True] = True
    execution_modes: FrozenSet[ExecutionMode]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
