"""Schema generation only. No database, provider request, run or external process."""
import json
from pathlib import Path
from fastapi import FastAPI
from sceneops_ai_pipeline import create_router

app = FastAPI(title="SceneOps AI Harness", version="5.0")
app.include_router(create_router(None))
target = Path(__file__).resolve().parents[1] / "contracts/harness.openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n")
