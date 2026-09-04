"""Versioned public event schemas for this module."""

from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import Field, field_validator

from .common import ExecutionMode, StrictModel, normalize_utc


class EventActor(StrictModel):
    type: Literal["user", "agent", "system"]
    id: str = Field(min_length=3)


class EventEnvelope(StrictModel):
    event_id: str = Field(min_length=3)
    occurred_at: datetime
    project_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    causation_id: str = Field(min_length=3)
    actor: EventActor
    mode: ExecutionMode

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        normalized = normalize_utc(value)
        if normalized is None:
            raise ValueError("occurred_at is required")
        return normalized


class CharacterInspectedPayload(StrictModel):
    character_id: str
    rig_version_id: str
    skin_version_id: str
    report_id: str
    automated_outcome: Literal["passed", "warnings", "failed", "blocked"]


class CharacterInspectedEvent(EventEnvelope):
    event_type: Literal["character.inspected"] = "character.inspected"
    event_version: Literal[1] = 1
    payload: CharacterInspectedPayload


class VersionApprovedPayload(StrictModel):
    character_id: str
    version_id: str
    version_number: int = Field(ge=1)
    reviewer_id: str
    rollback_version_id: Optional[str]


class RigVersionApprovedEvent(EventEnvelope):
    event_type: Literal["rig.version.approved"] = "rig.version.approved"
    event_version: Literal[1] = 1
    payload: VersionApprovedPayload


class AnimationClipApprovedEvent(EventEnvelope):
    event_type: Literal["animation.clip.approved"] = "animation.clip.approved"
    event_version: Literal[1] = 1
    payload: VersionApprovedPayload


class AnimationPreviewCapturedPayload(StrictModel):
    preview_artifact_id: str
    character_id: str
    rig_version_id: str
    clip_version_id: str
    camera_id: str
    artifact_uri: str


class AnimationPreviewCapturedEvent(EventEnvelope):
    event_type: Literal["animation.preview.captured"] = "animation.preview.captured"
    event_version: Literal[1] = 1
    payload: AnimationPreviewCapturedPayload


class UnityCharacterMappingAppliedPayload(StrictModel):
    mapping_id: str
    character_id: str
    rig_version_id: str
    skin_version_id: str
    unity_prefab_id: str
    unity_game_object_sceneops_id: str
    changeset_id: str


class UnityCharacterMappingAppliedEvent(EventEnvelope):
    event_type: Literal["unity.character.mapping.applied"] = "unity.character.mapping.applied"
    event_version: Literal[1] = 1
    payload: UnityCharacterMappingAppliedPayload


EVENT_MODELS: Dict[str, type] = {
    "character.inspected": CharacterInspectedEvent,
    "rig.version.approved": RigVersionApprovedEvent,
    "animation.clip.approved": AnimationClipApprovedEvent,
    "animation.preview.captured": AnimationPreviewCapturedEvent,
    "unity.character.mapping.applied": UnityCharacterMappingAppliedEvent,
}
