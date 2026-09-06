"""Export environment-scene contracts without invoking AI or opening a server."""
import json
from pathlib import Path

from fastapi import FastAPI
from world_composer import create_environment_scene_router
from asset_library import create_project_catalog_router


ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "modules/world-composer/contracts/environment.openapi.json"
app = FastAPI(title="SceneOps Environment Scenes", version="0.1.0")
app.include_router(create_environment_scene_router(object()))
app.include_router(create_project_catalog_router(object()))
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
