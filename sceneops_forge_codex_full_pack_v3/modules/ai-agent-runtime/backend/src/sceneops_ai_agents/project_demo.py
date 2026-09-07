"""Deterministic D1/D2 project Demo fixture and content-to-runtime delivery."""
from __future__ import annotations

import json
from pathlib import Path

from sceneops_harness import HarnessError
from .task_models import AgentAction, now


DOOR_SOURCE_ID = "sceneops-project-demo-door-v1"


def _door_asset(service, task):
    from asset_library import DoorRecipe, ProjectAssetRegistration, ProjectAssetVersion

    existing = next((item for item in service.project_assets.list(task.project_id)
                     if item.source_asset_id == DOOR_SOURCE_ID), None)
    if existing is not None:
        if existing.workspace_id != task.grant.workspace_id:
            raise HarnessError("TASK_SCOPE_DENIED", "门配方属于另一个项目工作区。")
        return existing
    version = ProjectAssetVersion(
        source_version=1, asset_version_id="aver_sceneops_project_demo_door_v1",
        source_kind="procedural", dimensions_m=(1.2, 2.2, .15),
        vertex_count=24, triangle_count=12, recipe=DoorRecipe(), operation="recipe-create",
    )
    result = service.project_assets.register_version(ProjectAssetRegistration(
        project_id=task.project_id, workspace_id=task.grant.workspace_id,
        source_asset_id=DOOR_SOURCE_ID, title="钥匙门", source_type="generated", version=version,
    ))
    return result.entry


def _ensure_fixture(service, task):
    from world_composer import ManualPlacementRequest, UpdateKeyDoorBehaviorRequest

    door = _door_asset(service, task)
    scene = service.environment_scenes.get(task.project_id)
    doors = [item for item in scene.objects if item.asset_id == door.id]
    for position in ((-2.0, 0.0, -4.0), (2.0, 0.0, -4.0))[len(doors):2]:
        scene = service.environment_scenes.add_object(task.project_id, ManualPlacementRequest(
            expected_version=scene.version, asset_id=door.id,
            asset_version=door.current_version, position_m=position,
        ))
    doors = [item for item in scene.objects if item.asset_id == door.id]
    for item in doors[:2]:
        if item.behavior is None:
            scene = service.environment_scenes.update_key_door_behavior(
                task.project_id, item.id, UpdateKeyDoorBehaviorRequest(
                    expected_version=scene.version, required_key_asset_id=door.id,
                    interaction_distance_m=2.0, open_angle_deg=90.0,
                ))
    return door, scene


def _source_version(root: Path) -> dict:
    marker = root / ".sceneops" / "game-architecture.json"
    try:
        data = json.loads(marker.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HarnessError("GAME_PROJECT_INVALID", "游戏架构记录不可读取。") from error
    return {
        "architecture_version": data.get("architecture_version"),
        "design_version": data.get("design_version"),
        "code_architecture": data.get("code_architecture"),
        "state": "working-tree",
    }


def _manifest(service, task, scene):
    asset_ids = {item.asset_id for item in scene.objects if item.behavior is not None}
    assets = []
    version_by_ref = {}
    for asset_id in sorted(asset_ids):
        entry = service.project_assets.get(task.project_id, asset_id)
        for version in entry.versions:
            version_by_ref[(entry.id, version.source_version)] = version
        referenced_versions = sorted({item.asset_version for item in scene.objects
                                      if item.asset_id == entry.id and item.behavior is not None})
        for number in referenced_versions:
            version = version_by_ref[(entry.id, number)]
            if version.source_kind != "procedural" or version.recipe is None:
                raise HarnessError("DEMO_ASSET_SOURCE_UNSUPPORTED",
                                   "首批 Demo 门实例必须引用可编辑程序化门配方。")
            assets.append({
                "asset_id": entry.id, "asset_version": number,
                "asset_version_id": version.asset_version_id,
                "recipe": version.recipe.model_dump(mode="json"),
                "runtime_artifacts": [item.model_dump(mode="json") for item in version.runtime_artifacts],
            })
    objects = []
    for item in scene.objects:
        if item.behavior is None:
            continue
        objects.append({
            "id": item.id, "asset_id": item.asset_id, "asset_version": item.asset_version,
            "asset_version_id": item.asset_version_id,
            "transform": item.transform.model_dump(mode="json"),
            "behavior": {
                "behavior_instance_id": item.behavior.behavior_instance_id,
                "kind": "KeyDoor", "definition_id": item.behavior.definition_id,
                "required_key_asset_id": item.behavior.required_key_asset_id,
                "interaction_distance_m": item.behavior.interaction_distance_m,
                "open_angle_deg": item.behavior.open_angle_deg,
            },
        })
    return {
        "schema_version": 1, "project_id": task.project_id,
        "workspace_id": task.grant.workspace_id, "scene_id": scene.scene_id,
        "scene_version": scene.version, "assets": assets, "objects": objects,
    }


def materialize_project_demo(service, task):
    if task.authorization_card.task_profile != "project-demo":
        raise HarnessError("TASK_SCOPE_DENIED", "当前任务不是项目级 Demo。")
    if service.project_assets is None or service.environment_scenes is None:
        raise HarnessError("PROJECT_DEMO_NOT_CONNECTED", "项目资产或场景服务尚未连接。")
    workspace = service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                                               expected_root=task.grant.workspace_root)
    _, scene = _ensure_fixture(service, task)
    manifest = _manifest(service, task, scene)
    report = service.workspace.materialize_demo_content(
        task.project_id, task.grant.workspace_id, manifest)
    root = Path(workspace["workspace_root"])
    materialization = {
        **report, "source_version": _source_version(root),
        "asset_versions": [{"asset_id": item["asset_id"],
                            "asset_version": item["asset_version"],
                            "asset_version_id": item["asset_version_id"]}
                           for item in manifest["assets"]],
    }
    service.records.update(task.id,
        lambda current: current.observations.update({"demo_materialization": materialization}),
        "agent.demo_content.materialized", {"scene_version": scene.version})
    service.game.invalidate_workspace(root)
    return {"tool": "demo_content", "mode": "live", "effect_state": "COMMITTED",
            "outcome": "source_saved", **materialization}


async def run_project_demo(service, task_id):
    """Execute the bounded materialize/check/build/preview recipe without a model call."""
    from .task_loop import execute_action, record_action

    task = service.check_grant(task_id)
    update_number = 1 + sum(item.action.capability_id == "code.demo_content.materialize"
                            for item in task.actions)
    prefix = f"demo_update_{update_number}"
    steps = [
        (f"{prefix}_materialize", "code.demo_content.materialize", "保存当前门配方、场景实例与行为参数到登记游戏工程。"),
    ]
    if not service.game.dependencies_ready(task.grant.workspace_root):
        if not task.grant.allow_dependency_install:
            raise HarnessError("DEPENDENCIES_NOT_READY", "工程依赖尚未准备，且本次未授权依赖准备。")
        steps.append((f"{prefix}_dependencies", "code.dependencies.prepare", "准备登记游戏工程声明的依赖。"))
    steps.extend([
        (f"{prefix}_check", "code.project.check", "检查当前物化内容与所选代码架构。"),
        (f"{prefix}_build", "code.project.build", "为本次内容请求生成独立试玩候选。"),
        (f"{prefix}_preview", "code.preview.start", "让最新成功候选成为当前作品的本地试玩。"),
    ])
    failure = None
    for action_id, capability, rationale in steps:
        record_action(service, task_id, AgentAction(
            action_id=action_id, capability_id=capability, rationale=rationale, inputs={}))
        await execute_action(service, task_id, action_id)
        entry = next(item for item in service.get(task_id).actions
                     if item.action.action_id == action_id)
        evidence = (entry.result or {}).get("evidence", {})
        run = evidence.get("run", {}) if isinstance(evidence, dict) else {}
        if capability.startswith(("code.project.", "code.preview.")) and run.get("passed") is not True:
            failure = run.get("failure_code") or "DEMO_UPDATE_FAILED"
            break
    snapshot = service.game.snapshot(service.get(task_id))
    def finish(current):
        current.status = "review_required"
        current.finished_at = now()
        current.reason = (f"试玩更新失败（{failure}）；上一可玩候选保持不变。" if failure else
                          "门配方、场景与行为配置已物化，最新试玩候选正在运行。")
        current.observations["demo_update"] = {
            "status": "failed" if failure else "updated", "failure_code": failure,
            "current_candidate_id": (snapshot.current_playable_candidate.id
                                     if snapshot.current_playable_candidate else None),
            "latest_candidate_id": snapshot.latest_candidate.id if snapshot.latest_candidate else None,
            "preview_url": snapshot.preview.preview_url if snapshot.preview else None,
        }
    service.records.update(task_id, finish, "agent.project_demo.finished",
                           {"status": "failed" if failure else "updated"})
