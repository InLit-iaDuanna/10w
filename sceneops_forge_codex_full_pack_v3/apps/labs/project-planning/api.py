from sceneops_design_ai import create_ai_router
from sceneops_production_planner import create_planning_lab_app
app = create_planning_lab_app()
app.include_router(create_ai_router())
