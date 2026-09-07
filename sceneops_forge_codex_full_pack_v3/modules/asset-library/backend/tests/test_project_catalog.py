import tempfile
import unittest
from pathlib import Path

from asset_library import (
    DoorMaterial,
    DoorRecipe,
    ProjectAssetCatalogService,
    ProjectAssetEntry,
    ProjectAssetRegistration,
    ProjectAssetVersion,
    RuntimeArtifactReference,
    SqliteProjectAssetRepository,
    UpdateProjectAssetRecipeRequest,
    door_recipe_definition,
)


class ProjectAssetCatalogTests(unittest.TestCase):
    def test_versions_append_and_exact_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-project-catalog-") as directory:
            service = ProjectAssetCatalogService(
                SqliteProjectAssetRepository(Path(directory) / "catalog.sqlite3")
            )
            version = ProjectAssetVersion(
                source_version=1,
                dimensions_m=(2, 3, 4),
                vertex_count=24,
                triangle_count=12,
                blend_path="assets/tree/v1/model.blend",
                preview_path="assets/tree/v1/preview.glb",
                fbx_path="assets/tree/v1/model.fbx",
                operation="generate",
            )
            request = ProjectAssetRegistration(
                project_id="prj_game",
                card_id="environment",
                source_asset_id="asset_tree",
                title="大树",
                source_type="generated",
                version=version,
            )
            first = service.register_version(request)
            retry = service.register_version(request)
            second = service.register_version(request.model_copy(update={
                "version": version.model_copy(update={
                    "source_version": 2,
                    "preview_path": "assets/tree/v2/preview.glb",
                    "blend_path": "assets/tree/v2/model.blend",
                    "fbx_path": "assets/tree/v2/model.fbx",
                })
            }))
            self.assertTrue(first.version_created)
            self.assertFalse(retry.version_created)
            self.assertEqual(first.entry.id, second.entry.id)
            self.assertEqual([item.source_version for item in second.entry.versions], [1, 2])
            self.assertEqual(service.list("prj_game"), [second.entry])

    def test_legacy_file_record_uses_compatible_defaults(self):
        entry = ProjectAssetEntry.model_validate({
            "id": "libasset_tree",
            "project_id": "prj_game",
            "card_id": "environment",
            "source_asset_id": "asset_tree",
            "title": "大树",
            "source_type": "generated",
            "current_version": 1,
            "versions": [{
                "source_version": 1,
                "dimensions_m": [2, 3, 4],
                "vertex_count": 24,
                "triangle_count": 12,
                "blend_path": "assets/tree/model.blend",
                "preview_path": "assets/tree/preview.glb",
                "fbx_path": "assets/tree/model.fbx",
                "operation": "generate",
            }],
        })

        self.assertIsNone(entry.workspace_id)
        self.assertEqual(entry.versions[0].source_kind, "file")
        self.assertIsNone(entry.versions[0].asset_version_id)
        self.assertIsNone(entry.versions[0].recipe)

    def test_project_workspace_door_recipe_appends_immutable_versions(self):
        with tempfile.TemporaryDirectory(prefix="sceneops-door-catalog-") as directory:
            database = Path(directory) / "catalog.sqlite3"
            service = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            recipe = DoorRecipe()
            created = service.register_version(ProjectAssetRegistration(
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
                    runtime_artifacts=[RuntimeArtifactReference(
                        artifact_id="artifact_front_door_module_1",
                        artifact_type="module",
                        project_relative_path="src/sceneops/assets/front-door.ts",
                        export_name="createFrontDoor",
                    )],
                    operation="recipe-create",
                ),
            ))
            request = UpdateProjectAssetRecipeRequest(
                expected_version=1,
                recipe=DoorRecipe(
                    width_m=1.8,
                    height_m=2.4,
                    thickness_m=0.2,
                    material=DoorMaterial(color_hex="#815B3A", roughness=0.6),
                ),
            )

            updated = service.update_recipe("prj_game", created.entry.id, request)
            retry = service.update_recipe("prj_game", created.entry.id, request)
            with self.assertRaisesRegex(ValueError, "资产版本已更新"):
                service.update_recipe("prj_game", created.entry.id, request.model_copy(update={
                    "recipe": request.recipe.model_copy(update={"width_m": 2.0}),
                }))

            self.assertIsNone(updated.entry.card_id)
            self.assertEqual(updated.entry.workspace_id, "workspace_game")
            self.assertTrue(updated.version_created)
            self.assertFalse(retry.version_created)
            self.assertEqual([item.source_version for item in updated.entry.versions], [1, 2])
            self.assertEqual(updated.entry.versions[-1].dimensions_m, (1.8, 2.4, 0.2))
            self.assertEqual(updated.entry.versions[-1].operation, "recipe-edit")
            self.assertIsNotNone(updated.entry.versions[-1].asset_version_id)
            self.assertIsNone(updated.entry.versions[-1].blend_path)
            reopened = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            self.assertEqual(reopened.get("prj_game", created.entry.id), updated.entry)
            definition = door_recipe_definition()
            self.assertEqual([item.path for item in definition.parameters[:3]],
                             ["width_m", "height_m", "thickness_m"])


if __name__ == "__main__":
    unittest.main()
