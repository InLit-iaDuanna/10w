"""Quality, comparison, ChangeSet, and API operation contracts."""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import Field, field_validator, model_validator

from .animation_models import (
    AnimationClipSpec,
    AnimatorStateSpec,
    FixedPreviewCamera,
    PreviewArtifact,
    RetargetProfile,
)
from .character_models import CharacterSpec, RigVersion, SkinVersion
from .common import (
    ApprovalRecord,
    ApprovalState,
    CheckStatus,
    ExecutionMode,
    ReviewDecision,
    Sha256Checksum,
    Severity,
    StrictModel,
    normalize_utc,
)


class QualityCheck(StrictModel):
    code: str = Field(min_length=3)
    status: CheckStatus
    severity: Severity
    message: str = Field(min_length=1)
    evidence: Dict[str, object] = Field(default_factory=dict)
    heuristic: bool = False
    limitation: Optional[str] = None


class QualityReport(StrictModel):
    report_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    mode: ExecutionMode
    checks: List[QualityCheck] = Field(min_length=1)
    automated_outcome: Literal["passed", "warnings", "failed", "blocked"]
    human_quality_approval: Literal[False] = False


class CharacterBundle(StrictModel):
    character: CharacterSpec
    rig: RigVersion
    skin: SkinVersion
    clips: List[AnimationClipSpec] = Field(min_length=1)
    retarget_profiles: List[RetargetProfile] = Field(default_factory=list)
    animator_states: List[AnimatorStateSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def child_owners_match(self) -> "CharacterBundle":
        character_id = self.character.character_id
        if self.rig.character_id != character_id or self.skin.character_id != character_id:
            raise ValueError("rig and skin must belong to the bundle character")
        if self.skin.rig_version_id != self.rig.rig_version_id:
            raise ValueError("skin must target the bundle rig version")
        if any(clip.character_id != character_id for clip in self.clips):
            raise ValueError("all clips must belong to the bundle character")
        return self


class CharacterInspectionRequest(StrictModel):
    request_id: str = Field(min_length=3)
    bundle: CharacterBundle
    mode: ExecutionMode


class CharacterInspectionResult(StrictModel):
    bundle: CharacterBundle
    report: QualityReport


class BoneChange(StrictModel):
    bone_id: str
    change: Literal["added", "removed", "renamed", "reparented"]
    previous_value: Optional[str] = None
    proposed_value: Optional[str] = None


class RigVersionDiff(StrictModel):
    base_rig_version_id: str
    proposed_rig_version_id: str
    bone_changes: List[BoneChange]
    coordinate_system_changed: bool
    reversible: Literal[True] = True


class EventMarkerChange(StrictModel):
    marker_id: str
    change: Literal["added", "removed", "renamed", "retimed"]
    previous_value: Optional[str] = None
    proposed_value: Optional[str] = None


class ClipVersionDiff(StrictModel):
    base_clip_version_id: str
    proposed_clip_version_id: str
    duration_delta_seconds: float
    loop_changed: bool
    root_motion_changed: bool
    event_marker_changes: List[EventMarkerChange]
    reversible: Literal[True] = True


class VersionComparisonRequest(StrictModel):
    request_id: str = Field(min_length=3)
    entity_type: Literal["rig", "clip"]
    base: Union[RigVersion, AnimationClipSpec]
    proposed: Union[RigVersion, AnimationClipSpec]


class VersionComparisonResult(StrictModel):
    entity_type: Literal["rig", "clip"]
    diff: Union[RigVersionDiff, ClipVersionDiff]


class VersionReviewRequest(StrictModel):
    request_id: str = Field(min_length=3)
    entity_type: Literal["rig", "clip"]
    entity_id: str = Field(min_length=3)
    decision: ReviewDecision
    reviewer_id: str = Field(min_length=3)
    reviewed_at: datetime
    comment: str = Field(min_length=1)

    @field_validator("reviewed_at")
    @classmethod
    def normalize_reviewed_at(cls, value: datetime) -> datetime:
        normalized = normalize_utc(value)
        if normalized is None:
            raise ValueError("reviewed_at is required")
        return normalized


class VersionReviewResult(StrictModel):
    entity_type: Literal["rig", "clip"]
    entity_id: str
    approval: ApprovalRecord
    rollback_version_id: Optional[str]


class ChangeSet(StrictModel):
    changeset_id: str = Field(min_length=3)
    base_version: str = Field(min_length=1)
    target_integration: Literal["blender", "unity"]
    target_object_ids: List[str] = Field(min_length=1)
    previous_values: Dict[str, object]
    proposed_values: Dict[str, object]
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: Literal["object", "character", "project"]
    risk: Literal["low", "medium", "high"]
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_requirements: List[str] = Field(min_length=1)
    approval_state: ApprovalState = ApprovalState.WAITING_APPROVAL
    dry_run: Literal[True] = True


class UnityCharacterMapping(StrictModel):
    mapping_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    rig_version_id: str = Field(min_length=3)
    skin_version_id: str = Field(min_length=3)
    clip_version_ids: List[str] = Field(min_length=1)
    unity_prefab_id: str = Field(min_length=3)
    unity_game_object_sceneops_id: str = Field(min_length=3)
    unity_animator_controller_id: str = Field(min_length=3)
    source_provenance_artifact_ids: List[str] = Field(min_length=3)
    source_provenance_checksums: List[Sha256Checksum] = Field(min_length=3)
    changeset_id: str = Field(min_length=3)
    approval_state: ApprovalState
    execution_mode: ExecutionMode

    @model_validator(mode="after")
    def stable_id_kinds_are_distinct(self) -> "UnityCharacterMapping":
        identities = {
            self.character_id,
            self.rig_version_id,
            self.skin_version_id,
            self.unity_prefab_id,
            self.unity_game_object_sceneops_id,
            self.unity_animator_controller_id,
        }
        if len(identities) != 6:
            raise ValueError("character, rig, skin, Prefab, scene object, and controller identities must be distinct")
        if len(self.source_provenance_artifact_ids) != len(self.source_provenance_checksums):
            raise ValueError("provenance artifact IDs and checksums must align")
        if len(set(self.source_provenance_artifact_ids)) != len(self.source_provenance_artifact_ids):
            raise ValueError("source provenance artifact IDs must be unique")
        if len(set(self.clip_version_ids)) != len(self.clip_version_ids):
            raise ValueError("clip version IDs must be unique")
        return self


class UnityMappingProposalRequest(StrictModel):
    request_id: str = Field(min_length=3)
    bundle: CharacterBundle
    unity_prefab_id: str = Field(min_length=3)
    unity_game_object_sceneops_id: str = Field(min_length=3)
    unity_animator_controller_id: str = Field(min_length=3)
    base_unity_version: str = Field(min_length=1)


class UnityMappingProposalResult(StrictModel):
    mapping: UnityCharacterMapping
    changeset: ChangeSet
    mode: ExecutionMode = ExecutionMode.PLANNED


class UnityMappingExecutionRequest(StrictModel):
    request_id: str = Field(min_length=3)
    timeout_seconds: float = Field(default=30, gt=0)
    mapping: UnityCharacterMapping
    changeset: ChangeSet


class PreviewCaptureRequest(StrictModel):
    request_id: str = Field(min_length=3)
    timeout_seconds: float = Field(default=30, gt=0)
    character: CharacterSpec
    rig: RigVersion
    clip: AnimationClipSpec
    camera: FixedPreviewCamera
    baseline_preview: Optional[PreviewArtifact] = None


class RetargetPreviewRequest(StrictModel):
    request_id: str = Field(min_length=3)
    timeout_seconds: float = Field(default=30, gt=0)
    character: CharacterSpec
    source_rig: RigVersion
    target_rig: RigVersion
    source_clip: AnimationClipSpec
    profile: RetargetProfile
    camera: FixedPreviewCamera


class RetargetPreviewResult(StrictModel):
    profile_valid: bool
    checks: List[QualityCheck]
    preview: Optional[PreviewArtifact]
    mode: ExecutionMode


class PreviewRegressionResult(StrictModel):
    baseline_preview_artifact_id: str
    candidate_preview_artifact_id: str
    same_fixed_camera: bool
    frame_difference_score: Optional[float]
    outcome: Literal["passed", "warning", "blocked"]
    limitation: str


class PreviewComparisonRequest(StrictModel):
    request_id: str = Field(min_length=3)
    baseline: PreviewArtifact
    candidate: PreviewArtifact


class ApiError(StrictModel):
    code: str
    message: str
    details: Dict[str, object]
    request_id: str
    retryable: bool
    suggested_actions: List[str]


class IntegrationAvailability(StrictModel):
    integration_id: str
    available: bool
    mode: ExecutionMode
    message: str
    supported_operations: List[str]


class IntegrationStatusResult(StrictModel):
    imported_character_path_available: Literal[True] = True
    integrations: List[IntegrationAvailability]
    generated_sources_message: str


class CharacterAnimationContractCatalog(StrictModel):
    character_spec: CharacterSpec
    rig_version: RigVersion
    skin_version: SkinVersion
    animation_clip_spec: AnimationClipSpec
    retarget_profile: RetargetProfile
    animator_state_spec: AnimatorStateSpec
    preview_artifact: PreviewArtifact
    unity_character_mapping: UnityCharacterMapping
    changeset: ChangeSet
