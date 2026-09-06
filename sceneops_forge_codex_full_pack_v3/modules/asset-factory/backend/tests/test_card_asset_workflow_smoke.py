"""Focused card-asset smoke; real Blender remains opt-in through environment."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from asset_factory import CardAssetService, LiveModelUpdateRequest, ModelPlanRequest
from asset_library import ProjectAssetCatalogService, SqliteProjectAssetRepository
from sceneops_ai_provider import ProviderService
from sceneops_project_workspace import SqliteWorkspaceRepository


class FixtureProvider:
    def __init__(self):
        self.calls = 0

    def settings(self):
        return SimpleNamespace(provider="fixture", model="tree-v1")

    async def structured(self, prompt, schema, **kwargs):
        self.calls += 1
        assert "固定 Blender 原语执行器" in prompt
        assert schema["type"] == "object"
        return {
            "title": "低多边形大树",
            "summary": "一个可作为场景地标的树干与分层树冠。",
            "target_extent_m": 6.0,
            "parts": [
                {"kind": "cylinder", "name": "树干", "dimensions_m": [1.0, 1.0, 4.0],
                 "location_m": [0.0, 0.0, 2.0], "rotation_deg": [0.0, 0.0, 0.0], "color": "#70472A"},
                {"kind": "sphere", "name": "树冠", "dimensions_m": [4.5, 4.5, 3.0],
                 "location_m": [0.0, 0.0, 4.5], "rotation_deg": [0.0, 0.0, 0.0], "color": "#3F7F45"},
            ],
        }


class FixtureBlender:
    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.payloads = []

    def run(self, change_id, _asset_root, payload):
        self.payloads.append(payload)
        for key, value in payload["output"].items():
            path = Path(value)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((key + "-fixture").encode())
        log = self.data_root / "card-asset-runs" / change_id / "blender.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("fixture", encoding="utf-8")
        return ({"dimensions_m": [2.0, 2.0, 6.0], "vertex_count": 48, "triangle_count": 80,
                 "object_ids": payload["object_ids"], "blender_version": "fixture"}, log)


class FixtureCardWorkspace:
    def __init__(self, root: Path):
        self.root = root

    def get_card_worktree(self, project_id, card_id):
        return {"worktree_path": str(self.root), "branch": f"card/{card_id}"}


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


class CardAssetWorkflowSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_live_dialogue_updates_append_versions_and_dedupe_message(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-turns-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            binding = repository.open_card_worktree(project.project_id, "map", "地图")
            provider = FixtureProvider()
            catalog = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            service = CardAssetService(database, root / "data", repository, provider,
                                       blender=FixtureBlender(root / "data"), catalog=catalog)
            first_request = LiveModelUpdateRequest(session_id="modeling_live", trigger_message_id="message_1",
                modeling_block="shape", transcript=[{"role": "user", "text": "低多边形背景树"}])
            first = await service.live_update(project.project_id, "map", first_request)
            duplicate = await service.live_update(project.project_id, "map", first_request)
            second = await service.live_update(project.project_id, "map", LiveModelUpdateRequest(
                session_id="modeling_live", trigger_message_id="message_2", modeling_block="scale",
                transcript=[{"role": "user", "text": "低多边形背景树"},
                            {"role": "assistant", "text": "尺寸如何？"},
                            {"role": "user", "text": "六米高"}]))
            self.assertTrue(first.version_created)
            self.assertTrue(duplicate.reused)
            self.assertFalse(duplicate.version_created)
            self.assertEqual(first.asset.id, second.asset.id)
            self.assertEqual([version.number for version in second.asset.versions], [1, 2])
            self.assertEqual(provider.calls, 2)
            saved = service.save_to_library(second.asset.id, 2)
            repeated_save = service.save_to_library(second.asset.id, 2)
            self.assertTrue(saved.version_created)
            self.assertFalse(repeated_save.version_created)
            self.assertEqual(saved.entry.source_asset_id, second.asset.id)
            self.assertEqual(saved.entry.current_version, 2)
            worktree = Path(binding["worktree_path"])
            self.assertTrue((worktree / second.asset.versions[0].preview_path).is_file())
            self.assertTrue((worktree / second.asset.versions[1].preview_path).is_file())

    async def test_model_rotation_inherits_and_save_bakes_a_new_calibration_version(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-rotation-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            database.parent.mkdir()
            blender = FixtureBlender(root / "data")
            catalog = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            service = CardAssetService(database, root / "data", FixtureCardWorkspace(root), FixtureProvider(),
                                       blender=blender, catalog=catalog)
            quarter_turn_x = (0.7071067811865476, 0.0, 0.0, 0.7071067811865476)
            quarter_turn_y = (0.0, 0.7071067811865476, 0.0, 0.7071067811865476)
            first = await service.live_update("project", "map", LiveModelUpdateRequest(
                session_id="rotation", trigger_message_id="message_1", modeling_block="shape",
                transcript=[{"role": "user", "text": "一个模型"}],
                model_rotation_quaternion_xyzw=quarter_turn_x))
            second = await service.live_update("project", "map", LiveModelUpdateRequest(
                session_id="rotation", trigger_message_id="message_2", modeling_block="scale",
                transcript=[{"role": "user", "text": "一个模型"}, {"role": "user", "text": "继续修改"}],
                model_rotation_quaternion_xyzw=quarter_turn_x))

            self.assertEqual([item.model_rotation_quaternion_xyzw for item in second.asset.versions],
                             [quarter_turn_x, quarter_turn_x])
            saved = service.save_to_library(second.asset.id, 2, quarter_turn_y)
            self.assertEqual(saved.entry.current_version, 3)
            self.assertEqual(saved.entry.versions[0].operation, "calibrate")
            record = service._load("card_asset_records", second.asset.id, type(second.asset))
            self.assertEqual([item.number for item in record.versions], [1, 2, 3])
            self.assertEqual(record.versions[-1].model_rotation_quaternion_xyzw, quarter_turn_y)
            self.assertEqual(blender.payloads[-1]["operation"], "calibrate")
            self.assertEqual(blender.payloads[-1]["model_rotation_quaternion_xyzw"], list(quarter_turn_y))

    async def test_plan_is_saved_without_running_blender(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-plan-") as directory:
            root = Path(directory).resolve()
            repository = SqliteWorkspaceRepository(root / "data" / "sceneops.sqlite3")
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            repository.open_card_worktree(project.project_id, "map", "地图")
            service = CardAssetService(root / "data" / "sceneops.sqlite3", root / "data", repository, FixtureProvider())
            proposal = await service.plan(project.project_id, "map", ModelPlanRequest(
                session_id="modeling_1", transcript=[{"role": "user", "text": "做一棵六米高的低多边形大树"}]))
            self.assertEqual(proposal.status, "planned")
            self.assertEqual(service.list(project.project_id, "map").assets, [])

    @unittest.skipUnless(os.environ.get("SCENEOPS_REAL_AI_SMOKE") == "1", "real AI smoke not requested")
    async def test_real_codebuddy_plan(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-ai-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            repository.open_card_worktree(project.project_id, "map", "地图")
            provider = ProviderService(database)
            provider.update_settings(provider="codebuddycli", model="glm-5.3-flash")
            service = CardAssetService(database, root / "data", repository, provider)
            proposal = await service.plan(project.project_id, "map", ModelPlanRequest(
                session_id="modeling_ai", transcript=[
                    {"role": "user", "text": "一棵六米高的低多边形卡通背景树，粗短树干、分层圆团树冠、自然绿棕色。"},
                    {"role": "assistant", "text": "作为不参与玩法交互的场景装饰，使用简单纯色材质。"},
                ]))
            self.assertEqual(proposal.provider, "codebuddycli")
            self.assertEqual(proposal.model, "glm-5.3-flash")
            self.assertGreaterEqual(len(proposal.parts), 1)

    @unittest.skipUnless(os.environ.get("SCENEOPS_REAL_BLENDER_SMOKE") == "1", "real Blender smoke not requested")
    async def test_real_live_dialogue_versions(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-live-turns-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            binding = repository.open_card_worktree(project.project_id, "map", "地图")
            service = CardAssetService(database, root / "data", repository, FixtureProvider())
            first = await service.live_update(project.project_id, "map", LiveModelUpdateRequest(
                session_id="modeling_real_live", trigger_message_id="message_1", modeling_block="shape",
                transcript=[{"role": "user", "text": "低多边形背景树"}]))
            second = await service.live_update(project.project_id, "map", LiveModelUpdateRequest(
                session_id="modeling_real_live", trigger_message_id="message_2", modeling_block="scale",
                transcript=[{"role": "user", "text": "低多边形背景树"},
                            {"role": "assistant", "text": "尺寸如何？"},
                            {"role": "user", "text": "六米高"}]))
            worktree = Path(binding["worktree_path"])
            self.assertEqual(second.asset.id, first.asset.id)
            self.assertEqual(second.asset.current_version, 2)
            self.assertGreater((worktree / first.asset.versions[0].preview_path).stat().st_size, 100)
            self.assertGreater((worktree / second.asset.versions[1].preview_path).stat().st_size, 100)

    @unittest.skipUnless(os.environ.get("SCENEOPS_REAL_AI_BLENDER_SMOKE") == "1", "real AI + Blender smoke not requested")
    async def test_real_codebuddy_live_dialogue_to_blender(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-ai-live-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            binding = repository.open_card_worktree(project.project_id, "map", "地图")
            provider = ProviderService(database)
            provider.update_settings(provider="codebuddycli", model="glm-5.3-flash")
            service = CardAssetService(database, root / "data", repository, provider)
            result = await service.live_update(project.project_id, "map", LiveModelUpdateRequest(
                session_id="modeling_ai_live", trigger_message_id="message_1", modeling_block="shape",
                transcript=[{"role": "user", "text": "制作一棵六米高的低多边形卡通背景树，粗短树干，分层圆团树冠，自然绿棕色。"}]))
            preview = Path(binding["worktree_path"]) / result.asset.versions[0].preview_path
            self.assertEqual(result.proposal.provider, "codebuddycli")
            self.assertEqual(result.proposal.model, "glm-5.3-flash")
            self.assertEqual(result.asset.status, "ready")
            self.assertGreater(preview.stat().st_size, 100)

    @unittest.skipUnless(os.environ.get("SCENEOPS_REAL_BLENDER_SMOKE") == "1", "real Blender smoke not requested")
    async def test_real_generate_import_and_normalize(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-card-asset-live-") as directory:
            root = Path(directory).resolve()
            database = root / "data" / "sceneops.sqlite3"
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, "game")
            repository.commit_design_version(project.project_id, 1, {"version": 1})
            binding = repository.open_card_worktree(project.project_id, "map", "地图")
            service = CardAssetService(database, root / "data", repository, FixtureProvider())
            proposal = await service.plan(project.project_id, "map", ModelPlanRequest(
                session_id="modeling_live", transcript=[{"role": "user", "text": "做一棵六米高的低多边形大树"}]))
            generated = service.generate(proposal.id)
            self.assertEqual(generated.status, "ready")
            self.assertTrue(generated.versions[0].blender_version.startswith("5.1"))
            worktree = Path(binding["worktree_path"])
            preview = worktree / generated.versions[0].preview_path
            self.assertGreater(preview.stat().st_size, 100)
            imported = service.import_asset(project.project_id, "map", preview, "generated-tree.glb")
            self.assertEqual(imported.status, "ready")
            fbx = worktree / generated.versions[0].fbx_path
            imported_fbx = service.import_asset(project.project_id, "map", fbx, "generated-tree.fbx")
            self.assertEqual(imported_fbx.status, "ready")
            normalized = service.normalize(imported.id, 2.0)
            self.assertEqual(normalized.current_version, 2)
            self.assertAlmostEqual(max(normalized.versions[-1].dimensions_m), 2.0, places=3)
            self.assertTrue((worktree / imported.source_path).is_file())
            self.assertIn("assets/", git(worktree, "status", "--porcelain"))
            self.assertEqual(git(worktree, "log", "-1", "--format=%s"), "Confirm design v1")


if __name__ == "__main__":
    unittest.main()
