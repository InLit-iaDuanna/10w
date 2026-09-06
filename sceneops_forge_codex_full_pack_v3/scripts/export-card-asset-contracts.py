"""Export card-asset API contracts without starting Blender, AI, or a server."""
import json
from pathlib import Path

from fastapi import FastAPI
from asset_factory import create_card_asset_router


ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "modules/asset-factory/contracts/card-assets.openapi.json"
app = FastAPI(title="SceneOps Card Assets", version="0.1.0")
app.include_router(create_card_asset_router(object()))
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
