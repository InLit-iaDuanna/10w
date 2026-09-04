"""Animation, retarget, state-machine, and preview contracts."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from .common import (
    ApprovalRecord,
    CoordinateSystem,
    ExecutionMode,
    Provenance,
    StrictModel,
    Vector3,
    normalize_utc,
)


class AnimationEventMarker(StrictModel):
    marker_id: str = Field(min_length=3)
    name: str = Field(min_length=1)
    time_seconds: float
    payload: Dict[str, object] = Field(default_factory=dict)


class LoopPose(StrictModel):
    root_translation_meters: Vector3
    root_rotation_degrees: Vector3


class RootMotionSample(StrictModel):
    time_seconds: float
    translation_meters: Vector3


class FootPlantSample(StrictModel):
    time_seconds: float
    foot: Literal["left", "right"]
    planted: bool
    position_meters: Vector3


class AnimationClipSpec(StrictModel):
    clip_version_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    rig_version_id: str = Field(min_length=3)
    version_number: int = Field(ge=1)
    previous_version_id: Optional[str] = None
    name: str = Field(min_length=1)
    duration_seconds: float
    sample_rate_hz: float
    loop: bool
    root_motion: Literal["in_place", "extract", "apply"]
    start_pose: LoopPose
    end_pose: LoopPose
    root_samples: List[RootMotionSample] = Field(default_factory=list)
    foot_samples: List[FootPlantSample] = Field(default_factory=list)
    event_markers: List[AnimationEventMarker] = Field(default_factory=list)
    approval: ApprovalRecord = ApprovalRecord()
    provenance: Provenance

    @model_validator(mode="after")
    def clip_identity_kinds_are_distinct(self) -> "AnimationClipSpec":
        if len({self.clip_version_id, self.character_id, self.rig_version_id}) != 3:
            raise ValueError("clip, character, and rig identities must be distinct")
        if self.provenance.artifact_id != self.clip_version_id:
            raise ValueError("clip provenance must identify the clip version")
        if self.approval.state != self.provenance.approval_state:
            raise ValueError("clip approval and provenance approval state must match")
        return self


class RetargetBoneMapping(StrictModel):
    source_bone_id: str = Field(min_length=3)
    target_bone_id: str = Field(min_length=3)
    rotation_offset_degrees: Vector3 = (0.0, 0.0, 0.0)
    translation_scale: float = Field(default=1.0, gt=0)


class RetargetProfile(StrictModel):
    retarget_profile_id: str = Field(min_length=3)
    source_rig_version_id: str = Field(min_length=3)
    target_rig_version_id: str = Field(min_length=3)
    coordinate_system: CoordinateSystem
    mappings: List[RetargetBoneMapping] = Field(min_length=1)
    root_bone_mapping: RetargetBoneMapping
    provenance: Provenance

    @model_validator(mode="after")
    def rig_versions_are_distinct(self) -> "RetargetProfile":
        if self.source_rig_version_id == self.target_rig_version_id:
            raise ValueError("retarget source and target rigs must be distinct")
        if self.provenance.artifact_id != self.retarget_profile_id:
            raise ValueError("retarget provenance must identify the profile")
        if self.root_bone_mapping not in self.mappings:
            raise ValueError("root_bone_mapping must be included in mappings")
        return self


class AnimatorTransitionSpec(StrictModel):
    target_state_id: str = Field(min_length=3)
    condition_parameter: str = Field(min_length=1)
    comparison: Literal["equals", "not_equals", "greater", "less"]
    threshold: float
    duration_seconds: float = Field(ge=0)


class AnimatorStateSpec(StrictModel):
    animator_state_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    name: str = Field(min_length=1)
    clip_version_id: str = Field(min_length=3)
    speed: float = Field(gt=0)
    transitions: List[AnimatorTransitionSpec] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def provenance_identifies_state(self) -> "AnimatorStateSpec":
        if self.provenance.artifact_id != self.animator_state_id:
            raise ValueError("animator state provenance must identify the state")
        return self


class FixedPreviewCamera(StrictModel):
    camera_id: str = Field(min_length=3)
    coordinate_space: Literal["character_local"] = "character_local"
    position_meters: Vector3
    target_meters: Vector3
    vertical_fov_degrees: float = Field(gt=1, lt=179)
    resolution_width: int = Field(gt=0)
    resolution_height: int = Field(gt=0)


class PreviewArtifact(StrictModel):
    preview_artifact_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    rig_version_id: str = Field(min_length=3)
    clip_version_id: str = Field(min_length=3)
    artifact_uri: str = Field(min_length=1)
    media_type: Literal["video/mp4", "image/png", "application/vnd.sceneops.animation-preview+json"]
    frame_count: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    camera: FixedPreviewCamera
    captured_at: datetime
    execution_mode: ExecutionMode
    baseline_preview_artifact_id: Optional[str] = None
    frame_difference_score: Optional[float] = Field(default=None, ge=0, le=1)
    provenance: Provenance

    @field_validator("captured_at")
    @classmethod
    def normalize_capture_time(cls, value: datetime) -> datetime:
        normalized = normalize_utc(value)
        if normalized is None:
            raise ValueError("captured_at is required")
        return normalized

    @model_validator(mode="after")
    def preview_identity_is_distinct(self) -> "PreviewArtifact":
        identities = {
            self.preview_artifact_id,
            self.character_id,
            self.rig_version_id,
            self.clip_version_id,
        }
        if len(identities) != 4:
            raise ValueError("preview, character, rig, and clip identities must be distinct")
        if self.provenance.artifact_id != self.preview_artifact_id:
            raise ValueError("preview provenance must identify the preview artifact")
        if self.execution_mode != self.provenance.execution_mode:
            raise ValueError("preview and provenance execution modes must match")
        return self
