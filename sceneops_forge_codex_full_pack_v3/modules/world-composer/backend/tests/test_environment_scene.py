import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from asset_library import (
    ProjectAssetCatalogService,
    ProjectAssetRegistration,
    ProjectAssetVersion,
    SqliteProjectAssetRepository,
)
from world_composer import (
    AiBuildRequest,
    EnvironmentSceneError,
    EnvironmentSceneService,
    EnvironmentTransform,
    ManualPlacementRequest,
    TransformObjectRequest,
)


class Workspace:
    def exists(self, project_id):
        return project_id == "prj_game"


class Provider:
    def __init__(self):
        self.calls = 0

    def settings(self):
        return SimpleNamespace(provider="fixture", model="scene-layout-v1")

    async def structured(self, prompt, schema, **_kwargs):
        self.calls += 1
        self.asset_id = next(item.id for item in self.catalog.list("prj_game"))
        self.assert_prompt = prompt
        assert schema["type"] == "object"
        return {
            "summary": "沿道路两边摆放两棵树，留出中间通道。",
            "replace_existing": False,
            "placements": [
                {"asset_id": self.asset_id, "position_m": [-3, 0, -4], "rotation_y_deg": 15, "scale": 1},
                {"asset_id": self.asset_id, "position_m": [3, 0, -4], "rotation_y_deg": -20, "scale": 0.9},
            ],
        }


class EnvironmentSceneTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_and_ai_scene_versions_are_real_and_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-environment-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            entry = catalog.register_version(ProjectAssetRegistration(
                project_id="prj_game",
                card_id="environment",
                source_asset_id="asset_tree",
                title="大树",
                source_type="generated",
                version=ProjectAssetVersion(
                    source_version=1,
                    dimensions_m=(4, 4, 6),
                    vertex_count=100,
                    triangle_count=160,
                    blend_path="assets/tree/model.blend",
                    preview_path="assets/tree/preview.glb",
                    fbx_path="assets/tree/model.fbx",
                    operation="generate",
                ),
            )).entry
            provider = Provider()
            provider.catalog = catalog
            service = EnvironmentSceneService(database, Workspace(), catalog, provider)
            manual = service.add_object("prj_game", ManualPlacementRequest(
                expected_version=0, asset_id=entry.id, position_m=(0, 0, 0)
            ))
            moved = service.transform_object("prj_game", manual.objects[0].id, TransformObjectRequest(
                expected_version=1,
                transform=EnvironmentTransform(position_m=(1, 0, 2), rotation_y_deg=45, scale=1.2),
            ))
            request = AiBuildRequest(
                request_id="request_1",
                expected_version=2,
                prompt="用两棵树围出道路入口",
            )
            built = await service.ai_build("prj_game", request)
            retry = await service.ai_build("prj_game", request)
            with self.assertRaises(EnvironmentSceneError) as conflict:
                await service.ai_build("prj_game", request.model_copy(update={"prompt": "改成另一种布局"}))
            self.assertEqual(moved.objects[0].transform.position_m, (1, 0, 2))
            self.assertEqual(built.scene.version, 3)
            self.assertEqual(len(built.scene.objects), 3)
            self.assertEqual(len(built.scene.history), 2)
            self.assertTrue(retry.reused)
            self.assertEqual(retry.scene.version, 3)
            self.assertEqual(provider.calls, 1)
            self.assertIn("资产库", provider.assert_prompt)
            self.assertEqual(conflict.exception.code, "AI_BUILD_REQUEST_CONFLICT")


if __name__ == "__main__":
    unittest.main()
