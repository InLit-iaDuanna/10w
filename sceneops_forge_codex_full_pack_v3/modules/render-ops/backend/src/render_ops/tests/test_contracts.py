import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from render_ops.fixtures import FIXTURE_TIME, mock_manifest, mock_recipe, mock_scene
from render_ops.schema_export import schema_path
from render_ops.schemas import (
    AovPass,
    ExecutionMode,
    RenderManifest,
    RenderRecipe,
    RecipeKind,
)


MODULE_ROOT = Path(__file__).resolve().parents[4]


class RenderManifestContractTests(unittest.TestCase):
    def test_committed_fixture_validates_and_carries_complete_provenance(self):
        path = MODULE_ROOT / "contracts/examples/render-manifest.mock.json"
        manifest = RenderManifest.model_validate_json(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest, mock_manifest())
        provenance = manifest.variants[0].provenance
        self.assertTrue(provenance.workflow_reference)
        self.assertEqual(len(provenance.workflow_checksum_sha256), 64)
        self.assertTrue(provenance.model_reference)
        self.assertEqual(len(provenance.model_checksum_sha256), 64)
        self.assertGreaterEqual(provenance.seed, 0)
        self.assertTrue(provenance.prompt)
        self.assertEqual(manifest.job.execution_mode, ExecutionMode.MOCK)

    def test_generated_schema_is_current(self):
        committed = json.loads(schema_path().read_text(encoding="utf-8"))
        self.assertEqual(committed, RenderManifest.model_json_schema())
        self.assertEqual(committed["title"], "RenderManifest")
        self.assertIn("$defs", committed)

    def test_missing_aov_is_rejected(self):
        payload = mock_manifest().model_dump(mode="python")
        payload["aovs"] = payload["aovs"][:-1]
        with self.assertRaisesRegex(ValidationError, "missing required AOV"):
            RenderManifest.model_validate(payload)

    def test_mismatched_camera_is_rejected(self):
        payload = mock_manifest().model_dump(mode="python")
        payload["aovs"][0]["scene"]["camera_version"] = "camera-other"
        with self.assertRaisesRegex(ValidationError, "scene/camera"):
            RenderManifest.model_validate(payload)

    def test_material_variant_requires_material_id(self):
        recipe = mock_recipe().model_dump(mode="python")
        recipe.update(kind=RecipeKind.MATERIAL_VARIANT)
        with self.assertRaisesRegex(ValidationError, "material_id"):
            RenderRecipe.model_validate(recipe)

    def test_workflow_reference_requires_checksum(self):
        recipe = mock_recipe().model_dump(mode="python")
        recipe["workflow_checksum_sha256"] = None
        with self.assertRaisesRegex(ValidationError, "supplied together"):
            RenderRecipe.model_validate(recipe)

    def test_all_truthful_execution_modes_round_trip(self):
        for mode in ExecutionMode:
            self.assertEqual(ExecutionMode(mode.value), mode)
        self.assertEqual(
            {item.value for item in ExecutionMode},
            {"live", "cached", "mock", "planned", "blocked"},
        )

    def test_manifest_rejects_non_utc_timestamp(self):
        payload = mock_manifest().model_dump(mode="python")
        payload["created_at"] = FIXTURE_TIME.replace(tzinfo=None)
        with self.assertRaisesRegex(ValidationError, "UTC"):
            RenderManifest.model_validate(payload)

    def test_manifest_requires_exact_protected_region_evidence(self):
        payload = mock_manifest().model_dump(mode="python")
        payload["comparisons"][0]["protected_regions"] = []
        payload["validations"][0]["protected_regions_passed"] = True
        with self.assertRaisesRegex(ValidationError, "exact protected-region"):
            RenderManifest.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
