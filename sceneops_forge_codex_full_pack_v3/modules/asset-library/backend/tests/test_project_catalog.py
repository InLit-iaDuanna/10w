import tempfile
import unittest
from pathlib import Path

from asset_library import (
    ProjectAssetCatalogService,
    ProjectAssetRegistration,
    ProjectAssetVersion,
    SqliteProjectAssetRepository,
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


if __name__ == "__main__":
    unittest.main()
