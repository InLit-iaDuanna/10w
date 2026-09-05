from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sceneops_harness import (ProductionIntent, ContextBundle, PipelineDefinition, RuntimeBudget,
    ValidationReport, ModelRoutingDecision, RecoveryPlan, StepEvaluation, FailureAnalysis,
    CapabilityDefinition, ConnectorDefinition, ProductionAgentDefinition)
from sceneops_ai_routing import ModelProfile

ModuleId = Literal["project-planning", "concept-assets", "character-animation", "world-logic",
    "ui-audio-vfx", "render-ops", "unity-build", "version-review", "ai-playtest", "integration-ops"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanningRequest(ApiModel):
    project_id: str
    goal: str = Field(min_length=1, max_length=16000)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    module_ids: list[ModuleId] = Field(default_factory=list)
    selection: dict[str, JsonValue] = Field(default_factory=dict)
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)


class PipelineProposal(ApiModel):
    id: str = Field(default_factory=lambda: "proposal_" + uuid4().hex)
    project_id: str
    intent: ProductionIntent
    context: ContextBundle
    definition: PipelineDefinition
    validation: ValidationReport
    routing: list[ModelRoutingDecision] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    execution_mode: Literal["planned"] = "planned"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProposedStep(ApiModel):
    id: str
    title: str
    capability_id: str
    agent_role: str | None = None
    objective: str = ""
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class ProposedStage(ApiModel):
    id: str
    title: str
    steps: list[ProposedStep] = Field(min_length=1, max_length=32)


class PlanOutline(ApiModel):
    title: str
    stages: list[ProposedStage] = Field(min_length=1, max_length=12)
    missing_facts: list[str] = Field(default_factory=list)


class StartRequest(ApiModel):
    request_id: str = Field(min_length=1, max_length=200)


class RunAction(ApiModel):
    action: Literal["cancel", "retry", "approve", "approve_rollback", "rollback"]
    step_id: str | None = None
    inspection_confirmed: bool = False


class RunObservation(ApiModel):
    evaluations: list[StepEvaluation]
    failures: list[FailureAnalysis]


class RecoveryResponse(ApiModel):
    proposal: RecoveryPlan
    executable: bool


class TitleRequest(ApiModel):
    title: str = Field(min_length=1, max_length=160)


class HarnessCatalog(ApiModel):
    version: Literal["5.0"] = "5.0"
    capabilities: list[CapabilityDefinition]
    connectors: list[ConnectorDefinition]
    agents: list[ProductionAgentDefinition]
    model_profiles: list[ModelProfile] = Field(default_factory=list)
    model_provider: str
    default_model: str
    notice: str = "目录表示可调用合同，不代表已验证生产能力。外部工具尚未接入 V5 执行。"


class HarnessAPIError(ApiModel):
    code: str
    message: str
    retryable: bool = False
