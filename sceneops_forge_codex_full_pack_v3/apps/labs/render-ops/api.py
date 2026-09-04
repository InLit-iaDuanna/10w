"""Composition only: mount the Render Ops module's isolated lab router."""

from fastapi import FastAPI
from render_ops import create_render_lab_router

app = FastAPI(title="Render Ops Local Workbench", version="0.1.0")
app.include_router(create_render_lab_router())
