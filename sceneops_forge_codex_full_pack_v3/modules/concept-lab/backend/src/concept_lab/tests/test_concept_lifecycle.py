from __future__ import annotations

from copy import deepcopy

import pytest

from concept_lab.errors import ConceptLabError, ReviewGateError
from concept_lab.schemas import (
    ConceptPatch,
    ImportedReferenceInput,
    ReviewAction,
    StyleEvidenceInput,
)
from concept_lab.tests.conftest import complete_style_evidence


def _add_two_view_variant(
    service, concept, payload, command_fields, *, title="导入方案", permission="cleared"
):
    references = []
    for view, suffix in [("front", "front"), ("three_quarter", "three")]:
        value = deepcopy(payload)
        value["title"] = f"{title}-{view}"
        value["view"] = view
        value["source"]["permission_status"] = permission
        value["provenance"]["artifact_id"] = f"art_{suffix}_{title}"
        value["provenance"]["checksum_sha256"] = (
            "b" if suffix == "front" else "c"
        ) * 64
        reference = service.import_reference(
            concept.concept_id,
            concept.version,
            ImportedReferenceInput.model_validate(value),
        )
        references.append(reference)
    variant = service.create_imported_variant(
        concept.concept_id,
        concept.version,
        title=title,
        reference_ids=[reference.reference_id for reference in references],
        **command_fields,
    )
    evidence = [
        StyleEvidenceInput.model_validate(value)
        for value in complete_style_evidence(references[0].reference_id)
    ]
    service.add_style_check(
        concept.concept_id,
        concept.version,
        variant.variant_id,
        evidence,
        created_by="usr_art_director",
    )
    return variant, references


def test_concept_create_edit_and_version_requires_approved_changeset(
    service, concept, command_fields
):
    assert concept.version == 1
    assert concept.project_bible_version_id == "pbv_remember_home_003"

    change = service.propose_change(
        concept.concept_id,
        1,
        ConceptPatch(materials=["aged brass", "blackened iron"]),
        rationale="AI proposes a less reflective inset.",
        expected_result="The key remains legible without a modern gloss.",
        impact_scope=["concept", "materials"],
        risk="low",
        validation_plan=["Review both required views"],
        rollback_plan="Keep concept version 1 as the rollback target.",
        proposed_by="agent_concept",
        proposed_by_type="agent",
    )
    with pytest.raises(ReviewGateError, match="approved"):
        service.apply_change(
            concept.concept_id, change.change_set_id, **command_fields
        )

    service.approve_change(concept.concept_id, change.change_set_id, "usr_producer")
    updated = service.apply_change(
        concept.concept_id, change.change_set_id, **command_fields
    )
    versions = service.list_versions(concept.concept_id)
    assert [value.version for value in versions] == [1, 2]
    assert versions[0].materials == ["aged brass", "darkened steel inset"]
    assert updated.materials == ["aged brass", "blackened iron"]
    assert updated.status.value == "draft"


def test_no_op_edit_does_not_create_a_changeset(service, concept):
    with pytest.raises(ConceptLabError) as error:
        service.propose_change(
            concept.concept_id,
            1,
            ConceptPatch(subject=concept.subject),
            rationale="No effective change.",
            expected_result="No change.",
            impact_scope=["concept"],
            risk="low",
            validation_plan=["Compare values"],
            rollback_plan="No rollback needed.",
            proposed_by="agent_concept",
            proposed_by_type="agent",
        )
    assert error.value.code == "EMPTY_CHANGE_SET"


def test_imported_reference_preserves_provenance_and_license_warning(
    service, concept, imported_reference_payload
):
    payload = deepcopy(imported_reference_payload)
    payload["source"]["license_name"] = "License requires art-director review"
    payload["source"]["permission_status"] = "warning"
    reference = service.import_reference(
        concept.concept_id,
        1,
        ImportedReferenceInput.model_validate(payload),
    )
    assert reference.source.permission_status.value == "warning"
    assert reference.provenance.checksum_sha256 == "a" * 64
    assert reference.provenance.execution_mode.value == "mock"
    assert reference.reference_id in service.get_concept(concept.concept_id).reference_ids


def test_planned_or_blocked_operation_cannot_claim_an_imported_artifact(
    service, concept, imported_reference_payload
):
    payload = deepcopy(imported_reference_payload)
    payload["provenance"]["execution_mode"] = "planned"
    with pytest.raises(ConceptLabError) as error:
        service.import_reference(
            concept.concept_id,
            1,
            ImportedReferenceInput.model_validate(payload),
        )
    assert error.value.code == "ARTIFACT_MODE_NOT_EXECUTED"


def test_compare_comment_approve_and_reject_keep_both_decisions(
    service, concept, imported_reference_payload, command_fields
):
    approved_variant, _ = _add_two_view_variant(
        service, concept, imported_reference_payload, command_fields, title="方案 A"
    )
    rejected_variant, _ = _add_two_view_variant(
        service, concept, imported_reference_payload, command_fields, title="方案 B"
    )
    comment = service.comment_on_variant(
        concept.concept_id,
        rejected_variant.variant_id,
        "齿部轮廓过于现代。",
        "usr_art_director",
    )
    assert comment.body == "齿部轮廓过于现代。"

    service.review_variant(
        concept.concept_id,
        1,
        approved_variant.variant_id,
        ReviewAction.APPROVE,
        rationale="方案 A 最符合门锁与可读性要求。",
        reviewer_id="usr_art_director",
        acknowledge_license_warning=False,
        correlation_id="corr_review",
        causation_id="cmd_approve",
    )
    service.review_variant(
        concept.concept_id,
        1,
        rejected_variant.variant_id,
        ReviewAction.REJECT,
        rationale="保留为被拒绝方案，避免重复探索。",
        reviewer_id="usr_art_director",
        acknowledge_license_warning=False,
        correlation_id="corr_review",
        causation_id="cmd_reject",
    )
    comparison = service.compare_variants(
        concept.concept_id,
        1,
        [approved_variant.variant_id, rejected_variant.variant_id],
    )
    assert [entry.status.value for entry in comparison.entries] == [
        "approved",
        "rejected",
    ]
    record = service.repository.get(concept.concept_id)
    assert len(record.decisions) == 2
    assert rejected_variant.variant_id in record.variants
    assert service.get_concept(concept.concept_id).status.value == "approved"


def test_license_warning_requires_explicit_acknowledgement(
    service, concept, imported_reference_payload, command_fields
):
    variant, _ = _add_two_view_variant(
        service,
        concept,
        imported_reference_payload,
        command_fields,
        title="许可待确认",
        permission="warning",
    )
    with pytest.raises(ReviewGateError) as error:
        service.review_variant(
            concept.concept_id,
            1,
            variant.variant_id,
            ReviewAction.APPROVE,
            rationale="视觉方案通过。",
            reviewer_id="usr_art_director",
            acknowledge_license_warning=False,
            correlation_id="corr_license",
            causation_id="cmd_license",
        )
    assert error.value.code == "LICENSE_WARNING_ACKNOWLEDGEMENT_REQUIRED"

    decision = service.review_variant(
        concept.concept_id,
        1,
        variant.variant_id,
        ReviewAction.APPROVE,
        rationale="已核对使用条件并记录风险。",
        reviewer_id="usr_art_director",
        acknowledge_license_warning=True,
        correlation_id="corr_license",
        causation_id="cmd_license_ack",
    )
    assert decision.acknowledged_license_warning is True
