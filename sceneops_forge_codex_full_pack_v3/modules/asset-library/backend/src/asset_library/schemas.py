from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MetricValue = Union[str, int, float, bool, None, List[str]]


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class PublicationStatus(str, Enum):
    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"


class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_RUN = "not_run"


class UnityStatus(str, Enum):
    NOT_IMPORTED = "not_imported"
    PENDING = "pending"
    IMPORTED = "imported"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class Vector3Meters(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    z: float = Field(ge=0)
    coordinate_space: str = "asset_local"
    axis_convention: str = "right-handed_z-up"
    unit: str = "meter"


class AssetSpec(BaseModel):
    schema_version: Literal[1] = 1
    asset_spec_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = ""
    intended_use: str = Field(min_length=1)
    target_dimensions_m: Vector3Meters
    triangle_budget: int = Field(gt=0)
    required_formats: List[str] = Field(default_factory=lambda: ["glb", "fbx"])
    required_gate_ids: List[str] = Field(
        default_factory=lambda: ["geometry", "uv_material", "identity"]
    )
    requires_uv: bool = True
    requires_rig: bool = False
    requires_lods: bool = False
    requires_collider: bool = True
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("created_at must be UTC")
        return value

    @field_validator("required_formats")
    @classmethod
    def formats_are_engine_ready(cls, value: List[str]) -> List[str]:
        normalized = [item.lower() for item in value]
        unsupported = sorted(set(normalized) - {"glb", "fbx"})
        if unsupported:
            raise ValueError("unsupported required formats: %s" % ", ".join(unsupported))
        if not normalized or len(normalized) != len(set(normalized)):
            raise ValueError("required formats must be non-empty and unique")
        return normalized

    @field_validator("required_gate_ids")
    @classmethod
    def required_gates_are_unique(cls, value: List[str]) -> List[str]:
        if not value or len(value) != len(set(value)) or any(not item for item in value):
            raise ValueError("required gate IDs must be non-empty and unique")
        return value


class SourceAsset(BaseModel):
    schema_version: Literal[1] = 1
    source_asset_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    project_relative_path: str = Field(min_length=1)
    format: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_commit: Optional[str] = None
    source_kind: str = Field(pattern="^(imported|generated|scanned)$")
    license_name: str = Field(min_length=1)
    license_uri: Optional[str] = None
    origin_uri: Optional[str] = None
    imported_at: datetime

    @field_validator("project_relative_path")
    @classmethod
    def source_path_is_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("source path must be project-relative")
        return normalized


class AssetObjectIdentity(BaseModel):
    sceneops_id: str = Field(min_length=1)
    source_asset_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source_object_locator: str = Field(min_length=1)
    parent_sceneops_id: Optional[str] = None


class GeometryMetrics(BaseModel):
    dimensions_m: Vector3Meters
    triangle_count: int = Field(ge=0)
    vertex_count: int = Field(ge=0)
    material_count: int = Field(ge=0)
    texture_count: int = Field(ge=0)
    has_uv: bool
    is_rigged: bool
    animation_names: List[str] = Field(default_factory=list)
    lod_count: int = Field(ge=0)
    collider_kind: Optional[str] = None


class QualityGate(BaseModel):
    gate_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: GateStatus
    blocking: bool
    message: str
    measurements: Dict[str, MetricValue] = Field(default_factory=dict)


class ArtifactOutput(BaseModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    format: str = Field(min_length=1)
    project_relative_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")

    @field_validator("project_relative_path")
    @classmethod
    def output_path_is_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("output path must be project-relative")
        return normalized


class AIProvenance(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    workflow_hash: str = Field(min_length=1)
    prompt: str
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    parameters: Dict[str, MetricValue] = Field(default_factory=dict)


class ArtifactProvenance(BaseModel):
    artifact_id: str = Field(min_length=1)
    source_project: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_commit: Optional[str] = None
    related_sceneops_ids: List[str] = Field(default_factory=list)
    producing_module: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    recipe_version: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    execution_mode: ExecutionMode
    timestamp: datetime
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    approval_state: str = Field(pattern="^(not_required|pending|approved|rejected)$")
    ai: Optional[AIProvenance] = None


class AssetVersion(BaseModel):
    schema_version: Literal[1] = 1
    asset_version_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    source_asset_id: str = Field(min_length=1)
    version: int = Field(gt=0)
    status: PublicationStatus
    execution_mode: ExecutionMode
    metrics: GeometryMetrics
    object_identities: List[AssetObjectIdentity]
    outputs: List[ArtifactOutput] = Field(min_length=1)
    quality_gates: List[QualityGate] = Field(min_length=1)
    provenance: List[ArtifactProvenance] = Field(min_length=1)
    approval_id: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None

    @model_validator(mode="after")
    def version_identity_and_provenance_match(self) -> "AssetVersion":
        output_id_values = [item.artifact_id for item in self.outputs]
        provenance_id_values = [item.artifact_id for item in self.provenance]
        if len(output_id_values) != len(set(output_id_values)):
            raise ValueError("artifact output IDs must be unique")
        if len(provenance_id_values) != len(set(provenance_id_values)):
            raise ValueError("artifact provenance IDs must be unique")
        gate_ids = [item.gate_id for item in self.quality_gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("quality gate IDs must be unique")
        output_ids = set(output_id_values)
        provenance_ids = set(provenance_id_values)
        if output_ids != provenance_ids:
            raise ValueError("each output requires matching provenance")
        object_ids = [item.sceneops_id for item in self.object_identities]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("sceneops_id values must be unique within an asset version")
        artifact_by_id = {item.artifact_id: item for item in self.outputs}
        if any(
            item.sha256 != artifact_by_id[item.artifact_id].sha256
            for item in self.provenance
        ):
            raise ValueError("artifact provenance checksums must match outputs")
        if any(
            not set(item.related_sceneops_ids).issubset(object_ids)
            for item in self.provenance
        ):
            raise ValueError("artifact provenance references an unknown sceneops_id")
        return self


class UsageReference(BaseModel):
    usage_id: str = Field(min_length=1)
    asset_version_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_instance_id: str = Field(min_length=1)
    unity_prefab_id: Optional[str] = None
    unity_status: UnityStatus
    build_ids: List[str] = Field(default_factory=list)
    first_seen_at: datetime

    @model_validator(mode="after")
    def scene_instance_is_not_asset_version(self) -> "UsageReference":
        if self.scene_instance_id == self.asset_version_id:
            raise ValueError("scene-instance identity must differ from asset-version identity")
        return self


class AssetRecord(BaseModel):
    schema_version: Literal[1] = 1
    spec: AssetSpec
    source: SourceAsset
    source_objects: List[AssetObjectIdentity]
    versions: List[AssetVersion] = Field(default_factory=list)
    usage_references: List[UsageReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def aggregate_relationships_are_consistent(self) -> "AssetRecord":
        if self.spec.asset_id != self.source.asset_id or self.spec.project_id != self.source.project_id:
            raise ValueError("spec and source must reference the same asset and project")
        if self.spec.asset_id == self.source.source_asset_id:
            raise ValueError("asset and source-asset identities must be distinct")
        source_object_ids = [item.sceneops_id for item in self.source_objects]
        if len(source_object_ids) != len(set(source_object_ids)):
            raise ValueError("source sceneops_id values must be unique")
        if any(
            item.source_asset_id != self.source.source_asset_id
            for item in self.source_objects
        ):
            raise ValueError("source objects must belong to the record source asset")
        version_ids = [item.asset_version_id for item in self.versions]
        version_numbers = [item.version for item in self.versions]
        if len(version_ids) != len(set(version_ids)) or len(version_numbers) != len(
            set(version_numbers)
        ):
            raise ValueError("asset version IDs and version numbers must be unique")
        if any(
            version.asset_id != self.spec.asset_id
            or version.source_asset_id != self.source.source_asset_id
            for version in self.versions
        ):
            raise ValueError("versions must belong to the record asset and source")
        if any(
            identity.source_asset_id != self.source.source_asset_id
            for version in self.versions
            for identity in version.object_identities
        ):
            raise ValueError("version objects must belong to the record source asset")
        stable_ids = set(source_object_ids)
        reserved_ids = {self.spec.asset_id, self.source.source_asset_id}
        reserved_ids.update(version_ids)
        scene_instance_ids = [item.scene_instance_id for item in self.usage_references]
        reserved_values = [self.spec.asset_id, self.source.source_asset_id]
        reserved_values.extend(version_ids)
        reserved_values.extend(scene_instance_ids)
        if len(reserved_values) != len(set(reserved_values)):
            raise ValueError("asset, source, version, and scene-instance IDs must be distinct")
        reserved_ids.update(scene_instance_ids)
        version_object_ids = {
            identity.sceneops_id
            for version in self.versions
            for identity in version.object_identities
        }
        if (stable_ids | version_object_ids) & reserved_ids:
            raise ValueError("asset, object, version, and scene-instance identities must be distinct")
        if any(
            item.asset_version_id not in set(version_ids)
            for item in self.usage_references
        ):
            raise ValueError("usage must reference a version in the same record")
        usage_ids = [item.usage_id for item in self.usage_references]
        if len(usage_ids) != len(set(usage_ids)) or len(scene_instance_ids) != len(
            set(scene_instance_ids)
        ):
            raise ValueError("usage and scene-instance IDs must be unique")
        if any(
            usage.project_id != self.spec.project_id for usage in self.usage_references
        ):
            raise ValueError("usage references must belong to the record project")
        return self

    @property
    def latest_version(self) -> Optional[AssetVersion]:
        return max(self.versions, key=lambda item: item.version) if self.versions else None

    @property
    def included_build_ids(self) -> List[str]:
        return sorted({build_id for usage in self.usage_references for build_id in usage.build_ids})


class AssetSearchFilter(BaseModel):
    project_id: Optional[str] = None
    query: str = ""
    formats: List[str] = Field(default_factory=list)
    gate_status: Optional[GateStatus] = None
    unity_status: Optional[UnityStatus] = None
    has_uv: Optional[bool] = None
    rigged: Optional[bool] = None
    has_animations: Optional[bool] = None
    has_lod: Optional[bool] = None
    has_collider: Optional[bool] = None
    has_ai_provenance: Optional[bool] = None
    license_name: Optional[str] = None
    min_triangles: Optional[int] = Field(None, ge=0)
    max_triangles: Optional[int] = Field(None, ge=0)
    execution_modes: List[ExecutionMode] = Field(default_factory=list)


class PublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    asset_version_id: str = Field(min_length=1)
    change_set_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)


class PublishedEvent(BaseModel):
    event_id: str
    event_type: Literal["asset.version.published"] = "asset.version.published"
    event_version: Literal[1] = 1
    occurred_at: datetime
    project_id: str
    correlation_id: str
    causation_id: str
    actor: Dict[str, str]
    mode: ExecutionMode
    payload: Dict[str, Union[str, int, List[str]]]
