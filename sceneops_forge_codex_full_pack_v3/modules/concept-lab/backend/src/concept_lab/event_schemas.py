from __future__ import annotations

from datetime import datetime
from typing import Dict, Generic, Literal, Optional, TypeVar

from .schemas import ExecutionMode, ReviewAction, StrictModel


class ConceptVersionCreatedPayload(StrictModel):
    concept_id: str
    version: int
    change_set_id: Optional[str] = None


class ConceptVariantRecordedPayload(StrictModel):
    concept_id: str
    concept_version: int
    variant_id: str
    execution_mode: ExecutionMode


class ConceptVariantReviewedPayload(StrictModel):
    concept_id: str
    concept_version: int
    variant_id: str
    decision_id: str
    action: ReviewAction


class AssetSpecDraftCompiledPayload(StrictModel):
    concept_id: str
    concept_version: int
    variant_id: str
    asset_spec_draft_id: str


PayloadT = TypeVar("PayloadT", bound=StrictModel)


class EventEnvelope(StrictModel, Generic[PayloadT]):
    event_id: str
    event_type: str
    event_version: Literal[1] = 1
    occurred_at: datetime
    project_id: str
    correlation_id: str
    causation_id: str
    actor: Dict[str, str]
    mode: ExecutionMode
    payload: PayloadT


class ConceptVersionCreatedEvent(EventEnvelope[ConceptVersionCreatedPayload]):
    event_type: Literal["concept.version.created"]


class ConceptVariantRecordedEvent(EventEnvelope[ConceptVariantRecordedPayload]):
    event_type: Literal["concept.variant.recorded"]


class ConceptVariantReviewedEvent(EventEnvelope[ConceptVariantReviewedPayload]):
    event_type: Literal["concept.variant.reviewed"]


class AssetSpecDraftCompiledEvent(EventEnvelope[AssetSpecDraftCompiledPayload]):
    event_type: Literal["concept.asset_spec_draft.compiled"]
