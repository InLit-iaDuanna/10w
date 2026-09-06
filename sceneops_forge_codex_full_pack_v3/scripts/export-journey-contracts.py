"""Export planning journey contracts without starting tools or generating content."""
import json
from pathlib import Path
from fastapi import FastAPI
from sceneops_design_ai import create_journey_router

app = FastAPI(title='SceneOps Planning Journey')
app.include_router(create_journey_router(None))
target = Path(__file__).resolve().parents[1] / 'modules/design-room/contracts/journey.openapi.json'
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
