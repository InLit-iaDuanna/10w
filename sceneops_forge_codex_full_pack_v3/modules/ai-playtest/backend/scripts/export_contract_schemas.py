from __future__ import annotations

import json
from pathlib import Path

from adapters.fixture_schema import DeterministicRuntimeFixture
from ai_playtest.events import EVENT_MODELS
from ai_playtest.schemas import SourceCatalog, TestCase


def write_schema(model: object, output_path: Path) -> None:
    content = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)
    output_path.write_text(content + "\n", encoding="utf-8")


def export(module_root: Path) -> None:
    event_directory = module_root / "contracts" / "events"
    manifest_directory = module_root / "contracts" / "manifests"
    event_directory.mkdir(parents=True, exist_ok=True)
    manifest_directory.mkdir(parents=True, exist_ok=True)
    for event_name, model in EVENT_MODELS.items():
        filename = event_name.replace(".", "-") + ".v1.schema.json"
        write_schema(model, event_directory / filename)
    write_schema(TestCase, manifest_directory / "test-case.v1.schema.json")
    write_schema(
        SourceCatalog,
        manifest_directory / "source-catalog.v1.schema.json",
    )
    write_schema(
        DeterministicRuntimeFixture,
        manifest_directory / "deterministic-runtime-fixture.v1.schema.json",
    )


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[2])
