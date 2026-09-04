"""Public, dependency-free UI Studio contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Protocol


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ChangeSetState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


@dataclass(frozen=True)
class UiScreen:
    id: str
    title: str
    kind: str  # hud, menu, quest_prompt, feedback_prompt
    localized_text: dict[str, str]
    next_screen_ids: tuple[str, ...] = ()
    elements: tuple["UiElement", ...] = ()


@dataclass(frozen=True)
class UiElement:
    """A bounded element positioned from a named safe-area anchor."""
    id: str
    anchor: str
    offset_x: int
    offset_y: int
    width: int
    height: int


@dataclass(frozen=True)
class UiFlow:
    id: str
    game_template: str
    entry_screen_id: str
    screens: tuple[UiScreen, ...]


@dataclass(frozen=True)
class SafeArea:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class ResolutionProfile:
    name: str
    width: int
    height: int
    safe_area: SafeArea


@dataclass(frozen=True)
class UiMappingRequest:
    mapping_id: str
    flow_id: str
    screen_id: str
    unity_canvas_path: str
    prefab_id: str
    base_version: str
    actor_id: str
    source_project_id: str
    target_sceneops_ids: tuple[str, ...]


@dataclass(frozen=True)
class Provenance:
    artifact_id: str
    artifact_type: str
    source_project_id: str
    source_version: str
    producing_module: str
    tool: str
    adapter_version: str
    source_commit: str | None
    related_sceneops_ids: tuple[str, ...]
    recipe_version: str
    workflow_version: str
    creator: str
    mode: ExecutionMode
    occurred_at: str
    approval_state: ChangeSetState
    checksum: str
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_workflow_hash: str | None = None
    ai_prompt: str | None = None
    ai_negative_prompt: str | None = None
    ai_seed: int | None = None
    ai_parameters: dict[str, str] | None = None

    def validate(self) -> None:
        required = (self.artifact_id, self.artifact_type, self.source_project_id, self.source_version,
                    self.producing_module, self.tool, self.adapter_version, self.recipe_version,
                    self.workflow_version, self.creator, self.occurred_at)
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("provenance has an empty required field")
        if not re.fullmatch(r"[0-9a-f]{64}", self.checksum):
            raise ValueError("provenance checksum must be a 64-character lowercase hex value")
        if self.source_commit is not None and (not isinstance(self.source_commit, str) or not self.source_commit.strip()):
            raise ValueError("source commit must be omitted or non-empty")
        if not isinstance(self.related_sceneops_ids, tuple) or not all(isinstance(identity, str) and identity.strip() for identity in self.related_sceneops_ids):
            raise ValueError("related sceneops IDs must be non-empty strings")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", self.occurred_at):
            raise ValueError("provenance timestamp must be UTC ISO-8601")
        ai_values = (self.ai_provider, self.ai_model, self.ai_workflow_hash, self.ai_prompt,
                     self.ai_negative_prompt, self.ai_seed, self.ai_parameters)
        if any(value is not None for value in ai_values):
            if not all(value is not None for value in (self.ai_provider, self.ai_model, self.ai_workflow_hash, self.ai_prompt, self.ai_seed, self.ai_parameters)):
                raise ValueError("AI provenance requires provider, model, workflow hash, prompt, seed, and parameters")
            if not isinstance(self.ai_parameters, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in self.ai_parameters.items()):
                raise ValueError("AI provenance parameters must be string pairs")


@dataclass(frozen=True)
class UnityUiMappingResult:
    mapping_id: str
    unity_canvas_path: str
    prefab_id: str
    mode: ExecutionMode
    adapter_version: str
    message: str
    provenance: Provenance | None


class UnityUiAdapter(Protocol):
    """The only permitted boundary to engine-unity for UI mappings."""

    def capability_report(self) -> dict[str, bool]: ...
    def dry_run_ui_mapping(self, request: UiMappingRequest) -> UnityUiMappingResult: ...
    def publish_ui_mapping(self, request: UiMappingRequest) -> UnityUiMappingResult: ...


@dataclass
class ChangeSet:
    id: str
    request: UiMappingRequest
    base_version: str
    target_integration: str
    target_object_ids: tuple[str, ...]
    previous_values: dict[str, str]
    proposed_values: dict[str, str]
    rationale: str
    expected_result: str
    impact_scope: str
    risk: str
    validation_plan: str
    rollback_plan: str
    approval_requirements: tuple[str, ...]
    state: ChangeSetState = ChangeSetState.PROPOSED
    mapping_result: UnityUiMappingResult | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    _approval_snapshot: tuple[object, ...] | None = field(default=None, init=False, repr=False)

    def validate(self) -> None:
        text_values = (self.id, self.base_version, self.target_integration, self.request.mapping_id,
                       self.request.flow_id, self.request.screen_id, self.request.unity_canvas_path,
                       self.request.prefab_id, self.request.base_version, self.request.actor_id,
                       self.request.source_project_id, self.rationale,
                       self.expected_result, self.impact_scope, self.risk, self.validation_plan,
                       self.rollback_plan)
        if not all(isinstance(value, str) and value.strip() for value in text_values):
            raise ValueError("ChangeSet has an empty required field")
        if self.target_integration != "unity":
            raise ValueError("UI mappings must target the canonical unity integration")
        if self.base_version != self.request.base_version:
            raise ValueError("ChangeSet base_version must equal mapping request base_version")
        if not self.request.target_sceneops_ids or any(not target.startswith("so_") for target in self.request.target_sceneops_ids):
            raise ValueError("mapping request requires stable so_ target IDs")
        expected_targets = set(self.request.target_sceneops_ids)
        if set(self.target_object_ids) != expected_targets:
            raise ValueError("ChangeSet targets must exactly match mapping sceneops IDs")
        valid_values = lambda values: isinstance(values, dict) and bool(values) and all(isinstance(key, str) and key.strip() and isinstance(value, str) and value.strip() for key, value in values.items())
        if not valid_values(self.previous_values) or not valid_values(self.proposed_values) or not self.approval_requirements or not all(isinstance(requirement, str) and requirement.strip() for requirement in self.approval_requirements):
            raise ValueError("ChangeSet requires values and approval requirements")
        approved_mapping = {
            "flow_id": self.request.flow_id,
            "screen_id": self.request.screen_id,
            "unity_canvas_path": self.request.unity_canvas_path,
            "prefab_id": self.request.prefab_id,
        }
        if any(self.proposed_values.get(key) != value for key, value in approved_mapping.items()):
            raise ValueError("ChangeSet proposed values must identify the complete UI mapping")

    def _content_snapshot(self) -> tuple[object, ...]:
        return (
            self.id, self.state, self.request, self.base_version, self.target_integration, self.target_object_ids,
            tuple(sorted(self.previous_values.items())), tuple(sorted(self.proposed_values.items())),
            self.rationale, self.expected_result, self.impact_scope, self.risk,
            self.validation_plan, self.rollback_plan, self.approval_requirements,
            self.approved_by, self.approved_at,
        )

    def approve(self, approver: str, approved_at: str) -> None:
        if self.state is not ChangeSetState.PROPOSED:
            raise ValueError("only a proposed ChangeSet can be approved")
        self.validate()
        if not approver.strip() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", approved_at):
            raise ValueError("approval requires an approver and UTC timestamp")
        self.approved_by, self.approved_at = approver, approved_at
        self.state = ChangeSetState.APPROVED
        self._approval_snapshot = self._content_snapshot()

    def publish(self, adapter: UnityUiAdapter) -> UnityUiMappingResult:
        if self.state is not ChangeSetState.APPROVED:
            raise PermissionError("UI mapping requires explicit ChangeSet approval")
        self.validate()
        if not self.approved_by or not self.approved_at:
            raise PermissionError("UI mapping requires recorded approval evidence")
        if self._approval_snapshot != self._content_snapshot():
            raise PermissionError("UI mapping content changed after approval")
        if not adapter.capability_report().get("ui_mapping", False):
            raise ValueError("Unity adapter does not support UI mapping")
        result = adapter.publish_ui_mapping(self.request)
        if (result.mapping_id != self.request.mapping_id or result.prefab_id != self.request.prefab_id
                or result.unity_canvas_path != self.request.unity_canvas_path):
            raise ValueError("adapter output does not match the approved mapping target")
        if result.mode in (ExecutionMode.PLANNED, ExecutionMode.BLOCKED):
            raise ValueError("planned or blocked adapter output cannot be published")
        if result.provenance is None:
            raise ValueError("published adapter output requires provenance")
        result.provenance.validate()
        if result.provenance.approval_state is not ChangeSetState.PUBLISHED:
            raise ValueError("published adapter output provenance must be marked published")
        if (result.provenance.adapter_version != result.adapter_version or
                result.provenance.mode is not result.mode or
                result.provenance.source_project_id != self.request.source_project_id or
                result.provenance.source_version != self.request.base_version or
                set(result.provenance.related_sceneops_ids) != set(self.request.target_sceneops_ids)):
            raise ValueError("adapter output provenance does not match the approved mapping")
        self.mapping_result = result
        self.state = ChangeSetState.PUBLISHED
        return result


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    screen_id: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    flow_id: str
    issues: tuple[ValidationIssue, ...]
    mode: ExecutionMode
    provenance: Provenance

    @property
    def valid(self) -> bool:
        return not self.issues
