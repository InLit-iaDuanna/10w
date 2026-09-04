from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional, Protocol, Union

from .event_schemas import (
    AssetSpecDraftCompiledPayload,
    AssetSpecDraftCompiledEvent,
    ConceptVariantRecordedPayload,
    ConceptVariantRecordedEvent,
    ConceptVariantReviewedPayload,
    ConceptVariantReviewedEvent,
    ConceptVersionCreatedPayload,
    ConceptVersionCreatedEvent,
)
from .schemas import ConceptDecision, ConceptSpec, ConceptVariant, ExecutionMode


ConceptLabEvent = Union[
    ConceptVersionCreatedEvent,
    ConceptVariantRecordedEvent,
    ConceptVariantReviewedEvent,
    AssetSpecDraftCompiledEvent,
]


class EventPublisher(Protocol):
    def publish(self, event: ConceptLabEvent) -> None: ...


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.events: List[ConceptLabEvent] = []

    def publish(self, event: ConceptLabEvent) -> None:
        self.events.append(event.model_copy(deep=True))


class ConceptEventEmitter:
    def __init__(
        self,
        publisher: EventPublisher,
        id_factory: Callable[[str], str],
        clock: Callable[[], datetime],
    ) -> None:
        self.publisher = publisher
        self.id_factory = id_factory
        self.clock = clock

    def version_created(
        self,
        spec: ConceptSpec,
        change_set_id: Optional[str],
        actor: str,
        correlation: str,
        causation: str,
    ) -> None:
        self.publisher.publish(
            ConceptVersionCreatedEvent(
                **self._fields(
                    spec, actor, correlation, causation, ExecutionMode.LIVE
                ),
                event_type="concept.version.created",
                payload=ConceptVersionCreatedPayload(
                    concept_id=spec.concept_id,
                    version=spec.version,
                    change_set_id=change_set_id,
                ),
            )
        )

    def variant_recorded(
        self,
        spec: ConceptSpec,
        variant: ConceptVariant,
        actor: str,
        correlation: str,
        causation: str,
    ) -> None:
        self.publisher.publish(
            ConceptVariantRecordedEvent(
                **self._fields(
                    spec, actor, correlation, causation, variant.execution_mode
                ),
                event_type="concept.variant.recorded",
                payload=ConceptVariantRecordedPayload(
                    concept_id=spec.concept_id,
                    concept_version=spec.version,
                    variant_id=variant.variant_id,
                    execution_mode=variant.execution_mode,
                ),
            )
        )

    def variant_reviewed(
        self,
        spec: ConceptSpec,
        variant: ConceptVariant,
        decision: ConceptDecision,
        correlation: str,
        causation: str,
    ) -> None:
        self.publisher.publish(
            ConceptVariantReviewedEvent(
                **self._fields(
                    spec,
                    decision.reviewer_id,
                    correlation,
                    causation,
                    variant.execution_mode,
                ),
                event_type="concept.variant.reviewed",
                payload=ConceptVariantReviewedPayload(
                    concept_id=spec.concept_id,
                    concept_version=spec.version,
                    variant_id=variant.variant_id,
                    decision_id=decision.decision_id,
                    action=decision.action,
                ),
            )
        )

    def asset_spec_compiled(
        self,
        spec: ConceptSpec,
        variant: ConceptVariant,
        draft_id: str,
        actor: str,
        correlation: str,
        causation: str,
    ) -> None:
        self.publisher.publish(
            AssetSpecDraftCompiledEvent(
                **self._fields(
                    spec, actor, correlation, causation, variant.execution_mode
                ),
                event_type="concept.asset_spec_draft.compiled",
                payload=AssetSpecDraftCompiledPayload(
                    concept_id=spec.concept_id,
                    concept_version=spec.version,
                    variant_id=variant.variant_id,
                    asset_spec_draft_id=draft_id,
                ),
            )
        )

    def _fields(self, spec, actor, correlation, causation, mode):
        return {
            "event_id": self.id_factory("evt"),
            "occurred_at": self.clock(),
            "project_id": spec.project_id,
            "correlation_id": correlation,
            "causation_id": causation,
            "actor": {"type": "user", "id": actor},
            "mode": mode,
        }
