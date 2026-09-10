"""Export from public Pydantic routes without constructing a database or provider."""
import json
from pathlib import Path
from fastapi import FastAPI
from sceneops_ai_distiller import create_experience_router

root = Path(__file__).resolve().parents[1]
app = FastAPI(title='SceneOps Experience', version='0.1.0')
app.include_router(create_experience_router(None))
target = root / 'modules/ai-run-distiller/contracts/experience.openapi.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
