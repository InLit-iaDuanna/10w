"""Generate OpenAPI without starting services or invoking CodeBuddy."""
import json
import tempfile
from pathlib import Path
from fastapi import FastAPI
from conversation_home import create_ai_router

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='sceneops-ai-schema-') as directory:
        app = FastAPI()
        app.include_router(create_ai_router(Path(directory) / 'schema.sqlite3'))
        destination = Path(__file__).resolve().parents[1] / 'contracts/unified-ai.openapi.json'
        destination.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
