"""D3 scripted-model acceptance for project-scoped editable Demo production."""
import asyncio
import json
import stat
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from asset_library import ProjectAssetCatalogService, SqliteProjectAssetRepository
from sceneops_ai_agents import AgentTaskService, AuthorizeAgentTask, PrepareAgentTask
from sceneops_ai_agents.task_models import ContinueProjectDemoRequest
from sceneops_harness import HarnessError
from sceneops_project_workspace import SqliteWorkspaceRepository
from world_composer import EnvironmentSceneService


def action(action_id, capability_id, **inputs):
    return {"action_id": action_id, "capability_id": capability_id,
            "rationale": f"D3 scripted decision: {capability_id}", "inputs": inputs}


class ScriptedDemoProvider:
    def __init__(self, database, kind):
        self.database_path = database
        self.kind = kind
        self.stage = 0
        self.follow_stage = 0
        self.requests = []
        self.assets = None
        self.scenes = None
        self.root = None

    def settings(self):
        return SimpleNamespace(provider="fixture", model="d3-scripted-model")

    async def generate(self, prompt, **kwargs):
        data = json.loads(prompt.split("本轮运行时输入：\n", 1)[1])
        self.requests.append({"data": data, **kwargs})
        if self.kind == "key-door":
            value = self.key_door_action()
        elif data["goal"].startswith("把开关顺序改为"):
            value = self.switch_followup_action()
        else:
            value = self.switch_initial_action()
        return SimpleNamespace(structured=value, text=json.dumps(value), provider="fixture",
            model="d3-scripted-model", latency_ms=1, usage={"total_tokens": 17})

    def key_door_action(self):
        assets = self.assets.list(self.project_id)
        scene = self.scenes.get(self.project_id)
        steps = [
            lambda: action("inspect-workspace", "code.workspace.inspect"),
            lambda: action("read-assets-0", "project.assets.list"),
            lambda: action("read-scene-0", "environment.scene.read"),
            lambda: action("create-door", "project.asset.door.create",
                source_asset_id="d3-key-door", title="钥匙门",
                recipe={"width_m": 1.4, "height_m": 2.3, "thickness_m": .18,
                        "material": {"color_hex": "#70513A", "roughness": .7,
                                     "metalness": .08}}),
            lambda: action("read-assets-1", "project.assets.list"),
            lambda: action("create-door-again", "project.asset.door.create",
                source_asset_id="d3-key-door", title="钥匙门",
                recipe={"width_m": 1.4, "height_m": 2.3, "thickness_m": .18,
                        "material": {"color_hex": "#70513A", "roughness": .7,
                                     "metalness": .08}}),
            lambda: action("read-scene-1", "environment.scene.read"),
            lambda: action("place-exit", "environment.object.place",
                expected_version=scene.version, asset_id=assets[0].id,
                asset_version=assets[0].current_version, position_m=[-2, 0, -4]),
            lambda: action("read-scene-2", "environment.scene.read"),
            lambda: action("place-scenery", "environment.object.place",
                expected_version=scene.version, asset_id=assets[0].id,
                asset_version=assets[0].current_version, position_m=[2, 0, -4]),
            lambda: action("read-scene-3", "environment.scene.read"),
            lambda: action("configure-exit", "environment.key_door.configure",
                object_id=scene.objects[0].id, expected_version=scene.version,
                required_key_asset_id=assets[0].id, interaction_distance_m=1.5,
                open_angle_deg=90),
            lambda: action("materialize-key-door", "code.demo_content.materialize"),
            lambda: action("prepare-key-door", "code.dependencies.prepare"),
            lambda: action("check-key-door", "code.project.check"),
            lambda: action("build-key-door", "code.project.build"),
            lambda: action("preview-key-door", "code.preview.start"),
            lambda: action("observe-key-door", "code.browser.observe"),
            lambda: action("finish-key-door", "agent.finish",
                summary="钥匙门初版已按真实内容源构建。"),
        ]
        selected = steps[self.stage]()
        self.stage += 1
        return selected

    @staticmethod
    def switch_source(order=("arrowleft", "arrowright")):
        values = ", ".join(repr(item) for item in order)
        return f"""export const switchParameters = {{ orderedKeys: [{values}] as const }}

export function installOrderedSwitchDemo(host: HTMLElement) {{
  let next = 0
  host.dataset.switchState = 'blocked'
  const prompt = document.querySelector<HTMLElement>('#prompt')
  addEventListener('keydown', event => {{
    const key = event.key.toLowerCase()
    if (!switchParameters.orderedKeys.includes(key as typeof switchParameters.orderedKeys[number])) return
    next = key === switchParameters.orderedKeys[next] ? next + 1 : 0
    if (next === switchParameters.orderedKeys.length) {{
      host.dataset.switchState = 'open'
      if (prompt) prompt.textContent = '开关顺序正确，出口已开启'
    }} else if (prompt) prompt.textContent = '按正确顺序启动两个开关'
  }})
}}
"""

    def switch_initial_action(self):
        main_path = self.root / "src/main.ts"
        module_path = self.root / "src/game/behaviors/OrderedSwitches.ts"
        main = main_path.read_text("utf-8")
        fixed = self.switch_source()
        broken = fixed + "\nBROKEN_SWITCH\n"
        integrated = main.replace("import { Game } from './game/Game'",
            "import { Game } from './game/Game'\nimport { installOrderedSwitchDemo } from './game/behaviors/OrderedSwitches'")
        integrated = integrated.replace("new Game(host).start()",
            "const game = new Game(host)\ninstallOrderedSwitchDemo(host)\ngame.start()")
        steps = [
            lambda: action("switch-inspect", "code.workspace.inspect"),
            lambda: action("switch-read-main", "code.file.read", path="src/main.ts"),
            lambda: action("switch-prepare", "code.dependencies.prepare"),
            lambda: action("switch-write-broken", "code.file.write",
                path="src/game/behaviors/OrderedSwitches.ts", expected_content=None,
                content=broken),
            lambda: action("switch-check-failure", "code.project.check"),
            lambda: action("switch-read-diagnostic-source", "code.file.read",
                path="src/game/behaviors/OrderedSwitches.ts"),
            lambda: action("switch-repair", "code.file.write",
                path="src/game/behaviors/OrderedSwitches.ts", expected_content=broken,
                content=fixed),
            lambda: action("switch-wire-runtime", "code.file.write", path="src/main.ts",
                expected_content=main, content=integrated),
            lambda: action("switch-materialize", "code.demo_content.materialize"),
            lambda: action("switch-check", "code.project.check"),
            lambda: action("switch-build", "code.project.build"),
            lambda: action("switch-preview", "code.preview.start"),
            lambda: action("switch-finish", "agent.finish",
                summary="顺序开关初版已修复并构建。"),
        ]
        selected = steps[self.stage]()
        self.stage += 1
        return selected

    def switch_followup_action(self):
        path = self.root / "src/game/behaviors/OrderedSwitches.ts"
        current = path.read_text("utf-8")
        updated = self.switch_source(("arrowright", "arrowleft"))
        steps = [
            lambda: action("follow-read-switch", "code.file.read",
                path="src/game/behaviors/OrderedSwitches.ts"),
            lambda: action("follow-update-switch", "code.file.write",
                path="src/game/behaviors/OrderedSwitches.ts", expected_content=current,
                content=updated),
            lambda: action("follow-materialize", "code.demo_content.materialize"),
            lambda: action("follow-check", "code.project.check"),
            lambda: action("follow-build", "code.project.build"),
            lambda: action("follow-preview", "code.preview.start"),
            lambda: action("follow-finish", "agent.finish",
                summary="同一 Demo 的开关顺序已更新。"),
        ]
        selected = steps[self.follow_stage]()
        self.follow_stage += 1
        return selected


@pytest.fixture
def d3_workspace():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        yield root


def make_pnpm(root):
    executable = root / "fixture-pnpm"
    executable.write_text(f'''#!{Path(sys.executable).resolve()}
import pathlib, sys, json
root=pathlib.Path.cwd()
if sys.argv[1]=='install':
 target=root/'node_modules/.bin';target.mkdir(parents=True,exist_ok=True);(target/'tsc').write_text('x');(target/'vite').write_text('x')
 manifest=json.loads((root/'package.json').read_text())
 for name in ('three','@types/three'):
  version=manifest.get('dependencies',{{}}).get(name) or manifest.get('devDependencies',{{}}).get(name)
  if version:
   target=root/'node_modules'/name;target.mkdir(parents=True,exist_ok=True);(target/'package.json').write_text(json.dumps({{'version':version}}))
elif sys.argv[1:3]==['exec','tsc']:
 broken=any('BROKEN_SWITCH' in path.read_text(errors='ignore') for path in (root/'src').rglob('*.ts'))
 print('src/game/behaviors/OrderedSwitches.ts:14:1 - error TS2304: Cannot find name BROKEN_SWITCH' if broken else 'fixture check')
 if broken: raise SystemExit(2)
elif sys.argv[1:3]==['exec','vite']:
 output=root/'dist';output.mkdir(exist_ok=True);(output/'index.html').write_text('<main>sceneops d3</main>')
else: raise SystemExit(64)
''', encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def make_service(root, kind):
    database = root / "state.sqlite3"
    workspace = SqliteWorkspaceRepository(database)
    project = workspace.create_folder_project(root, f"D3 {kind}")
    workspace.initialize_game_project(project.project_id, {
        "target_platform": "web", "engine": "threejs",
        "code_architecture": "object-component", "architecture_label": "对象／组件式",
        "selection_method": "manual", "rationale": "D3 acceptance", "tradeoffs": [],
        "ecs_library": None,
    }, 1, commit_baseline=False)
    direction_id = "direction_" + ("3" if kind == "key-door" else "4") * 32
    provider = ScriptedDemoProvider(database, kind)
    assets = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
    scenes = EnvironmentSceneService(database, workspace, assets, provider)
    provider.assets, provider.scenes = assets, scenes
    provider.project_id, provider.root = project.project_id, Path(project.root_path)
    service = AgentTaskService(database, workspace, root / "data", provider=provider,
        project_assets=assets, environment_scenes=scenes,
        project_demo_context=lambda project_id: {"direction_id": direction_id,
            "direction": {"core_experience": kind},
            "technical_plan": {"code_architecture": "object-component"}},
        pnpm_executable=str(make_pnpm(root)))
    request = PrepareAgentTask(project_id=project.project_id, goal=(
        "制作一扇需要钥匙的出口和一扇共享外观的装饰门" if kind == "key-door" else
        "制作按左、右顺序启动两个开关后开启出口的初版"),
        task_profile="project-demo-agent", execution_mode="typed-tools",
        allow_game_execution=True, allow_dependency_install=True, include_demo_assets=True,
        allow_browser_observation=kind == "key-door",
        alignment_id=direction_id)
    return service, provider, assets, scenes, project, request


async def settle(service):
    await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())), timeout=30)


def test_model_composes_key_door_without_implicit_fixture(d3_workspace):
    asyncio.run(_model_composes_key_door_without_implicit_fixture(d3_workspace))


async def _model_composes_key_door_without_implicit_fixture(d3_workspace):
    service, provider, assets, scenes, project, request = make_service(d3_workspace, "key-door")
    try:
        prepared = service.prepare(request)
        assert prepared.authorization_card.max_model_calls == 28
        assert "project.asset.door.create" in prepared.authorization_card.capability_ids
        assert assets.list(project.project_id) == []
        assert scenes.get(project.project_id).objects == []
        async def capture(runtime, url, screenshot, **kwargs):
            return {"status": "succeeded", "loaded": True, "screenshot_collected": False,
                    "diagnostics_status": "dom_only_game_diagnostics_missing",
                    "console_errors": [], "page_errors": [], "network_errors": []}
        with patch("sceneops_ai_agents.browser_observation.capture", capture):
            service.authorize(prepared.id, AuthorizeAgentTask(
                authorization_card_id=prepared.authorization_card.id, accept_unknown_cost=True))
            await settle(service)
        completed = service.get(prepared.id)
        scene = scenes.get(project.project_id)
        assert completed.status == "review_required", completed.reason
        assert completed.model_calls_used == 19
        repeated = next(item for item in completed.actions
                        if item.action.action_id == "create-door-again")
        assert repeated.state == "succeeded"
        assert repeated.effect_state == "NONE"
        assert repeated.result["evidence"]["outcome"] == "already_present"
        assert len(scene.objects) == 2
        assert scene.objects[0].behavior is not None
        assert scene.objects[1].behavior is None
        manifest = json.loads((Path(project.root_path) / ".sceneops/demo-content.json").read_text("utf-8"))
        assert len(manifest["objects"]) == 2
        assert manifest["objects"][1]["behavior"] is None
        assert "project_demo_fixture" not in completed.observations
        assert all("# SceneOps Demo Composer" in item["instructions"]
                   and "# SceneOps Editable Content" in item["instructions"]
                   for item in provider.requests)
        candidate = service.game_status(prepared.id).current_playable_candidate
        assert candidate.scene_version == scene.version
        assert candidate.source_version["content_action_ids"]
        assert service.game_status(prepared.id).observation.status == "succeeded"
    finally:
        await service.close()


def test_project_demo_agent_keeps_workspace_pairing_and_derived_sources_read_only(d3_workspace):
    asyncio.run(_project_demo_agent_keeps_workspace_pairing_and_derived_sources_read_only(
        d3_workspace))


async def _project_demo_agent_keeps_workspace_pairing_and_derived_sources_read_only(d3_workspace):
    service, _provider, _assets, _scenes, project, request = make_service(
        d3_workspace, "key-door")
    try:
        prepared = service.prepare(request)
        from sceneops_ai_agents.code_workspace import task_source_path

        with pytest.raises(HarnessError) as derived:
            task_source_path(prepared, "src/game/sceneops-demo-content.ts")
        assert derived.value.code == "CODE_PATH_DERIVED"
        assert task_source_path(prepared,
            "src/game/behaviors/OrderedSwitches.ts").as_posix() == \
            "src/game/behaviors/OrderedSwitches.ts"

        other = service.workspace.create_folder_project(d3_workspace, "D3 other")
        service.workspace.initialize_game_project(other.project_id, {
            "target_platform": "web", "engine": "threejs",
            "code_architecture": "object-component", "architecture_label": "对象／组件式",
            "selection_method": "manual", "rationale": "D3 scope check", "tradeoffs": [],
            "ecs_library": None,
        }, 1, commit_baseline=False)
        other_workspace = service.workspace.open_project_demo_workspace(other.project_id)
        with pytest.raises(HarnessError) as crossed:
            service.project_demo_workspace(project.project_id, other_workspace["workspace_id"])
        assert crossed.value.code == "PROJECT_DEMO_WORKSPACE_INVALID"
    finally:
        await service.close()


def test_model_repairs_switch_source_and_continues_same_task(d3_workspace):
    asyncio.run(_model_repairs_switch_source_and_continues_same_task(d3_workspace))


async def _model_repairs_switch_source_and_continues_same_task(d3_workspace):
    service, provider, assets, scenes, project, request = make_service(d3_workspace, "switch")
    try:
        prepared = service.prepare(request)
        assert service.prepare(request).id == prepared.id
        service.authorize(prepared.id, AuthorizeAgentTask(
            authorization_card_id=prepared.authorization_card.id, accept_unknown_cost=True))
        await settle(service)
        first = service.get(prepared.id)
        failed_checks = [entry for entry in first.actions
            if entry.action.capability_id == "code.project.check"
            and entry.result["evidence"]["run"]["passed"] is False]
        assert failed_checks
        assert first.status == "review_required", first.reason
        source = Path(project.root_path) / "src/game/behaviors/OrderedSwitches.ts"
        assert source.read_text("utf-8") == provider.switch_source()
        manifest_path = Path(project.root_path) / ".sceneops/demo-content.json"
        manifest = json.loads(manifest_path.read_text("utf-8"))
        assert manifest["assets"] == []
        assert manifest["objects"] == []
        assert "project_demo_fixture" not in first.observations
        first_candidate = service.game_status(prepared.id).current_playable_candidate

        follow = ContinueProjectDemoRequest(request_id="follow_switch_order",
            goal="把开关顺序改为右、左，保留当前作品和其他源码")
        queued = service.continue_project_demo(prepared.id, follow)
        assert queued.id == prepared.id
        await settle(service)
        completed = service.get(prepared.id)
        assert completed.model_calls_used == 20
        assert completed.grant.expires_at == first.grant.expires_at
        assert completed.grant.budget == first.grant.budget
        assert completed.grant.workspace_id == first.grant.workspace_id
        assert source.read_text("utf-8") == provider.switch_source(("arrowright", "arrowleft"))
        second_candidate = service.game_status(prepared.id).current_playable_candidate
        assert second_candidate.id != first_candidate.id
        assert second_candidate.source_version["goal_request_id"] == "follow_switch_order"
        calls = len(provider.requests)
        assert service.continue_project_demo(prepared.id, follow).id == prepared.id
        assert len(provider.requests) == calls
        with pytest.raises(HarnessError, match="不能更换目标"):
            service.continue_project_demo(prepared.id, ContinueProjectDemoRequest(
                request_id="follow_switch_order", goal="换成任意新目标"))
        await service.close()
        service = AgentTaskService(provider.database_path, service.workspace,
            d3_workspace / "data", provider=provider, project_assets=assets,
            environment_scenes=scenes)
        assert service.get(prepared.id).observations["demo_goals"] == completed.observations["demo_goals"]
        assert service.game_status(prepared.id).current_playable_candidate.id == second_candidate.id
        assert source.read_text("utf-8") == provider.switch_source(("arrowright", "arrowleft"))
    finally:
        await service.close()
