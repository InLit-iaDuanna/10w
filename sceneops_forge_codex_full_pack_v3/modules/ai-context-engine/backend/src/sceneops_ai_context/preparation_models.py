"""Public contracts for task-scoped production preparation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


ProductionKind = Literal["game_create", "game_modify", "modeling", "scene", "planning", "export"]
CandidateKind = Literal["asset", "experience", "skill", "capability"]
CandidateScope = Literal["builtin", "shared", "current_project"]
PreparationStatus = Literal["succeeded", "failed", "skipped"]
CallStatus = Literal["succeeded", "failed", "cancelled", "skipped"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class ProductionPreparationRequest(StrictModel):
    """Facts and limits fixed by the caller for one user production request."""

    project_id: str = Field(min_length=1, max_length=200)
    request_key: str = Field(min_length=1, max_length=200)
    production_kind: ProductionKind
    requirement: str = Field(min_length=1, max_length=20_000)
    confirmed_direction: str | None = Field(default=None, max_length=10_000)
    target_platform: str | None = Field(default=None, max_length=100)
    current_state: dict[str, JsonValue] = Field(default_factory=dict)
    available_capability_ids: list[str] = Field(default_factory=list, max_length=200)
    model_call_allowed: bool = True
    remaining_model_calls: int = Field(default=1, ge=0, le=1_000)
    remaining_time_seconds: float | None = Field(default=None, gt=0, le=86_400)


class CandidateSummary(StrictModel):
    """A whole, compact catalogue item supplied through a public provider."""

    provider_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=300)
    kind: CandidateKind
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=4_000)
    scope: CandidateScope
    project_id: str | None = Field(default=None, max_length=200)
    version: str | None = Field(default=None, max_length=200)
    revision: int | None = Field(default=None, ge=1)
    enabled: bool = True
    production_kinds: list[ProductionKind] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list, max_length=50)
    required_capability_ids: list[str] = Field(default_factory=list, max_length=50)
    disputed: bool = False
    counterexamples: list[str] = Field(default_factory=list, max_length=20)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identity(self):
        if self.scope == "current_project" and not self.project_id:
            raise ValueError("current-project candidates require project_id")
        if self.scope != "current_project" and self.project_id is not None:
            raise ValueError("builtin/shared candidates cannot carry a project_id")
        if self.kind == "asset" and not self.version:
            raise ValueError("asset candidates require a version")
        if self.kind == "experience" and self.revision is None:
            raise ValueError("experience candidates require a revision")
        if self.disputed and not self.counterexamples:
            raise ValueError("disputed candidates require counterexamples")
        return self


class CandidateDirectory(StrictModel):
    project_id: str
    request_key: str
    character_budget: int = 24_000
    character_count: int = 0
    candidates: list[CandidateSummary] = Field(default_factory=list)
    omitted_count: int = 0
    source_errors: list[str] = Field(default_factory=list)


class CandidateSearchRequest(StrictModel):
    request: ProductionPreparationRequest
    query: str = Field(default="", max_length=2_000)
    kinds: list[CandidateKind] = Field(default_factory=list, max_length=4)


class CandidateIdentity(StrictModel):
    provider_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=300)
    kind: CandidateKind
    version: str | None = Field(default=None, max_length=200)
    revision: int | None = Field(default=None, ge=1)


class CandidateDetailRequest(StrictModel):
    request: ProductionPreparationRequest
    identity: CandidateIdentity


class CandidateDetail(StrictModel):
    identity: CandidateIdentity
    title: str = Field(min_length=1, max_length=300)
    content: JsonValue


class RecommendationSelection(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=300)
    version: str | None = Field(default=None, max_length=200)
    revision: int | None = Field(default=None, ge=1)
    purpose: str = Field(min_length=1, max_length=1_000)
    adoption: Literal["use", "import", "modify", "create", "reference"]
    reason: str = Field(min_length=1, max_length=2_000)
    considered_counterexample: str | None = Field(default=None, max_length=2_000)


class ProductionRecommendationDraft(StrictModel):
    """Strict model output. It is advice and never an executable instruction."""

    assets: list[RecommendationSelection] = Field(default_factory=list, max_length=1_000)
    experiences: list[RecommendationSelection] = Field(default_factory=list, max_length=6)
    skills: list[RecommendationSelection] = Field(default_factory=list, max_length=4)
    capability_ids: list[str] = Field(default_factory=list, max_length=200)
    production_advice: list[str] = Field(default_factory=list, max_length=30)
    conflicts: list[str] = Field(default_factory=list, max_length=30)
    gaps: list[str] = Field(default_factory=list, max_length=30)


class RecommendationModelConfig(StrictModel):
    provider_id: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    timeout_seconds: float = Field(default=30.0, gt=0, le=30.0)


class RecommendationProviderResponse(StrictModel):
    structured: dict[str, JsonValue]
    provider_id: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    usage: dict[str, int] | None = None
    cost_usd: float | None = Field(default=None, ge=0)


class RecommendationCallRecord(StrictModel):
    call_id: str
    provider_id: str | None = None
    model: str | None = None
    status: CallStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0, le=30)
    usage: dict[str, int] | None = None
    cost_usd: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    error_message: str | None = None


class ProductionPreparationResult(StrictModel):
    preparation_id: str
    project_id: str
    request_key: str
    status: PreparationStatus
    candidate_directory: CandidateDirectory
    recommendation: ProductionRecommendationDraft | None = None
    call: RecommendationCallRecord
    failure_code: str | None = None
    failure_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reused: bool = False
