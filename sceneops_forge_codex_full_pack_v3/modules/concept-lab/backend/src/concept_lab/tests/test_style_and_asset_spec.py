from __future__ import annotations

from copy import deepcopy

import pytest

from concept_lab.errors import ReviewGateError
from concept_lab.schemas import (
    ImportedReferenceInput,
    ReviewAction,
    StyleEvidenceInput,
)
from concept_lab.tests.conftest import complete_style_evidence


def _approved_imported_variant(
    service, concept, payload, command_fields, *, approve=True
):
    references = []
    for view, digit in [("front", "d"), ("three_quarter", "e")]:
        value = deepcopy(payload)
        value["view"] = view
        value["provenance"]["artifact_id"] = f"art_imported_{view}"
        value["provenance"]["checksum_sha256"] = digit * 64
        references.append(
            service.import_reference(
                concept.concept_id,
                1,
                ImportedReferenceInput.model_validate(value),
            )
        )
    variant = service.create_imported_variant(
        concept.concept_id,
        1,
        title="项目自有概念图",
        reference_ids=[value.reference_id for value in references],
        **command_fields,
    )
    evidence = [
        StyleEvidenceInput.model_validate(value)
        for value in complete_style_evidence(references[0].reference_id)
    ]
    check = service.add_style_check(
        concept.concept_id,
        1,
        variant.variant_id,
        evidence,
        created_by="usr_art_director",
    )
    if approve:
        service.review_variant(
            concept.concept_id,
            1,
            variant.variant_id,
            ReviewAction.APPROVE,
            rationale="导入方案满足当前资产简报要求。",
            reviewer_id="usr_art_director",
            acknowledge_license_warning=False,
            correlation_id="corr_review",
            causation_id="cmd_review",
        )
    return variant, check


def test_style_check_returns_evidence_confidence_and_subjective_label(
    service, concept, imported_reference_payload, command_fields
):
    variant, check = _approved_imported_variant(
        service, concept, imported_reference_payload, command_fields
    )
    assert variant.variant_id == check.variant_id
    assert check.assessment.value == "consistent"
    assert check.confidence == pytest.approx(0.9033, abs=0.0001)
    assert check.evidence_coverage == 1
    assert check.unevaluated_criteria == []
    assert check.is_subjective is True
    assert check.method == "declared-evidence-review"


def test_partial_mismatch_evidence_is_explainable_not_absolute(
    service, concept, imported_reference_payload, command_fields
):
    variant, _ = _approved_imported_variant(
        service,
        concept,
        imported_reference_payload,
        command_fields,
        approve=False,
    )
    reference_id = service.repository.get(concept.concept_id).variants[
        variant.variant_id
    ].reference_ids[0]
    check = service.add_style_check(
        concept.concept_id,
        1,
        variant.variant_id,
        [
            StyleEvidenceInput(
                criterion="warm hand-forged brass",
                criterion_kind="style_constraint",
                observed="The supplied image appears cool and polished.",
                verdict="mismatch",
                evidence_reference_id=reference_id,
                confidence=0.7,
                rationale="This is a reviewer observation from one view.",
            )
        ],
        created_by="usr_reviewer",
    )
    assert check.assessment.value == "inconsistent"
    assert check.evidence_coverage == pytest.approx(1 / 3, abs=0.0001)
    assert len(check.unevaluated_criteria) == 2
    assert check.is_subjective is True


def test_approved_imported_concept_compiles_asset_spec_draft_without_generator(
    service, concept, imported_reference_payload, command_fields
):
    variant, _ = _approved_imported_variant(
        service, concept, imported_reference_payload, command_fields
    )
    draft = service.compile_asset_spec_draft(
        concept.concept_id,
        1,
        variant.variant_id,
        **command_fields,
    )
    assert draft.status == "draft"
    assert draft.source_concept_id == concept.concept_id
    assert draft.approved_variant_id == variant.variant_id
    assert draft.project_id == "prj_remember_home"
    assert draft.dimensions.unit == "m"
    assert draft.platform_budget.max_triangles == 2500
    assert draft.producing_module == "concept-lab"
    assert draft.execution_mode.value == "mock"
    workspace = service.get_review_workspace(concept.concept_id, 1)
    assert workspace.concept.status.value == "approved"
    assert [value.variant_id for value in workspace.variants] == [variant.variant_id]
    assert [value.asset_spec_draft_id for value in workspace.asset_spec_drafts] == [
        draft.asset_spec_draft_id
    ]


def test_unapproved_variant_cannot_compile_asset_spec(
    service, concept, imported_reference_payload, command_fields
):
    variant, _ = _approved_imported_variant(
        service,
        concept,
        imported_reference_payload,
        command_fields,
        approve=False,
    )
    with pytest.raises(ReviewGateError) as error:
        service.compile_asset_spec_draft(
            concept.concept_id,
            1,
            variant.variant_id,
            **command_fields,
        )
    assert error.value.code == "APPROVED_CONCEPT_REQUIRED"
