"""Generate task API contracts without providers, databases or external sessions."""
import json
from pathlib import Path
from fastapi import FastAPI
from sceneops_ai_agents import create_agent_task_router, create_production_router

app = FastAPI(title="SceneOps Agent Tasks", version="0.5.0")
app.include_router(create_agent_task_router(None))
app.include_router(create_production_router(None))
target = Path(__file__).resolve().parents[1] / "modules/ai-agent-runtime/contracts/agent.openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n")
