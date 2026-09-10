"""Export shipped asset DTOs without reading assets or creating project records."""
import json
from pathlib import Path
from fastapi import FastAPI
from asset_library import BuiltinAssetCatalog, create_builtin_asset_router

app = FastAPI(title='SceneOps Builtin Assets')
app.include_router(create_builtin_asset_router(BuiltinAssetCatalog()))
target = Path(__file__).resolve().parents[1] / 'modules/asset-library/contracts/builtin-assets.openapi.json'
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
