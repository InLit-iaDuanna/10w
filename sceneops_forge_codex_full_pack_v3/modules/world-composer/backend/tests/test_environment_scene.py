import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from asset_library import (
    DoorRecipe,
    ProjectAssetCatalogService,
    ProjectAssetRegistration,
    ProjectAssetVersion,
    SqliteProjectAssetRepository,
    UpdateProjectAssetRecipeRequest,
)
from world_composer import (
    AiBuildRequest,
    AssetVersionRebindResult,
    EnvironmentObject,
    EnvironmentScene,
    EnvironmentSceneError,
    EnvironmentSceneService,
    EnvironmentTransform,
    ManualPlacementRequest,
    RebindAssetVersionRequest,
    SharedProjectMemory,
    TransformObjectRequest,
    UpdateKeyDoorBehaviorRequest,
    key_door_behavior_definition,
)


class Workspace:
    def exists(self, project_id):
        return project_id == "prj_game"


class TwoProjectWorkspace:
    def exists(self, project_id):
        return project_id in {"prj_game", "prj_other"}


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


class FixturePreparation:
    def __init__(self):
        self.calls = []

    async def prepare(self, request):
        self.calls.append(request)
        return SimpleNamespace(
            recommendation=SimpleNamespace(assets=[]),
            model_dump=lambda **_kwargs: {'status': 'succeeded', 'recommendation': {
                'assets': [], 'experiences': [{'candidate_id': 'scene-scale', 'revision': 2,
                    'purpose': '尺度', 'adoption': 'reference', 'reason': '匹配'}],
                'skills': [], 'production_advice': [], 'conflicts': [], 'gaps': []}},
        )

    async def selected_context(self, request, result):
        return {'status': 'succeeded', 'recommendation': result.model_dump()['recommendation'],
                'selected_details': [{'identity': {'candidate_id': 'scene-scale'},
                                      'content': {'body': '保持米制尺度与道路净宽'}}]}


class BuiltinPreparation(FixturePreparation):
    async def prepare(self, request):
        self.calls.append(request)
        selection = SimpleNamespace(candidate_id='builtin:tree')
        return SimpleNamespace(
            recommendation=SimpleNamespace(assets=[selection]),
            model_dump=lambda **_kwargs: {'status': 'succeeded', 'recommendation': {
                'assets': [{'candidate_id': 'builtin:tree', 'version': 'pack:1',
                    'purpose': '道路入口', 'adoption': 'import', 'reason': '匹配'}],
                'experiences': [], 'skills': [], 'production_advice': [],
                'conflicts': [], 'gaps': []}},
        )

    async def selected_context(self, request, result):
        return {'status': 'succeeded', 'recommendation': result.model_dump()['recommendation'],
                'selected_details': []}


class EnvironmentSceneTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def catalog(database):
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
        return catalog, entry

    async def test_manual_and_ai_scene_versions_are_real_and_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-environment-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog, entry = self.catalog(database)
            provider = Provider()
            provider.catalog = catalog
            preparation = FixturePreparation()
            service = EnvironmentSceneService(database, Workspace(), catalog, provider,
                                              production_preparation=preparation)
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
                shared_memory=SharedProjectMemory(
                    project_title="像素末世",
                    core_loop="探索、刷怪、升级",
                    technical_plan="Three.js + Miniplex ECS",
                    active_card="3D 世界与场景搭建",
                ),
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
            self.assertEqual(len(preparation.calls), 1)
            self.assertEqual(preparation.calls[0].production_kind, 'scene')
            self.assertEqual(built.production_preparation['status'], 'succeeded')
            self.assertEqual(retry.production_preparation, built.production_preparation)
            self.assertIn('保持米制尺度与道路净宽', provider.assert_prompt)
            self.assertIn("资产库", provider.assert_prompt)
            self.assertIn("像素末世", provider.assert_prompt)
            self.assertIn("探索、刷怪、升级", provider.assert_prompt)
            self.assertIn("Three.js + Miniplex ECS", provider.assert_prompt)
            self.assertEqual(conflict.exception.code, "AI_BUILD_REQUEST_CONFLICT")

    async def test_builtin_adoption_failure_is_visible_and_existing_scene_assets_continue(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-environment-adoption-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog, _ = self.catalog(database)
            provider = Provider()
            provider.catalog = catalog
            preparation = BuiltinPreparation()
            def fail_adoption(*_args):
                raise RuntimeError("fixture adoption failure")
            service = EnvironmentSceneService(database, Workspace(), catalog, provider,
                production_preparation=preparation,
                builtin_asset_adopt=fail_adoption)

            result = await service.ai_build("prj_game", AiBuildRequest(
                request_id="adoption_failure", expected_version=0,
                prompt="用现有树围出道路入口"))

            materialization = result.production_preparation['materialization']
            self.assertEqual(materialization[0]['state'], 'not_adopted')
            self.assertIn('fixture adoption failure', materialization[0]['reason'])
            self.assertEqual(result.scene.version, 1)

    async def test_manual_placement_rejects_the_201st_object_without_saving_it(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-environment-limit-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog, entry = self.catalog(database)
            service = EnvironmentSceneService(database, Workspace(), catalog, Provider())
            template = EnvironmentObject(id="sobj_0", asset_id=entry.id, asset_version=1,
                source_asset_id=entry.source_asset_id, title=entry.title,
                transform=EnvironmentTransform())
            scene = EnvironmentScene(scene_id="scene_game", project_id="prj_game", version=1,
                objects=[template.model_copy(update={"id": f"sobj_{index}"}) for index in range(200)])
            with service._connect() as connection:
                connection.execute(
                    "INSERT INTO environment_scene_versions VALUES (?,?,?,?)",
                    ("prj_game", 1, scene.model_dump_json(), scene.updated_at),
                )

            with self.assertRaises(EnvironmentSceneError) as limit:
                service.add_object("prj_game", ManualPlacementRequest(
                    expected_version=1, asset_id=entry.id,
                ))

            self.assertEqual(limit.exception.code, "SCENE_OBJECT_LIMIT")
            latest = service.get("prj_game")
            self.assertEqual(latest.version, 1)
            self.assertEqual(len(latest.objects), 200)

    async def test_restart_marks_an_interrupted_ai_request_retryable(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-environment-restart-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog, _ = self.catalog(database)
            provider = Provider()
            provider.catalog = catalog
            request = AiBuildRequest(request_id="interrupted", expected_version=0,
                                     prompt="用两棵树围出道路入口")
            first_process = EnvironmentSceneService(database, Workspace(), catalog, provider)
            self.assertIsNone(first_process._claim_ai("prj_game", request))

            restarted = EnvironmentSceneService(database, Workspace(), catalog, provider)
            result = await restarted.ai_build(
                "prj_game", request.model_copy(update={"retry_failed": True})
            )

            self.assertEqual(result.scene.version, 1)
            self.assertFalse(result.reused)

    async def test_key_door_behavior_shared_asset_upgrade_and_restart(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-key-door-") as directory:
            database = Path(directory) / "sceneops.sqlite3"
            catalog, key = self.catalog(database)
            recipe = DoorRecipe()
            door = catalog.register_version(ProjectAssetRegistration(
                project_id="prj_game",
                workspace_id="workspace_game",
                source_asset_id="asset_front_door",
                title="家门",
                source_type="generated",
                version=ProjectAssetVersion(
                    source_version=1,
                    asset_version_id="aver_front_door_1",
                    source_kind="procedural",
                    dimensions_m=recipe.dimensions_m,
                    vertex_count=24,
                    triangle_count=12,
                    recipe=recipe,
                    operation="recipe-create",
                ),
            )).entry
            service = EnvironmentSceneService(database, Workspace(), catalog, Provider())
            first = service.add_object("prj_game", ManualPlacementRequest(
                expected_version=0, asset_id=door.id, position_m=(-2, 0, 0),
            ))
            second = service.add_object("prj_game", ManualPlacementRequest(
                expected_version=1, asset_id=door.id, position_m=(2, 0, 0),
            ))
            first_id, second_id = first.objects[0].id, second.objects[1].id
            behavior_scene = service.update_key_door_behavior(
                "prj_game", first_id, UpdateKeyDoorBehaviorRequest(
                    expected_version=2,
                    required_key_asset_id=key.id,
                    interaction_distance_m=2,
                    open_angle_deg=105,
                ),
            )
            behavior_id = behavior_scene.objects[0].behavior.behavior_instance_id
            updated_door = catalog.update_recipe(
                "prj_game", door.id,
                UpdateProjectAssetRecipeRequest(
                    expected_version=1,
                    recipe=recipe.model_copy(update={"width_m": 1.8}),
                ),
            ).entry

            rebound = service.rebind_asset_version(
                "prj_game", door.id,
                RebindAssetVersionRequest(
                    expected_version=3, from_asset_version=1, to_asset_version=2,
                ),
            )

            self.assertIsInstance(rebound, AssetVersionRebindResult)
            self.assertEqual(rebound.affected_object_ids, [first_id, second_id])
            self.assertEqual([item.asset_version for item in rebound.scene.objects], [2, 2])
            self.assertEqual(
                {item.asset_version_id for item in rebound.scene.objects},
                {updated_door.versions[-1].asset_version_id},
            )
            self.assertEqual(
                [item.transform.position_m for item in rebound.scene.objects],
                [(-2, 0, 0), (2, 0, 0)],
            )
            self.assertEqual(rebound.scene.objects[0].behavior.behavior_instance_id, behavior_id)
            self.assertIsNone(rebound.scene.objects[1].behavior)

            restarted = EnvironmentSceneService(database, Workspace(), catalog, Provider())
            restored = restarted.get("prj_game")
            changed = restarted.update_key_door_behavior(
                "prj_game", first_id, UpdateKeyDoorBehaviorRequest(
                    expected_version=restored.version,
                    required_key_asset_id=key.id,
                    interaction_distance_m=1,
                    open_angle_deg=105,
                ),
            )
            self.assertEqual(changed.objects[0].behavior.behavior_instance_id, behavior_id)
            self.assertEqual(changed.objects[0].behavior.interaction_distance_m, 1)
            self.assertIsNone(changed.objects[1].behavior)
            self.assertEqual(key_door_behavior_definition().parameters[1].unit, "meter")

            with self.assertRaises(EnvironmentSceneError) as conflict:
                restarted.rebind_asset_version(
                    "prj_game", door.id,
                    RebindAssetVersionRequest(
                        expected_version=3, from_asset_version=1, to_asset_version=2,
                    ),
                )
            self.assertEqual(conflict.exception.code, "SCENE_VERSION_CONFLICT")
            cross_project = EnvironmentSceneService(
                database, TwoProjectWorkspace(), catalog, Provider()
            )
            with self.assertRaises(EnvironmentSceneError) as wrong_project:
                cross_project.rebind_asset_version(
                    "prj_other", door.id,
                    RebindAssetVersionRequest(
                        expected_version=0, from_asset_version=1, to_asset_version=2,
                    ),
                )
            self.assertEqual(wrong_project.exception.code, "ASSET_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
