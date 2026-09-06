"""Export public DTOs without creating the application, database, or domain services."""
import json
from pathlib import Path
from fastapi import FastAPI
from sceneops_project_workspace import create_workspace_router, create_folder_router
root = Path(__file__).resolve().parents[1]
app = FastAPI()
app.include_router(create_workspace_router(None))  # Schema only; no request handlers executed.
app.include_router(create_folder_router(None))
target = root / 'packages/workspace-client/contracts/workspace.openapi.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
