from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from concept_lab.adapters import FixtureGenerationAdapter
from concept_lab.schemas import ConceptCreateInput, ExecutionMode
from concept_lab.service import ConceptLabService


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
MODULE_ROOT = Path(__file__).resolve().parents[4]


class SequentialIds:
    def __init__(self) -> None:
        self.counts = {}

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        return f"{prefix}_test_{self.counts[prefix]:03d}"


@pytest.fixture
def fixed_now():
    return datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def id_factory():
    return SequentialIds()


@pytest.fixture
def hero_request():
    return ConceptCreateInput.model_validate(
        json.loads((FIXTURE_DIR / "hero-key-concept.json").read_text(encoding="utf-8"))
    )


@pytest.fixture
def service(id_factory, fixed_now):
    adapters = [
        FixtureGenerationAdapter(
            FIXTURE_DIR / "generation-mock.json", ExecutionMode.MOCK
        ),
        FixtureGenerationAdapter(
            FIXTURE_DIR / "generation-cached.json", ExecutionMode.CACHED
        ),
    ]
    return ConceptLabService(
        adapters=adapters,
        id_factory=id_factory,
        clock=lambda: fixed_now,
    )


@pytest.fixture
def command_fields():
    return {
        "actor_id": "usr_designer",
        "correlation_id": "corr_test",
        "causation_id": "cmd_test",
    }


@pytest.fixture
def concept(service, hero_request, command_fields):
    return service.create_concept(hero_request, **command_fields)


@pytest.fixture
def imported_reference_payload():
    path = MODULE_ROOT / "contracts" / "examples" / "imported-key-reference.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def complete_style_evidence(reference_id: str):
    return [
        {
            "criterion": "warm hand-forged brass",
            "criterion_kind": "style_constraint",
            "observed": "Warm brass and hand-worked edges are visible.",
            "verdict": "match",
            "evidence_reference_id": reference_id,
            "confidence": 0.91,
            "rationale": "Reviewer evidence, not an objective style measurement.",
        },
        {
            "criterion": "readable silhouette at gameplay distance",
            "criterion_kind": "style_constraint",
            "observed": "The broad bow remains identifiable in the reduced preview.",
            "verdict": "match",
            "evidence_reference_id": reference_id,
            "confidence": 0.84,
            "rationale": "Final readability still requires an in-engine check.",
        },
        {
            "criterion": "modern electronic key fob",
            "criterion_kind": "forbidden_element",
            "observed": "No electronic fob is visible.",
            "verdict": "match",
            "evidence_reference_id": reference_id,
            "confidence": 0.96,
            "rationale": "The prohibited element is absent from the supplied views.",
        },
    ]
