import unittest

from render_ops.cache import plan_aov_cache, validate_aov_set
from render_ops.fixtures import mock_aovs, mock_dependency_snapshot, mock_recipe, mock_scene
from render_ops.schemas import AovPass, ExecutionMode


class AovCacheTests(unittest.TestCase):
    def setUp(self):
        self.recipe = mock_recipe()
        self.scene = mock_scene()
        self.snapshot = mock_dependency_snapshot()
        self.aovs = {item.pass_type: item for item in mock_aovs()}

    def plan(self, current=None, previous=None, aovs=None):
        return plan_aov_cache(
            self.recipe,
            self.scene,
            current or self.snapshot,
            self.aovs if aovs is None else aovs,
            self.snapshot if previous is None else previous,
            ExecutionMode.MOCK,
        )

    def test_prompt_only_change_reuses_all_required_aovs(self):
        plan = self.plan()
        self.assertEqual(set(plan.reused_passes), set(self.recipe.required_passes))
        self.assertEqual(plan.capture_passes, [])

    def test_geometry_change_invalidates_all_required_aovs(self):
        plan = self.plan(current=mock_dependency_snapshot(geometry_version="geometry-v9"))
        self.assertEqual(set(plan.capture_passes), set(self.recipe.required_passes))
        self.assertTrue(all(reason == "geometry changed" for reason in plan.reasons.values()))

    def test_camera_change_invalidates_all_required_aovs(self):
        scene = self.scene.model_copy(update={"camera_version": "camera-v5"})
        plan = plan_aov_cache(
            self.recipe,
            scene,
            mock_dependency_snapshot(camera_version="camera-v5"),
            self.aovs,
            self.snapshot,
            ExecutionMode.MOCK,
        )
        self.assertEqual(set(plan.capture_passes), set(self.recipe.required_passes))

    def test_material_change_only_invalidates_material_dependent_passes(self):
        plan = self.plan(current=mock_dependency_snapshot(material_version="material-v4"))
        self.assertEqual(
            set(plan.capture_passes),
            {AovPass.BEAUTY, AovPass.ALBEDO},
        )
        self.assertEqual(
            set(plan.reused_passes),
            {AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID},
        )

    def test_lighting_change_only_invalidates_beauty(self):
        plan = self.plan(current=mock_dependency_snapshot(lighting_version="lighting-v6"))
        self.assertEqual(plan.capture_passes, [AovPass.BEAUTY])

    def test_sample_or_recipe_version_change_invalidates_all_passes(self):
        samples = self.plan(current=mock_dependency_snapshot(samples=128))
        self.assertEqual(set(samples.capture_passes), set(self.recipe.required_passes))
        version = self.plan(
            current=mock_dependency_snapshot(recipe_version="1.0.1")
        )
        self.assertEqual(set(version.capture_passes), set(self.recipe.required_passes))

    def test_missing_cached_pass_is_captured(self):
        cached = dict(self.aovs)
        del cached[AovPass.NORMAL]
        plan = self.plan(aovs=cached)
        self.assertEqual(plan.capture_passes, [AovPass.NORMAL])

    def test_mock_aov_cannot_be_relabelled_as_cached_real(self):
        plan = plan_aov_cache(
            self.recipe,
            self.scene,
            self.snapshot,
            self.aovs,
            self.snapshot,
            ExecutionMode.CACHED,
        )
        self.assertEqual(set(plan.capture_passes), set(self.recipe.required_passes))
        self.assertTrue(
            all(reason == "cached pass execution mode is incompatible" for reason in plan.reasons.values())
        )

    def test_cached_real_aovs_are_reusable_without_rerender(self):
        cached = {}
        for pass_type, aov in self.aovs.items():
            artifact = aov.artifact.model_copy(update={"execution_mode": ExecutionMode.CACHED})
            cached[pass_type] = aov.model_copy(update={"artifact": artifact})
        plan = plan_aov_cache(
            self.recipe,
            self.scene,
            self.snapshot,
            cached,
            self.snapshot,
            ExecutionMode.CACHED,
        )
        self.assertEqual(set(plan.reused_passes), set(self.recipe.required_passes))
        self.assertEqual(plan.capture_passes, [])

    def test_capture_validation_rejects_invalid_or_missing_aov(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            validate_aov_set(
                self.recipe, self.scene, 4, 4, mock_aovs()[:-1], ExecutionMode.MOCK
            )
        wrong_size = mock_aovs()
        wrong_size[0] = wrong_size[0].model_copy(update={"width": 8})
        with self.assertRaisesRegex(ValueError, "dimensions"):
            validate_aov_set(
                self.recipe, self.scene, 4, 4, wrong_size, ExecutionMode.MOCK
            )

    def test_public_capture_validation_rejects_mode_laundering(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            validate_aov_set(
                self.recipe, self.scene, 4, 4, mock_aovs(), ExecutionMode.LIVE
            )


if __name__ == "__main__":
    unittest.main()
