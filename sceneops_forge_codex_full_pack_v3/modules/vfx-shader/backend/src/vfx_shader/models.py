"""Typed, dependency-free VFX/Shader domain contracts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import re
from typing import Any, Mapping, Optional


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ApprovalState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class QualityTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ParameterKind(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    COLOR = "color"


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    kind: ParameterKind
    label_zh: str
    default: Any
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None

    def validate(self, value: Any) -> tuple[str, ...]:
        errors: list[str] = []
        if self.kind is ParameterKind.BOOLEAN:
            if type(value) is not bool:
                errors.append(f"{self.key} must be boolean")
            return tuple(errors)
        if self.kind is ParameterKind.COLOR:
            if not (
                isinstance(value, str)
                and len(value) == 7
                and value.startswith("#")
                and all(c in "0123456789abcdefABCDEF" for c in value[1:])
            ):
                errors.append(f"{self.key} must be #RRGGBB")
            return tuple(errors)
        if self.kind is ParameterKind.INTEGER:
            valid_number = type(value) is int
        else:
            valid_number = type(value) in (int, float)
        if not valid_number:
            return (f"{self.key} must be {self.kind.value}",)
        numeric = float(value)
        if self.minimum is not None and numeric < self.minimum:
            errors.append(f"{self.key} must be >= {self.minimum}")
        if self.maximum is not None and numeric > self.maximum:
            errors.append(f"{self.key} must be <= {self.maximum}")
        return tuple(errors)


@dataclass(frozen=True)
class QualityBudget:
    max_particles: int
    max_overdraw_layers: float
    max_screen_coverage_percent: float


QUALITY_BUDGETS: Mapping[QualityTier, QualityBudget] = {
    QualityTier.LOW: QualityBudget(64, 1.5, 8.0),
    QualityTier.MEDIUM: QualityBudget(128, 2.5, 14.0),
    QualityTier.HIGH: QualityBudget(256, 4.0, 22.0),
}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _freeze_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True)
class EventBinding:
    binding_id: str
    event_name: str
    target_sceneops_id: str
    action: str
    enabled: bool

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.binding_id.startswith("vfxbind_"):
            errors.append("binding_id must start with vfxbind_")
        if not self.target_sceneops_id.startswith("so_"):
            errors.append("target_sceneops_id must start with so_")
        if self.action not in {"enable", "disable", "pulse"}:
            errors.append("action must be enable, disable, or pulse")
        if "." not in self.event_name:
            errors.append("event_name must be namespaced")
        return tuple(errors)


@dataclass(frozen=True)
class Provenance:
    artifact_id: str
    artifact_type: str
    source_project_id: str
    source_version: str
    source_commit: Optional[str]
    related_sceneops_ids: tuple[str, ...]
    producing_module: str
    tool: str
    adapter_version: str
    recipe_version: str
    creator: str
    execution_mode: ExecutionMode
    timestamp: str
    checksum_sha256: str
    approval_state: ApprovalState
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    workflow_hash: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    ai_parameters: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        required = {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "source_project_id": self.source_project_id,
            "source_version": self.source_version,
            "producing_module": self.producing_module,
            "tool": self.tool,
            "adapter_version": self.adapter_version,
            "recipe_version": self.recipe_version,
            "creator": self.creator,
            "timestamp": self.timestamp,
            "checksum_sha256": self.checksum_sha256,
        }
        errors = [f"{key} is required" for key, value in required.items() if not value]
        if self.producing_module != "vfx-shader":
            errors.append("producing_module must be vfx-shader")
        if len(self.checksum_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.checksum_sha256.lower()):
            errors.append("checksum_sha256 must be 64 hexadecimal characters")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", self.timestamp):
            errors.append("timestamp must be UTC ISO-8601")
        if not self.related_sceneops_ids or any(not value.startswith("so_") for value in self.related_sceneops_ids):
            errors.append("related_sceneops_ids must contain stable sceneops IDs")
        if self.execution_mode is ExecutionMode.LIVE and self.tool == "deterministic-fixture":
            errors.append("deterministic fixtures cannot claim live execution")
        ai_values = (self.ai_provider, self.ai_model, self.workflow_hash, self.prompt,
                     self.negative_prompt, self.seed)
        if (any(value is not None for value in ai_values) or bool(self.ai_parameters)) and not all(
            (self.ai_provider, self.ai_model, self.workflow_hash, self.prompt, self.seed is not None, self.ai_parameters)
        ):
            errors.append("AI provenance requires provider, model, workflow_hash, prompt, seed, and parameters")
        return tuple(errors)


@dataclass(frozen=True)
class VfxShaderRecipe:
    recipe_id: str
    version: str
    template_id: str
    title_zh: str
    shader_family: str
    quality_tier: QualityTier
    parameter_specs: tuple[ParameterSpec, ...]
    parameters: Mapping[str, Any]
    particle_count: int
    estimated_overdraw_layers: float
    estimated_screen_coverage_percent: float
    bindings: tuple[EventBinding, ...]
    provenance: Provenance
    optional: bool = True

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.recipe_id.startswith("vfxrec_"):
            errors.append("recipe_id must start with vfxrec_")
        specs = {spec.key: spec for spec in self.parameter_specs}
        if set(specs) != set(self.parameters):
            errors.append("parameters must exactly match parameter_specs")
        for key, value in self.parameters.items():
            if key in specs:
                errors.extend(specs[key].validate(value))
        for binding in self.bindings:
            errors.extend(binding.validate())
        errors.extend(self.provenance.validate())
        return tuple(errors)

    def with_binding_enabled(self, binding_id: str, enabled: bool) -> "VfxShaderRecipe":
        if not any(binding.binding_id == binding_id for binding in self.bindings):
            raise KeyError(binding_id)
        bindings = tuple(
            replace(binding, enabled=enabled) if binding.binding_id == binding_id else binding
            for binding in self.bindings
        )
        return replace(self, bindings=bindings)


@dataclass(frozen=True)
class BudgetWarning:
    code: str
    metric: str
    actual: float
    allowed: float
    message_zh: str


@dataclass(frozen=True)
class PreviewPlan:
    preview_id: str
    recipe_id: str
    quality_tier: QualityTier
    passes: tuple[str, ...]
    seed: int
    frame_count: int
    execution_mode: ExecutionMode
    warnings: tuple[BudgetWarning, ...]


@dataclass(frozen=True)
class ChangeSet:
    change_set_id: str
    base_version: str
    target_integration: str
    target_object_ids: tuple[str, ...]
    previous_values: Mapping[str, Any]
    proposed_values: Mapping[str, Any]
    rationale: str
    expected_result: str
    impact_scope: str
    risk: str
    validation_plan: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    approval_requirements: tuple[str, ...]
    approval_state: ApprovalState
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_snapshot: Optional[tuple[Any, ...]] = field(default=None, repr=False)

    def _content_snapshot(self) -> tuple[Any, ...]:
        return (
            self.change_set_id, self.base_version, self.target_integration, self.target_object_ids,
            _freeze_value(self.previous_values), _freeze_value(self.proposed_values), self.rationale,
            self.expected_result, self.impact_scope, self.risk, self.validation_plan,
            self.rollback_plan, self.approval_requirements, self.approval_state,
            self.approved_by, self.approved_at,
        )

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.change_set_id.startswith("chg_"):
            errors.append("change_set_id must start with chg_")
        if not self.base_version:
            errors.append("base_version is required")
        if self.target_integration != "unity":
            errors.append("target_integration must be unity")
        if not self.target_object_ids or any(not value.startswith("so_") for value in self.target_object_ids):
            errors.append("target_object_ids must contain stable sceneops IDs")
        required_text = (self.rationale, self.expected_result, self.impact_scope, self.risk)
        if any(not value for value in required_text):
            errors.append("rationale, expected_result, impact_scope, and risk are required")
        if not self.validation_plan or not self.rollback_plan or not self.approval_requirements:
            errors.append("validation, rollback, and approval plans are required")
        if self.approval_state is ApprovalState.APPROVED and not (self.approved_by and self.approved_at):
            errors.append("approved ChangeSet requires approved_by and approved_at")
        if self.approval_state is ApprovalState.APPROVED and self.approval_snapshot != self._content_snapshot():
            errors.append("approved ChangeSet content changed after approval")
        return tuple(errors)

    def approve(self, actor_id: str, occurred_at: str) -> "ChangeSet":
        if self.approval_state is not ApprovalState.PROPOSED:
            raise ValueError("only a proposed ChangeSet can be approved")
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if not actor_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", occurred_at):
            raise ValueError("approval requires actor and UTC timestamp")
        approved = replace(self, approval_state=ApprovalState.APPROVED, approved_by=actor_id, approved_at=occurred_at)
        return replace(approved, approval_snapshot=approved._content_snapshot())


@dataclass(frozen=True)
class EventActor:
    type: str
    id: str


@dataclass(frozen=True)
class EventContext:
    event_id: str
    occurred_at: str
    project_id: str
    correlation_id: str
    causation_id: str
    actor: EventActor


@dataclass(frozen=True)
class PublicationRequest:
    recipe: VfxShaderRecipe
    change_set: ChangeSet
    event_context: EventContext


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    code: str
    message_zh: str
    execution_mode: ExecutionMode
    blocks_core_build: bool
    events: tuple[Mapping[str, Any], ...] = ()
    adapter_result_id: Optional[str] = None
    output_provenance: Optional[Provenance] = None
