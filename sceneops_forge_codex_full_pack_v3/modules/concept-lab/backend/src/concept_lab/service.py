from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence
from uuid import uuid4

from .adapters import ConceptGenerationAdapter
from .domain_helpers import (
    Clock,
    IdFactory,
    attach_reference_to_spec,
    derived_mode,
    get_references,
    new_variant,
    set_spec_status,
)
from .errors import ConceptLabError, ConflictError, NotFoundError, ReviewGateError
from .events import ConceptEventEmitter, EventPublisher, InMemoryEventPublisher
from .generation_service import ConceptGenerationService
from .generation_schemas import GenerationOutcome, GenerationRequest
from .repository import ConceptRecord, ConceptRepository, InMemoryConceptRepository
from .review_service import ConceptReviewService
from .schemas import (
    AssetSpecDraft,
    ChangeSetStatus,
    ConceptChangeSet,
    ConceptCreateInput,
    ConceptDecision,
    ConceptPatch,
    ConceptReference,
    ConceptSpec,
    ConceptStatus,
    ConceptVariant,
    ExecutionMode,
    ImportedReferenceInput,
    ReferenceKind,
    ReviewAction,
    StyleCheck,
    StyleEvidenceInput,
    VariantComment,
    VariantComparison,
)
from .workspace_schemas import ConceptReviewWorkspace
from .workspace_reader import ConceptWorkspaceReader


def random_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConceptLabService:
    """Public facade composed from lifecycle, generation, and review services."""

    def __init__(
        self,
        repository: Optional[ConceptRepository] = None,
        *,
        adapters: Optional[Sequence[ConceptGenerationAdapter]] = None,
        event_publisher: Optional[EventPublisher] = None,
        id_factory: IdFactory = random_id,
        clock: Clock = utc_now,
    ) -> None:
        self.repository = repository or InMemoryConceptRepository()
        self.events = event_publisher or InMemoryEventPublisher()
        self.id_factory = id_factory
        self.clock = clock
        emitter = ConceptEventEmitter(self.events, id_factory, clock)
        self._event_emitter = emitter
        self._generation = ConceptGenerationService(
            self.repository, adapters or [], emitter, id_factory, clock
        )
        self._review = ConceptReviewService(
            self.repository, emitter, id_factory, clock
        )
        self._workspace = ConceptWorkspaceReader(self.repository)

    def create_concept(
        self,
        request: ConceptCreateInput,
        *,
        actor_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> ConceptSpec:
        now = self.clock()
        spec = ConceptSpec(
            **request.model_dump(),
            concept_id=self.id_factory("cpt"),
            version=1,
            created_at=now,
            updated_at=now,
            authored_by=actor_id,
        )
        self.repository.add(ConceptRecord(specs=[spec]))
        self._event_emitter.version_created(
            spec, None, actor_id, correlation_id, causation_id
        )
        return spec

    def get_concept(self, concept_id: str, version: Optional[int] = None) -> ConceptSpec:
        record = self.repository.get(concept_id)
        return record.spec_at(version) if version else record.latest_spec

    def list_versions(self, concept_id: str) -> List[ConceptSpec]:
        return self.repository.get(concept_id).specs

    def get_review_workspace(
        self, concept_id: str, version: Optional[int] = None
    ) -> ConceptReviewWorkspace:
        return self._workspace.get(concept_id, version)

    def propose_change(
        self,
        concept_id: str,
        base_version: int,
        patch: ConceptPatch,
        *,
        rationale: str,
        expected_result: str,
        impact_scope: List[str],
        risk: str,
        validation_plan: List[str],
        rollback_plan: str,
        proposed_by: str,
        proposed_by_type: str,
    ) -> ConceptChangeSet:
        record = self.repository.get(concept_id)
        base = record.spec_at(base_version)
        proposed = patch.model_dump(exclude_none=True)
        base_values = base.model_dump()
        proposed = {
            name: value
            for name, value in proposed.items()
            if value != base_values[name]
        }
        if not proposed:
            raise ConceptLabError("EMPTY_CHANGE_SET", "At least one field must change.")
        candidate = {**base_values, **proposed}
        ConceptSpec.model_validate(candidate)
        change_set = ConceptChangeSet(
            change_set_id=self.id_factory("chg"),
            concept_id=concept_id,
            base_version=base_version,
            target_object_ids=[concept_id],
            previous_values={name: base_values[name] for name in proposed},
            proposed_values=proposed,
            rationale=rationale,
            expected_result=expected_result,
            impact_scope=impact_scope,
            risk=risk,
            validation_plan=validation_plan,
            rollback_plan=rollback_plan,
            approval_requirements=["concept:review"],
            proposed_by=proposed_by,
            proposed_by_type=proposed_by_type,
            status=ChangeSetStatus.PROPOSED,
            created_at=self.clock(),
        )
        record.change_sets[change_set.change_set_id] = change_set
        self.repository.save(concept_id, record)
        return change_set

    def approve_change(
        self, concept_id: str, change_set_id: str, reviewer_id: str
    ) -> ConceptChangeSet:
        record = self.repository.get(concept_id)
        change_set = self._change_set(record, change_set_id)
        if change_set.status != ChangeSetStatus.PROPOSED:
            raise ReviewGateError(
                "CHANGE_SET_NOT_PROPOSED",
                "Only a proposed ChangeSet can be approved.",
                status=change_set.status.value,
            )
        change_set = change_set.model_copy(
            update={
                "status": ChangeSetStatus.APPROVED,
                "approved_by": reviewer_id,
                "approved_at": self.clock(),
            }
        )
        record.change_sets[change_set_id] = change_set
        self.repository.save(concept_id, record)
        return change_set

    def apply_change(
        self,
        concept_id: str,
        change_set_id: str,
        *,
        actor_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> ConceptSpec:
        record = self.repository.get(concept_id)
        change_set = self._change_set(record, change_set_id)
        if change_set.status != ChangeSetStatus.APPROVED:
            raise ReviewGateError(
                "CHANGE_SET_APPROVAL_REQUIRED",
                "The Concept ChangeSet must be approved before it is applied.",
                status=change_set.status.value,
            )
        latest = record.latest_spec
        if latest.version != change_set.base_version:
            raise ConflictError(
                "The concept changed after this ChangeSet was proposed.",
                expected_version=change_set.base_version,
                actual_version=latest.version,
            )
        updated = self._apply_patch(latest, change_set, actor_id)
        record.specs.append(updated)
        record.change_sets[change_set_id] = change_set.model_copy(
            update={"status": ChangeSetStatus.APPLIED, "applied_at": self.clock()}
        )
        self.repository.save(concept_id, record)
        self._event_emitter.version_created(
            updated, change_set_id, actor_id, correlation_id, causation_id
        )
        return updated

    def import_reference(
        self, concept_id: str, concept_version: int, value: ImportedReferenceInput
    ) -> ConceptReference:
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        if value.source.kind != ReferenceKind.IMPORTED:
            raise ConceptLabError(
                "REFERENCE_KIND_INVALID", "Imported references must declare kind=imported."
            )
        if value.provenance.source_project_id != spec.project_id:
            raise ConceptLabError(
                "PROVENANCE_PROJECT_MISMATCH",
                "Reference provenance must match the concept project.",
            )
        if value.provenance.execution_mode in {
            ExecutionMode.PLANNED,
            ExecutionMode.BLOCKED,
        }:
            raise ConceptLabError(
                "ARTIFACT_MODE_NOT_EXECUTED",
                "A planned or blocked operation cannot supply an imported artifact.",
            )
        reference = ConceptReference(
            **value.model_dump(),
            reference_id=self.id_factory("ref"),
            concept_id=concept_id,
            concept_version=concept_version,
            imported_at=self.clock(),
        )
        record.references[reference.reference_id] = reference
        attach_reference_to_spec(record, reference.reference_id, concept_version)
        self.repository.save(concept_id, record)
        return reference

    def create_imported_variant(
        self,
        concept_id: str,
        concept_version: int,
        *,
        title: str,
        reference_ids: List[str],
        actor_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> ConceptVariant:
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        references = get_references(record, reference_ids)
        if any(reference.source.kind != ReferenceKind.IMPORTED for reference in references):
            raise ConceptLabError(
                "IMPORTED_VARIANT_REFERENCE_INVALID",
                "Imported variants can contain imported references only.",
            )
        mode = derived_mode(reference.provenance.execution_mode for reference in references)
        variant = new_variant(
            spec, title, references, mode, self.id_factory, self.clock
        )
        record.variants[variant.variant_id] = variant
        set_spec_status(record, concept_version, ConceptStatus.IN_REVIEW)
        self.repository.save(concept_id, record)
        self._event_emitter.variant_recorded(
            spec, variant, actor_id, correlation_id, causation_id
        )
        return variant

    def generate_variant(self, request: GenerationRequest, **context) -> GenerationOutcome:
        return self._generation.generate_variant(request, **context)

    def add_style_check(
        self,
        concept_id: str,
        concept_version: int,
        variant_id: str,
        evidence: Iterable[StyleEvidenceInput],
        *,
        created_by: str,
    ) -> StyleCheck:
        return self._review.add_style_check(
            concept_id,
            concept_version,
            variant_id,
            evidence,
            created_by=created_by,
        )

    def comment_on_variant(
        self, concept_id: str, variant_id: str, body: str, author_id: str
    ) -> VariantComment:
        return self._review.comment_on_variant(concept_id, variant_id, body, author_id)

    def compare_variants(
        self, concept_id: str, concept_version: int, variant_ids: List[str]
    ) -> VariantComparison:
        return self._review.compare_variants(concept_id, concept_version, variant_ids)

    def review_variant(
        self,
        concept_id: str,
        concept_version: int,
        variant_id: str,
        action: ReviewAction,
        **context,
    ) -> ConceptDecision:
        return self._review.review_variant(
            concept_id, concept_version, variant_id, action, **context
        )

    def compile_asset_spec_draft(
        self, concept_id: str, concept_version: int, variant_id: str, **context
    ) -> AssetSpecDraft:
        return self._review.compile_asset_spec_draft(
            concept_id, concept_version, variant_id, **context
        )

    def _apply_patch(
        self, latest: ConceptSpec, change_set: ConceptChangeSet, actor_id: str
    ) -> ConceptSpec:
        values = latest.model_dump()
        values.update(change_set.proposed_values)
        values.update(
            version=latest.version + 1,
            status=ConceptStatus.DRAFT,
            updated_at=self.clock(),
            authored_by=actor_id,
        )
        return ConceptSpec.model_validate(values)

    @staticmethod
    def _change_set(record: ConceptRecord, change_set_id: str) -> ConceptChangeSet:
        try:
            return record.change_sets[change_set_id]
        except KeyError as error:
            raise NotFoundError("concept ChangeSet", change_set_id) from error
