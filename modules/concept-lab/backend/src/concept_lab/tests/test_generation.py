from __future__ import annotations

from pathlib import Path

from concept_lab.adapters import FixtureGenerationAdapter
from concept_lab.generation_schemas import GenerationRequest
from concept_lab.schemas import ExecutionMode


def _request(concept, **overrides):
    values = {
        "concept_id": concept.concept_id,
        "concept_version": 1,
        "title": "钥匙生成方案",
        "requested_views": ["front", "three_quarter"],
        "prompt": "Aged hand-forged brass house key",
        "negative_prompt": "electronic fob",
        "seed": 240906,
        "workflow_version": "concept-multiview-fixture@1",
        "execution_mode": "mock",
        "adapter_id": "concept-fixture-mock",
        "model": "fixture-key-v1",
        "fixture_key": "hero-key-v1",
    }
    values.update(overrides)
    return GenerationRequest.model_validate(values)


def test_mock_generation_is_deterministic_and_preserves_ai_metadata(
    service, concept, command_fields
):
    first = service.generate_variant(_request(concept), **command_fields)
    assert first.run.state.value == "succeeded"
    assert first.run.execution_mode == ExecutionMode.MOCK
    assert first.variant is not None
    assert first.variant.execution_mode == ExecutionMode.MOCK
    assert first.variant.generation.seed == 240906
    assert first.variant.generation.prompt.startswith("Aged hand-forged")
    assert service.get_concept(concept.concept_id).status.value == "in_review"
    refs = service.repository.get(concept.concept_id).references
    assert {refs[value].provenance.execution_mode for value in first.variant.reference_ids} == {
        ExecutionMode.MOCK
    }


def test_cached_generation_remains_cached_and_carries_license_warning(
    service, concept, command_fields
):
    request = _request(
        concept,
        execution_mode="cached",
        adapter_id="concept-fixture-cached",
        model="recorded-concept-model-v2",
        workflow_version="concept-turnaround@2",
        fixture_key="hero-key-cached-v1",
    )
    outcome = service.generate_variant(request, **command_fields)
    assert outcome.run.state.value == "succeeded"
    assert outcome.variant.execution_mode == ExecutionMode.CACHED
    record = service.repository.get(concept.concept_id)
    statuses = {
        record.references[value].source.permission_status.value
        for value in outcome.variant.reference_ids
    }
    assert statuses == {"warning"}


def test_live_generation_without_adapter_is_visibly_blocked(
    service, concept, command_fields
):
    request = _request(
        concept,
        execution_mode="live",
        adapter_id="provider-live",
        model="provider-model",
        fixture_key=None,
    )
    outcome = service.generate_variant(request, **command_fields)
    assert outcome.variant is None
    assert outcome.run.state.value == "blocked"
    assert outcome.run.execution_mode == ExecutionMode.LIVE
    assert "not configured" in outcome.run.reason


def test_missing_model_and_unsupported_turnaround_are_blocked(
    service, concept, command_fields
):
    missing_model = service.generate_variant(
        _request(concept, model="missing-model"), **command_fields
    )
    assert missing_model.run.state.value == "blocked"
    assert "not supported" in missing_model.run.reason

    no_turnaround = service.generate_variant(
        _request(concept, requested_views=["turnaround"]), **command_fields
    )
    assert no_turnaround.run.state.value == "blocked"
    assert "unsupported" in no_turnaround.run.reason


def test_missing_fixture_is_failed_and_preserves_reason(service, concept, command_fields):
    outcome = service.generate_variant(
        _request(concept, fixture_key="does-not-exist"), **command_fields
    )
    assert outcome.run.state.value == "failed"
    assert outcome.variant is None
    assert "fixture" in outcome.run.reason.lower()


def test_fixture_adapter_contract_has_health_dry_run_execute_and_cancel(concept):
    fixture = Path(__file__).resolve().parents[1] / "fixtures/generation-mock.json"
    adapter = FixtureGenerationAdapter(fixture, ExecutionMode.MOCK)
    request = _request(concept)
    assert adapter.health_check().available is True
    assert adapter.capabilities().supports_cancellation is False
    plan = adapter.dry_run(request)
    assert plan.approval_required is True
    assert plan.execution_mode == ExecutionMode.MOCK
    assert adapter.execute(request).execution_mode == ExecutionMode.MOCK
    assert adapter.cancel("run_already_finished") is False
