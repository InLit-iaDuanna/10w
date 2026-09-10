"""Explicit composition of public domain interfaces; no standalone lab apps."""
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, HTTPException, Request
from sceneops_character_animation import CharacterAnimationService, SqliteVersionRepository, create_router as character_router
from sceneops_production_planner import create_workspace_router as planning_router
from asset_factory import ConceptAssetLab, create_lab_router as asset_router
from render_ops import RenderLabService, create_render_lab_router
from build_release import UnityBuildWorkbenchService, create_workbench_router as build_router
from version_collaboration import create_workspace_router as review_router, create_tree_router, TreeProgress
from ui_studio import create_lab_router as ui_router
from audio_studio import create_lab_router as audio_router
from vfx_shader import create_lab_router as vfx_router
from world_composer import workbench_router as world_router
from logic_studio import workbench_router as logic_router
from integration_center import create_empty_workbench, create_demo_workbench, create_workbench_router as ops_router
from observability import create_router as observability_router

from .scoped_routes import ProjectModule, ProjectRouters


def compose_domains(app, repository, data_dir: Path):
    registry = ProjectRouters(repository)
    schema_storage = TemporaryDirectory(prefix="sceneops-api-schema-")

    def database(project_id):
        return Path(schema_storage.name) / "contracts.sqlite3" if project_id == "schema_only" else repository.path

    def project_directory(project_id):
        # IDs only come from the validated workspace repository, never arbitrary paths.
        path = Path(schema_storage.name) if project_id == "schema_only" else data_dir / "projects" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def saved_sample(project_id, module_id):
        if project_id == "schema_only":
            return None
        return repository.get_document(project_id, module_id).sample_id

    def assets(project_id):
        lab = ConceptAssetLab(project_directory(project_id) / "mock-assets", seed=False, project_id=project_id)
        sample = saved_sample(project_id, "concept-assets")
        if sample:
            lab.import_sample(sample)
        return ProjectModule(asset_router(lab), lab.import_sample)

    def renders(project_id):
        return ProjectModule(create_render_lab_router(service_factory=lambda: RenderLabService(seed=False, project_id=project_id)))

    def builds(project_id):
        service = UnityBuildWorkbenchService(project_directory(project_id) / "build-proposals.sqlite3",
            seed=False, project_id=project_id)
        sample = saved_sample(project_id, "unity-build")
        if sample:
            service.import_sample(sample)
        return ProjectModule(build_router(service), service.import_sample)

    def reviews(project_id):
        database = project_directory(project_id) / "reviews.sqlite3"
        def progress():
            journey = getattr(app.state, "planning_journey", None)
            if journey is None:
                return None
            state = journey.get(project_id)
            card_titles = {card.id: card.title for card in state.cards}
            return TreeProgress(stage=state.stage, confirmed_versions=len(state.versions),
                planned_cards=len(state.cards), card_branches=len(state.card_branches),
                milestones={version.commit: f"策划 v{version.number}" for version in state.git_versions},
                branch_labels={branch.branch: card_titles.get(branch.card_id, branch.card_id)
                    for branch in state.card_branches},
                title=state.outline.title if state.outline else None,
                cards=tuple(dict(card_id=card.id, title=card.title, description=card.description,
                    acceptance=card.acceptance, dependencies=tuple(card.dependencies),
                    branches=tuple(branch.branch for branch in state.card_branches if branch.card_id == card.id))
                    for card in state.cards),
                versions=tuple(dict(number=version.number, title=version.outline.title,
                    confirmed_at=version.confirmed_at,
                    commit=next((item.commit for item in state.git_versions if item.number == version.number), None))
                    for version in state.versions))

        def compose_review(sample):
            router = review_router(database, project_id, sample)
            router.include_router(create_tree_router(project_id,
                lambda: Path(repository.get_folder_project(project_id).root_path), progress))
            return router
        result = ProjectModule(compose_review(saved_sample(project_id, "version-review")))
        def load(sample):
            result.router = compose_review(sample)
        result.import_sample = load
        return result

    def audiovisual(project_id):
        router = APIRouter()
        for factory in (ui_router, audio_router, vfx_router):
            router.include_router(factory())
        return ProjectModule(router)

    def world(project_id):
        router = APIRouter()
        router.include_router(world_router, prefix="/api")
        router.include_router(logic_router, prefix="/api")
        return ProjectModule(router)

    def operations(project_id):
        title = "Schema" if project_id == "schema_only" else repository.get_project(project_id).name
        sample = saved_sample(project_id, "integration-ops")
        workbench = create_demo_workbench(project_id, sample) if sample else create_empty_workbench(project_id, title)
        result = ProjectModule(APIRouter())

        def compose(workbench):
            def require_permission(permission):
                def check(request: Request):
                    if permission not in {"integration:read", "observability:read", "observability:export"}:
                        raise HTTPException(403, "未授权外部事件写入或恢复操作。")
                return check

            class Access:
                def authorize_project(self, permission, requested_project):
                    if requested_project != project_id:
                        raise HTTPException(404, "当前项目没有此数据。")

                def authorize_producer(self, *args):
                    raise HTTPException(403, "本地工作台不接受外部事件生产者。")

            router = APIRouter()
            router.include_router(ops_router(workbench, require_permission))
            router.include_router(observability_router(workbench.logs, require_permission, Access(),
                health_provider=lambda project: []))
            return router

        result.router = compose(workbench)
        result.import_sample = lambda sample: setattr(result, "router", compose(create_demo_workbench(project_id, sample)))
        return result

    factories = {
        "project-planning": lambda project: ProjectModule(planning_router(database(project), project)),
        "concept-assets": assets,
        "character-animation": lambda project: ProjectModule(character_router(CharacterAnimationService(
            repository=SqliteVersionRepository(database(project), project)))),
        "world-logic": world,
        "ui-audio-vfx": audiovisual,
        "render-ops": renders,
        "unity-build": builds,
        "version-review": reviews,
        "integration-ops": operations,
    }
    for module_id, factory in factories.items():
        template = factory("schema_only")
        app.include_router(registry.register(module_id, factory, template.router))
    schema_storage.cleanup()
    return registry
