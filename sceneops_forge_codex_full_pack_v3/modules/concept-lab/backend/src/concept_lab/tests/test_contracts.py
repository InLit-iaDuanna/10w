from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import yaml

import concept_lab
from concept_lab.schemas import ImportedReferenceInput, StyleEvidenceInput


MODULE_ROOT = Path(__file__).resolve().parents[4]


def test_module_manifest_declares_public_surface_and_dependencies():
    manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["id"] == "concept-lab"
    assert manifest["feature_flag"] == "concept_lab"
    assert manifest["entrypoints"] == {
        "frontend": "./frontend/src/index.ts",
        "backend": "concept_lab",
    }
    assert set(manifest["contributes"]["editors"]) == {
        "concept.moodboard",
        "concept.style_bible",
    }
    assert "image-generation" in manifest["requires"]["optional_integrations"]
    assert len(manifest["contributes"]["events"]) == 4


def test_backend_public_entrypoint_is_explicit():
    assert set(concept_lab.__all__) == {
        "AdapterHealth",
        "AssetSpecDraft",
        "ConceptChangeSet",
        "ConceptGenerationAdapter",
        "ConceptLabError",
        "ConceptLabService",
        "ConceptReference",
        "ConceptRepository",
        "ConceptSpec",
        "ConceptVariant",
        "ExecutionMode",
        "FixtureGenerationAdapter",
        "GenerationCapabilities",
        "GenerationOutput",
        "GenerationPlan",
        "GenerationRequest",
        "InMemoryConceptRepository",
        "StyleCheck",
        "concept_lab_error_handler",
        "create_router",
        "module_contribution",
    }


def test_imported_reference_example_matches_pydantic_contract():
    value = json.loads(
        (MODULE_ROOT / "contracts/examples/imported-key-reference.v1.json").read_text(
            encoding="utf-8"
        )
    )
    parsed = ImportedReferenceInput.model_validate(value)
    assert parsed.source.kind.value == "imported"
    assert parsed.provenance.execution_mode.value == "mock"

    style_values = json.loads(
        (MODULE_ROOT / "contracts/examples/style-evidence.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert len([StyleEvidenceInput.model_validate(item) for item in style_values]) == 3


def test_generated_contracts_are_current():
    result = subprocess.run(
        [sys.executable, str(MODULE_ROOT / "scripts/export_contracts.py"), "--check"],
        cwd=MODULE_ROOT.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_emitted_event_validates_against_versioned_schema(
    service, hero_request, command_fields
):
    service.create_concept(hero_request, **command_fields)
    event = service.events.events[0].model_dump(mode="json")
    schema = json.loads(
        (
            MODULE_ROOT
            / "contracts/events/concept.version.created.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(event, schema)


def test_module_has_no_cross_module_internal_imports():
    source_root = MODULE_ROOT / "backend/src/concept_lab"
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.rglob("*.py")
        if "tests" not in path.parts
    )
    assert "modules." not in sources
    assert "asset_factory." not in sources
    assert "design_room." not in sources
