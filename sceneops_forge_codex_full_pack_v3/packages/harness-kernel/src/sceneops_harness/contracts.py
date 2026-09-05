"""Canonical V5 planning contracts; execution is separate from a proposal."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sceneops_core_contracts import ChangeSet, ExecutionMode


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class HarnessContract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RuntimeBudget(HarnessContract):
    max_steps: int = Field(default=32, ge=1, le=256)
    max_attempts_per_step: int = Field(default=2, ge=1, le=10)
    max_duration_seconds: float = Field(default=300, gt=0, le=86400)
    max_tokens: int = Field(default=32000, ge=0)
    max_cost_usd: float = Field(default=1, ge=0, allow_inf_nan=False)
    usage_policy: Literal["require_reported", "bounded_calls"] = "require_reported"
    max_metered_calls: int = Field(default=4, ge=0, le=16)


class ResourceRef(HarnessContract):
    id: str
    kind: str
    source_version: str | None = None
    reason: str = ""


class AcceptanceCriterion(HarnessContract):
    id: str
    description: str
    evidence_required: list[str] = Field(default_factory=list)


class ProductionIntent(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("intent"))
    project_id: str
    goal: str = Field(min_length=1, max_length=16000)
    desired_outcome: str = ""
    constraints: list[str] = Field(default_factory=list)
    protected_baseline: list[ResourceRef] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)
    deadline: str | None = None
    allowed_mutation_scopes: list[str] = Field(default_factory=list)
    forbidden_mutation_scopes: list[str] = Field(default_factory=list)
    requested_artifacts: list[str] = Field(default_factory=list)


class ContextItem(HarnessContract):
    ref: ResourceRef
    content: JsonValue
    inclusion_reason: str
    execution_mode: ExecutionMode = ExecutionMode.PLANNED


class ContextBundle(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("context"))
    project_id: str
    intent_id: str
    items: list[ContextItem] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class Condition(HarnessContract):
    """Only literal, top-level input/output predicates; never executable expressions."""
    source: Literal["inputs", "outputs"] = "inputs"
    field: str
    operator: Literal["equals", "exists"] = "equals"
    value: JsonValue = None


class RetryPolicy(HarnessContract):
    max_attempts: int = Field(default=1, ge=1, le=10)
    retryable_codes: list[str] = Field(default_factory=list)
    side_effect_retry_safe: bool = False


class CapabilityDefinition(HarnessContract):
    id: str
    provider_module_id: str
    title: str
    purpose: str = ""
    version: str = "1"
    input_schema: dict[str, JsonValue] = Field(default_factory=dict)
    output_schema: dict[str, JsonValue] = Field(default_factory=dict)
    mode: Literal["read", "plan", "mutate", "validate", "build", "test"] = "read"
    risk: Literal["low", "medium", "high", "critical"] = "low"
    execution_mode: ExecutionMode = ExecutionMode.PLANNED
    availability_reason: str | None = None
    required_context: list[str] = Field(default_factory=list)
    required_integrations: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    preconditions: list[Condition] = Field(default_factory=list)
    postconditions: list[Condition] = Field(default_factory=list)
    evidence_produced: list[str] = Field(default_factory=list)
    supports_dry_run: bool = False
    supports_rollback: bool = False
    cross_system: bool = False
    timeout_seconds: float = Field(default=60, gt=0, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    estimated_duration_seconds: float | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)
    metered: bool = True
    allowed_agent_roles: list[str] = Field(default_factory=list)


class ConnectorDefinition(HarnessContract):
    id: str
    title: str
    status: Literal["available", "offline", "planned", "blocked"] = "planned"
    reason: str | None = None
    version: str | None = None


class Authority(HarnessContract):
    project_id: str
    actor_id: str
    actor_type: Literal["user", "agent", "service", "system"] = "user"
    permissions: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)


class ModelRoutingDecision(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("routing"))
    agent_role: str
    tier: Literal["fast", "standard", "reasoning", "vision", "player"] = "standard"
    provider: str
    model: str | None = None
    reason: str
    escalation_count: int = Field(default=0, ge=0)
    execution_mode: ExecutionMode = ExecutionMode.PLANNED


class ProductionAgentDefinition(HarnessContract):
    id: str
    role: str
    title: str
    allowed_capabilities: list[str] = Field(default_factory=list)
    model_tier: Literal["fast", "standard", "reasoning", "vision", "player"] = "standard"
    prompt: str
    context_policy: list[str] = Field(default_factory=list)
    maximum_handoffs: int = Field(default=1, ge=0, le=10)


class AgentTask(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("agent_task"))
    agent_role: str
    objective: str
    context_refs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)


class AgentResult(HarnessContract):
    task_id: str
    agent_role: str
    summary: str
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    proposed_capabilities: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    routing_decision: ModelRoutingDecision


class AgentHandoff(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("handoff"))
    from_task_id: str
    to_task: AgentTask
    reason: str
    context_refs: list[str] = Field(default_factory=list)


class PipelineStep(HarnessContract):
    id: str
    title: str
    kind: Literal["agent", "tool", "approval", "policy_gate", "evaluator", "fan_out", "fan_in", "sub_pipeline", "retry", "rollback"] = "tool"
    capability_id: str | None = None
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    input_schema: dict[str, JsonValue] = Field(default_factory=dict)
    output_schema: dict[str, JsonValue] = Field(default_factory=dict)
    conditions: list[Condition] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    failure_strategy: Literal["stop", "ask_human"] = "stop"
    evidence_requirements: list[str] = Field(default_factory=list)
    checkpoint: bool = True
    dry_run: bool = False
    change_set: ChangeSet | None = None
    snapshot_ref: str | None = None
    agent_task: AgentTask | None = None
    model_routing: ModelRoutingDecision | None = None


class PipelineStage(HarnessContract):
    id: str
    title: str
    steps: list[PipelineStep] = Field(min_length=1)


class PipelineDefinition(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("pipeline"))
    schema_version: Literal[5] = 5
    project_id: str
    intent_id: str
    title: str = "制作流水线"
    stages: list[PipelineStage] = Field(min_length=1)
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    context_refs: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)
    rollback_strategy: Literal["manual", "none"] = "manual"
    template_source: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.PLANNED


class ValidationIssue(HarnessContract):
    code: str
    message: str
    step_id: str | None = None


class ValidationReport(HarnessContract):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    approval_steps: list[str] = Field(default_factory=list)
