from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field

from .schemas import (
    AiGenerationMetadata,
    ArtifactProvenance,
    ConceptVariant,
    ExecutionMode,
    GenerationState,
    ReferenceSource,
    RequiredView,
    StrictModel,
)


class GenerationRequest(StrictModel):
    concept_id: str
    concept_version: int = Field(ge=1)
    title: str = Field(min_length=1)
    requested_views: List[RequiredView] = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: Optional[str] = None
    seed: int = Field(ge=0)
    workflow_version: str = Field(min_length=1)
    execution_mode: ExecutionMode
    adapter_id: str = Field(min_length=1)
    model: Optional[str] = None
    fixture_key: Optional[str] = None


class GeneratedViewArtifact(StrictModel):
    view: RequiredView
    title: str = Field(min_length=1)
    artifact_uri: str = Field(min_length=1)
    source: ReferenceSource
    provenance: ArtifactProvenance


class GenerationOutput(StrictModel):
    execution_mode: ExecutionMode
    generation: AiGenerationMetadata
    artifacts: List[GeneratedViewArtifact] = Field(min_length=1)


class GenerationRun(StrictModel):
    run_id: str
    request: GenerationRequest
    state: GenerationState
    execution_mode: ExecutionMode
    reason: Optional[str] = None
    result_variant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GenerationOutcome(StrictModel):
    run: GenerationRun
    variant: Optional[ConceptVariant] = None


class AdapterHealth(StrictModel):
    adapter_id: str
    available: bool
    execution_mode: ExecutionMode
    reason: Optional[str] = None


class GenerationCapabilities(StrictModel):
    adapter_id: str
    supported_views: List[RequiredView]
    supports_turnaround: bool
    models: List[str]
    timeout_seconds: int = Field(default=120, gt=0)
    retry_limit: int = Field(default=0, ge=0)
    supports_cancellation: bool = False


class GenerationPlan(StrictModel):
    adapter_id: str
    execution_mode: ExecutionMode
    requested_views: List[RequiredView]
    model: Optional[str] = None
    approval_required: Literal[True] = True
    warnings: List[str] = Field(default_factory=list)
