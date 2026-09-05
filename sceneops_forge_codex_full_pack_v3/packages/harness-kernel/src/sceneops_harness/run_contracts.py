"""Durable run, observation and recovery records."""
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue
from sceneops_core_contracts import ChangeSet, ExecutionMode

from .contracts import (
    AgentResult, AgentTask, Authority, HarnessContract, ModelRoutingDecision,
    PipelineDefinition, RuntimeBudget, new_id, utc_now,
)

RunState = Literal["draft", "compiling", "awaiting_approval", "queued", "running", "observing", "recovering", "verifying", "completed", "blocked", "failed", "cancelled", "rolled_back"]
StepState = Literal["pending", "ready", "assigned", "running", "evaluating", "succeeded", "failed", "waiting_approval", "blocked", "skipped", "cancelled", "rolled_back"]


class CapabilityInvocation(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("invocation"))
    project_id: str
    run_id: str
    step_id: str
    step_run_id: str
    attempt: int = Field(ge=1)
    capability_id: str
    inputs: dict[str, JsonValue]
    execution_mode: ExecutionMode
    metered: bool = True
    dry_run: bool = False
    change_set_id: str | None = None
    change_set: ChangeSet | None = None
    snapshot_ref: str | None = None
    agent_task: AgentTask | None = None
    model_routing: ModelRoutingDecision | None = None
    authority: Authority
    budget: RuntimeBudget
    dependency_outputs: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


class AcceptanceResult(HarnessContract):
    criterion_id: str
    passed: bool
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)


class StepEvaluation(HarnessContract):
    step_run_id: str
    deterministic_facts: list[str] = Field(default_factory=list)
    ai_interpretation: str | None = None
    acceptance_results: list[AcceptanceResult] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    next_disposition: Literal["continue", "recover", "await_human", "abort"] = "continue"


class CapabilityResult(HarnessContract):
    execution_mode: ExecutionMode
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_types: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    rollback_ref: str | None = None
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    tokens: int | None = Field(default=None, ge=0)
    evaluation: StepEvaluation | None = None
    agent_result: AgentResult | None = None


class AttemptRecord(HarnessContract):
    invocation: CapabilityInvocation
    started_at: datetime
    ended_at: datetime | None = None
    state: StepState = "running"
    result: CapabilityResult | None = None
    error_code: str | None = None
    error: str | None = None


class RollbackAttempt(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("rollback_attempt"))
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    state: Literal["running", "succeeded", "uncertain"] = "running"
    approved_by: str
    result: CapabilityResult | None = None
    reason: str | None = None


class StepRun(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("step_run"))
    step_id: str
    stage_id: str
    state: StepState = "pending"
    execution_mode: ExecutionMode = ExecutionMode.PLANNED
    attempts: list[AttemptRecord] = Field(default_factory=list)
    result: CapabilityResult | None = None
    reason: str | None = None
    approved_by: list[str] = Field(default_factory=list)
    rollback_approved_by: str | None = None
    checkpoint_at: datetime | None = None
    rollback_result: CapabilityResult | None = None
    rollback_state: Literal["not_started", "running", "succeeded", "uncertain"] = "not_started"
    rollback_attempts: list[RollbackAttempt] = Field(default_factory=list)


class PipelineRun(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("run"))
    project_id: str
    request_id: str
    definition: PipelineDefinition
    submitted_by: str
    state: RunState = "queued"
    execution_mode: ExecutionMode = ExecutionMode.PLANNED
    step_runs: list[StepRun]
    reason: str | None = None
    cancel_requested: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: float = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    budget_accounting_complete: bool = True
    metered_calls_used: int = Field(default=0, ge=0)
    revision: int = 0
    owner_pid: int | None = None


class HarnessEvent(HarnessContract):
    sequence: int
    schema_version: Literal[1] = 1
    project_id: str
    run_id: str
    event_type: str
    occurred_at: datetime
    step_id: str | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class CauseCandidate(HarnessContract):
    description: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)


class FailureAnalysis(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("failure"))
    run_id: str
    step_id: str
    deterministic_facts: list[str]
    cause_candidates: list[CauseCandidate] = Field(default_factory=list)
    interpretation: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class RecoveryPlan(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("recovery"))
    run_id: str
    step_id: str
    cause_candidates: list[CauseCandidate] = Field(default_factory=list)
    selected_action: Literal["retry", "retry_adjusted", "add_context", "upgrade_model", "switch_capability", "split_step", "rollback", "ask_human", "abort"]
    proposed_changes: list[dict[str, JsonValue]] = Field(default_factory=list)
    new_budget_impact: float = Field(default=0, ge=0)
    requires_approval: bool = True
    maximum_additional_attempts: int = Field(default=0, ge=0, le=10)
    reason: str
    status: Literal["proposed", "approved", "applied", "rejected"] = "proposed"


class DistilledWorkflow(HarnessContract):
    id: str = Field(default_factory=lambda: new_id("workflow"))
    project_id: str
    source_run_id: str
    title: str
    pipeline_template: PipelineDefinition
    skill: str
    agent_roles: list[str] = Field(default_factory=list)
    required_context: list[str] = Field(default_factory=list)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    approval_policy: list[str] = Field(default_factory=list)
    recovery_strategy: str
    limitations: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
