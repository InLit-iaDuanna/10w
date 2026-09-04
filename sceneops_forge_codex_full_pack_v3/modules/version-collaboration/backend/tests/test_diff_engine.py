from __future__ import annotations

import unittest

from pydantic import ValidationError

from version_collaboration.base import ExecutionMode
from version_collaboration.diff_engine import FourLayerDiffEngine
from version_collaboration.diff_models import DiffState, SemanticEntity

from support import behavior_pair, semantic_pair, visual_pair


class FourLayerDiffEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FourLayerDiffEngine()

    def test_semantic_diff_uses_stable_identity_and_property_paths(self) -> None:
        before, after = semantic_pair()

        layer, conflicts = self.engine.compare_semantic(before, after)

        self.assertEqual(layer.state, DiffState.SUCCEEDED)
        self.assertEqual(len(layer.changes), 1)
        self.assertEqual(layer.changes[0].entity_id, "sceneobject_door_01")
        self.assertEqual(layer.changes[0].path, "/locked")
        self.assertEqual((layer.changes[0].before, layer.changes[0].after), (True, False))
        self.assertEqual(conflicts, [])

    def test_deleted_mutation_target_is_a_blocking_conflict(self) -> None:
        before, _ = semantic_pair()

        layer, conflicts = self.engine.compare_semantic(
            before, (), target_ids=("sceneobject_door_01",)
        )

        self.assertEqual(layer.state, DiffState.SUCCEEDED)
        self.assertEqual(conflicts[0].code.value, "deleted_target")
        self.assertTrue(conflicts[0].blocking)

    def test_semantic_schema_mismatch_is_not_reported_as_empty(self) -> None:
        before, after = semantic_pair()
        changed = after[0].model_copy(update={"schema_version": 2})

        layer, conflicts = self.engine.compare_semantic(before, (changed,))

        self.assertEqual(layer.state, DiffState.INCOMPATIBLE)
        self.assertEqual(layer.mode, ExecutionMode.BLOCKED)
        self.assertEqual(conflicts[0].code.value, "incompatible_schema")

    def test_missing_semantic_provider_is_unavailable_not_empty(self) -> None:
        layer, conflicts = self.engine.compare_semantic(None, None)

        self.assertEqual(layer.state, DiffState.UNAVAILABLE)
        self.assertEqual(layer.mode, ExecutionMode.PLANNED)
        self.assertEqual(conflicts, [])

    def test_fixed_camera_visual_diff_reports_objective_pixel_delta(self) -> None:
        before, after = visual_pair()

        layer, conflicts = self.engine.compare_visual(before, after)

        self.assertEqual(layer.state, DiffState.SUCCEEDED)
        self.assertEqual(layer.changed_samples, 2)
        self.assertEqual(layer.sample_count, 4)
        self.assertEqual(layer.mean_absolute_error, 3.0)
        self.assertEqual(layer.maximum_absolute_error, 10)
        self.assertEqual(conflicts, [])

    def test_visual_descriptor_mismatch_is_incompatible(self) -> None:
        before, after = visual_pair()
        changed = after.model_copy(update={"renderer_version": "renderer-fixture-v2"})

        layer, conflicts = self.engine.compare_visual(before, changed)

        self.assertEqual(layer.state, DiffState.INCOMPATIBLE)
        self.assertEqual(layer.mode, ExecutionMode.BLOCKED)
        self.assertEqual(len(conflicts), 1)

    def test_behavior_diff_reports_delta_without_claiming_improvement(self) -> None:
        before, after = behavior_pair()

        layer, conflicts = self.engine.compare_behavior(before, after)

        self.assertEqual(layer.state, DiffState.SUCCEEDED)
        self.assertEqual({item.category for item in layer.changes}, {"objective", "assertion", "step"})
        self.assertNotIn("improved", layer.model_dump_json())
        self.assertEqual(conflicts, [])

    def test_behavior_configuration_mismatch_is_incompatible(self) -> None:
        before, after = behavior_pair()
        changed = after.model_copy(update={"seed": 99})

        layer, conflicts = self.engine.compare_behavior(before, changed)

        self.assertEqual(layer.state, DiffState.INCOMPATIBLE)
        self.assertEqual(len(conflicts), 1)

    def test_visual_capture_rejects_wrong_pixel_count(self) -> None:
        before, _ = visual_pair()
        payload = before.model_dump()
        payload["pixels"] = (0,)

        with self.assertRaises(ValidationError):
            type(before).model_validate(payload)


if __name__ == "__main__":
    unittest.main()
