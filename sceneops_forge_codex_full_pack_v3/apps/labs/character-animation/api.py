"""Local composition only; all routes and behavior belong to the module."""
from fastapi import FastAPI
from sceneops_character_animation import backend_module_contribution

app = FastAPI(title="角色与动画独立工作台")
app.include_router(backend_module_contribution.router)
