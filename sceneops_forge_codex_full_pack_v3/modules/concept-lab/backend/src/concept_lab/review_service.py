from __future__ import annotations

from typing import Iterable, List

from .domain_helpers import Clock, IdFactory, get_references, get_variant, set_spec_status
from .errors import ConceptLabError, ReviewGateError
from .events import ConceptEventEmitter
from .repository import ConceptRepository
from .schemas import (
    AssetSpecDraft,
    ConceptDecision,
    ConceptStatus,
    ExecutionMode,
    PermissionStatus,
    ReviewAction,
    StyleCheck,
    StyleEvidenceInput,
    VariantComment,
    VariantComparison,
    VariantComparisonEntry,
    VariantStatus,
)
from .style_checks import evaluate_declared_style_evidence


class ConceptReviewService:
    def __init__(
        self,
        repository: ConceptRepository,
        events: ConceptEventEmitter,
        id_factory: IdFactory,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.events = events
        self.id_factory = id_factory
        self.clock = clock

    def add_style_check(
        self,
        concept_id: str,
        concept_version: int,
        variant_id: str,
        evidence: Iterable[StyleEvidenceInput],
        *,
        created_by: str,
    ) -> StyleCheck:
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        variant = get_variant(record, variant_id, concept_version)
        evidence_items = list(evidence)
        invalid_references = sorted(
            {
                item.evidence_reference_id
                for item in evidence_items
                if item.evidence_reference_id not in variant.reference_ids
            }
        )
        if invalid_references:
            raise ReviewGateError(
                "STYLE_EVIDENCE_REFERENCE_INVALID",
                "Style evidence must point to a reference in the reviewed variant.",
                reference_ids=invalid_references,
            )
        check = evaluate_declared_style_evidence(
            spec,
            variant,
            evidence_items,
            style_check_id=self.id_factory("sty"),
            created_by=created_by,
            now=self.clock(),
        )
        record.style_checks.setdefault(variant_id, []).append(check)
        self.repository.save(concept_id, record)
        return check

    def comment_on_variant(
        self, concept_id: str, variant_id: str, body: str, author_id: str
    ) -> VariantComment:
        record = self.repository.get(concept_id)
        get_variant(record, variant_id)
        comment = VariantComment(
            comment_id=self.id_factory("com"),
            variant_id=variant_id,
            body=body,
            author_id=author_id,
            created_at=self.clock(),
        )
        record.comments.setdefault(variant_id, []).append(comment)
        self.repository.save(concept_id, record)
        return comment

    def compare_variants(
        self, concept_id: str, concept_version: int, variant_ids: List[str]
    ) -> VariantComparison:
        if len(variant_ids) < 2 or len(set(variant_ids)) != len(variant_ids):
            raise ConceptLabError(
                "COMPARISON_REQUIRES_DISTINCT_VARIANTS",
                "Compare at least two distinct variants.",
            )
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        entries = [self._comparison_entry(record, spec, value) for value in variant_ids]
        return VariantComparison(
            comparison_id=self.id_factory("cmp"),
            concept_id=concept_id,
            concept_version=concept_version,
            entries=entries,
            created_at=self.clock(),
        )

    def review_variant(
        self,
        concept_id: str,
        concept_version: int,
        variant_id: str,
        action: ReviewAction,
        *,
        rationale: str,
        reviewer_id: str,
        acknowledge_license_warning: bool,
        correlation_id: str,
        causation_id: str,
    ) -> ConceptDecision:
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        variant = get_variant(record, variant_id, concept_version)
        if variant.status != VariantStatus.PROPOSED:
            raise ReviewGateError(
                "VARIANT_ALREADY_REVIEWED",
                "A reviewed variant cannot receive another terminal decision.",
                status=variant.status.value,
            )
        if action == ReviewAction.APPROVE:
            self._assert_approval_gates(
                record, spec, variant, acknowledge_license_warning
            )
        status = (
            VariantStatus.APPROVED
            if action == ReviewAction.APPROVE
            else VariantStatus.REJECTED
        )
        record.variants[variant_id] = variant.model_copy(update={"status": status})
        if status == VariantStatus.APPROVED:
            set_spec_status(record, concept_version, ConceptStatus.APPROVED)
        else:
            same_version = [
                value
                for value in record.variants.values()
                if value.concept_version == concept_version
            ]
            if any(value.status == VariantStatus.APPROVED for value in same_version):
                next_status = ConceptStatus.APPROVED
            elif same_version and all(
                value.status == VariantStatus.REJECTED for value in same_version
            ):
                next_status = ConceptStatus.REJECTED
            else:
                next_status = ConceptStatus.IN_REVIEW
            set_spec_status(record, concept_version, next_status)
        decision = ConceptDecision(
            decision_id=self.id_factory("dec"),
            concept_id=concept_id,
            concept_version=concept_version,
            variant_id=variant_id,
            action=action,
            rationale=rationale,
            reviewer_id=reviewer_id,
            acknowledged_license_warning=acknowledge_license_warning,
            created_at=self.clock(),
        )
        record.decisions.append(decision)
        self.repository.save(concept_id, record)
        self.events.variant_reviewed(
            spec, variant, decision, correlation_id, causation_id
        )
        return decision

    def compile_asset_spec_draft(
        self,
        concept_id: str,
        concept_version: int,
        variant_id: str,
        *,
        actor_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> AssetSpecDraft:
        record = self.repository.get(concept_id)
        spec = record.spec_at(concept_version)
        variant = get_variant(record, variant_id, concept_version)
        if variant.status != VariantStatus.APPROVED:
            raise ReviewGateError(
                "APPROVED_CONCEPT_REQUIRED",
                "Only an approved concept variant can compile an AssetSpec draft.",
            )
        decision = next(
            (
                value
                for value in reversed(record.decisions)
                if value.variant_id == variant_id and value.action == ReviewAction.APPROVE
            ),
            None,
        )
        if decision is None:
            raise ReviewGateError(
                "APPROVAL_DECISION_MISSING", "The approval decision could not be found."
            )
        draft = AssetSpecDraft(
            asset_spec_draft_id=self.id_factory("asd"),
            source_concept_id=concept_id,
            source_concept_version=concept_version,
            approved_variant_id=variant_id,
            approval_decision_id=decision.decision_id,
            project_id=spec.project_id,
            feature_id=spec.feature_id,
            task_id=spec.task_id,
            subject=spec.subject,
            gameplay_function=spec.gameplay_function,
            proportions=spec.proportions,
            dimensions=spec.dimensions,
            materials=spec.materials,
            required_views=spec.required_views,
            platform_budget=spec.platform_budget,
            style_constraints=spec.style_constraints,
            forbidden_elements=spec.forbidden_elements,
            concept_reference_ids=variant.reference_ids,
            execution_mode=variant.execution_mode,
            created_by=actor_id,
            created_at=self.clock(),
        )
        record.asset_spec_drafts[draft.asset_spec_draft_id] = draft
        self.repository.save(concept_id, record)
        self.events.asset_spec_compiled(
            spec,
            variant,
            draft.asset_spec_draft_id,
            actor_id,
            correlation_id,
            causation_id,
        )
        return draft

    @staticmethod
    def _assert_approval_gates(record, spec, variant, acknowledged):
        if variant.execution_mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ReviewGateError(
                "VARIANT_NOT_EXECUTED",
                "A planned or blocked variant cannot be approved.",
            )
        references = get_references(record, variant.reference_ids)
        permissions = {reference.source.permission_status for reference in references}
        if PermissionStatus.BLOCKED in permissions:
            raise ReviewGateError(
                "LICENSE_PERMISSION_BLOCKED",
                "A reference is not permitted for downstream use.",
            )
        if PermissionStatus.WARNING in permissions and not acknowledged:
            raise ReviewGateError(
                "LICENSE_WARNING_ACKNOWLEDGEMENT_REQUIRED",
                "Review the reference license warning before approval.",
            )
        missing = sorted(
            set(spec.required_views) - set(variant.covered_views),
            key=lambda value: value.value,
        )
        if missing:
            raise ReviewGateError(
                "REQUIRED_VIEWS_MISSING",
                "The variant does not cover every required view.",
                missing_views=[value.value for value in missing],
            )
        if not record.style_checks.get(variant.variant_id):
            raise ReviewGateError(
                "STYLE_CHECK_REQUIRED",
                "Record reviewable style evidence before approval.",
            )

    @staticmethod
    def _comparison_entry(record, spec, variant_id):
        variant = get_variant(record, variant_id, spec.version)
        references = get_references(record, variant.reference_ids)
        checks = record.style_checks.get(variant_id, [])
        latest = checks[-1] if checks else None
        return VariantComparisonEntry(
            variant_id=variant_id,
            status=variant.status,
            execution_mode=variant.execution_mode,
            covered_views=variant.covered_views,
            missing_required_views=sorted(
                set(spec.required_views) - set(variant.covered_views),
                key=lambda value: value.value,
            ),
            permission_statuses=sorted(
                {reference.source.permission_status for reference in references},
                key=lambda value: value.value,
            ),
            latest_style_assessment=latest.assessment if latest else None,
            latest_style_confidence=latest.confidence if latest else None,
        )
