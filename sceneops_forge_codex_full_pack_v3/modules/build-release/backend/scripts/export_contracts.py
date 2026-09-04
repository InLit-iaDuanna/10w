"""Generate module-owned JSON Schema and OpenAPI contracts from Pydantic."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from build_release.events import EVENT_PAYLOAD_MODELS
from build_release.models_build import BuildManifest
from build_release.router import create_router


MODULE_ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    write_json(
        MODULE_ROOT / "contracts/manifests/build-manifest.schema.json",
        BuildManifest.model_json_schema(),
    )
    for event_name, model in EVENT_PAYLOAD_MODELS.items():
        filename = event_name.replace("@", "-v") + ".schema.json"
        write_json(
            MODULE_ROOT / "contracts/events" / filename,
            model.model_json_schema(),
        )
    app = FastAPI(title="SceneOps Forge Build Release API", version="0.1.0")
    app.include_router(create_router())
    write_json(
        MODULE_ROOT / "contracts/openapi/build-release.openapi.json",
        app.openapi(),
    )


if __name__ == "__main__":
    main()
