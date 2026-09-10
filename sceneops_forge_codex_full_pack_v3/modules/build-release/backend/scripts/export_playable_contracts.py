"""Generate the local export OpenAPI contract from its public router."""
import json
from pathlib import Path
from fastapi import FastAPI
from build_release import create_export_router

app = FastAPI(title='SceneOps Playable Export API', version='1.0.0')
app.include_router(create_export_router(None))
output = Path(__file__).resolve().parents[2] / 'contracts/openapi/playable-export.openapi.json'
output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
