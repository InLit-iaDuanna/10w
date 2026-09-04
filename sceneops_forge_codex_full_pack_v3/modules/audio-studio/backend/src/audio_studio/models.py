"""Typed local domain contracts for Audio Studio."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class AssetStatus(str, Enum):
    PROPOSAL = "proposal"
    PUBLISHED = "published"


class ChangeSetStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass(frozen=True)
class Provenance:
    artifact_id: str
    artifact_type: str
    source_project_id: str
    source_version: str
    source_commit: str | None
    related_sceneops_ids: tuple[str, ...]
    producing_module: str
    tool_name: str
    tool_version: str
    adapter_version: str | None
    recipe_version: str | None
    creator: str
    mode: ExecutionMode
    occurred_at: str
    approval_state: str
    sha256: str
    provider: str | None = None
    model: str | None = None
    workflow_hash: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    relevant_parameters: dict[str, str | int | float | bool] | None = None
    seed: int | None = None


@dataclass(frozen=True)
class AudioSpec:
    spec_id: str
    project_id: str
    purpose: str
    intended_events: tuple[str, ...]
    target_mixer_group: str
    generation_reference: str | None = None


@dataclass(frozen=True)
class AudioMetadata:
    format: str
    channels: int
    sample_rate_hz: int
    bit_depth: int
    duration_seconds: float


@dataclass(frozen=True)
class AudioAnalysis:
    metadata: AudioMetadata
    peak_dbfs: float
    approximate_loudness_dbfs: float
    waveform_peaks: tuple[float, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AudioAsset:
    asset_id: str
    status: AssetStatus
    provenance: Provenance
    analysis: AudioAnalysis


@dataclass(frozen=True)
class EventBinding:
    binding_id: str
    gameplay_event: str
    audio_asset_id: str
    optional: bool = True


@dataclass
class ChangeSet:
    change_set_id: str
    status: ChangeSetStatus
    base_version: str
    target_integration: str
    target_object_ids: tuple[str, ...]
    previous_values: dict[str, str | None]
    proposed_values: dict[str, str]
    rationale: str
    expected_result: str
    impact_scope: str
    risk: str
    validation_plan: str
    rollback_plan: str
    approval_requirements: tuple[str, ...]
    approval_evidence: tuple[str, ...]
    approved_by: str | None = None
    approved_at: str | None = None
    _approval_snapshot: tuple[object, ...] | None = field(default=None, init=False, repr=False)

    def _content_snapshot(self) -> tuple[object, ...]:
        return (
            self.change_set_id, self.status, self.base_version, self.target_integration, self.target_object_ids,
            tuple(sorted(self.previous_values.items())), tuple(sorted(self.proposed_values.items())),
            self.rationale, self.expected_result, self.impact_scope, self.risk,
            self.validation_plan, self.rollback_plan, self.approval_requirements, self.approval_evidence,
            self.approved_by, self.approved_at,
        )

    def _record_approval(self) -> None:
        self._approval_snapshot = self._content_snapshot()

    @property
    def approval_matches_content(self) -> bool:
        return self._approval_snapshot is not None and self._approval_snapshot == self._content_snapshot()


@dataclass(frozen=True)
class AudioMapping:
    mapping_id: str
    binding: EventBinding
    target_sceneops_id: str
    audio_source_name: str
    mixer_group: str


@dataclass(frozen=True)
class ModuleState:
    state: Literal["ready", "disabled", "offline"]
    user_message: str
    mode: ExecutionMode


@dataclass(frozen=True)
class AdapterCapabilities:
    supports_audio_mapping: bool
    supports_dry_run: bool
    adapter_version: str


@dataclass(frozen=True)
class AdapterHealth:
    online: bool
    message: str
    mode: ExecutionMode
    adapter_version: str


@dataclass(frozen=True)
class MappingResult:
    status: Literal["proposed", "published", "failed"]
    mode: ExecutionMode
    adapter_version: str
    message: str
    mapping_id: str
    target_sceneops_id: str
    audio_asset_id: str
    audio_source_name: str
    mixer_group: str
    provenance: Provenance | None


class EngineUnityAudioAdapter(Protocol):
    """The sole public boundary to engine-unity for AudioSource/Mixer changes."""

    def get_capabilities(self) -> AdapterCapabilities: ...

    def health_check(self) -> AdapterHealth: ...

    def dry_run_audio_mapping(self, mapping: AudioMapping, change_set: ChangeSet) -> MappingResult: ...

    def publish_audio_mapping(self, mapping: AudioMapping, change_set: ChangeSet) -> MappingResult: ...
