from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Type


MODULE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = MODULE_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from concept_lab.errors import ConceptLabError  # noqa: E402
from concept_lab.router import concept_lab_error_handler, create_router  # noqa: E402
from concept_lab.event_schemas import (  # noqa: E402
    AssetSpecDraftCompiledEvent,
    ConceptVariantRecordedEvent,
    ConceptVariantReviewedEvent,
    ConceptVersionCreatedEvent,
)
from concept_lab.generation_schemas import GenerationRequest  # noqa: E402
from concept_lab.schemas import (  # noqa: E402
    AssetSpecDraft,
    ConceptSpec,
)
from concept_lab.service import ConceptLabService  # noqa: E402


SCHEMAS: Dict[Path, Type[BaseModel]] = {
    Path("contracts/manifests/concept-spec.v1.schema.json"): ConceptSpec,
    Path("contracts/manifests/generation-request.v1.schema.json"): GenerationRequest,
    Path("contracts/manifests/asset-spec-draft.v1.schema.json"): AssetSpecDraft,
    Path("contracts/events/concept.version.created.v1.schema.json"): ConceptVersionCreatedEvent,
    Path("contracts/events/concept.variant.recorded.v1.schema.json"): ConceptVariantRecordedEvent,
    Path("contracts/events/concept.variant.reviewed.v1.schema.json"): ConceptVariantReviewedEvent,
    Path(
        "contracts/events/concept.asset_spec_draft.compiled.v1.schema.json"
    ): AssetSpecDraftCompiledEvent,
}


def serialize(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def expected_outputs() -> Dict[Path, str]:
    outputs = {}
    for relative, model in SCHEMAS.items():
        schema = model.model_json_schema()
        if relative.parent.name == "events":
            schema["x-event-type"] = schema["properties"]["event_type"]["const"]
            schema["x-event-version"] = schema["properties"]["event_version"]["const"]
        outputs[relative] = serialize(schema)
    app = FastAPI(title="SceneOps Concept Lab API", version="0.1.0")
    app.add_exception_handler(ConceptLabError, concept_lab_error_handler)
    app.include_router(create_router(ConceptLabService()))
    outputs[Path("contracts/openapi/concept-lab.openapi.json")] = serialize(app.openapi())
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for relative, content in expected_outputs().items():
        destination = MODULE_ROOT / relative
        if args.check:
            if not destination.exists() or destination.read_text(encoding="utf-8") != content:
                stale.append(str(relative))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    if stale:
        print("stale generated contracts:")
        for path in stale:
            print(f"- {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
