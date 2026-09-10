"""Generate native Lookdev OpenAPI without starting providers or a server."""
import json
from pathlib import Path
from fastapi import FastAPI
from vfx_shader import create_lookdev_router, LookdevDocument

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='SceneOps Lookdev', version='1.0.0')
app.include_router(create_lookdev_router(object()))
target = ROOT / 'modules/vfx-shader/contracts/lookdev.openapi.json'
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')

(ROOT / 'modules/vfx-shader/contracts/lookdev-document.schema.json').write_text(
    json.dumps(LookdevDocument.model_json_schema(), ensure_ascii=False, indent=2) + '\n')
