import json
import unittest
from pathlib import Path

from render_ops.capture import (
    AovCaptureWorker,
    CaptureCancellation,
    CaptureCapabilities,
    CapturePreview,
    CaptureResult,
)
from render_ops.fixtures import mock_aovs, mock_recipe, mock_scene
from render_ops.recipes import instantiate_recipe, load_recipe_catalog
from render_ops.schemas import AovPass, ExecutionMode, RecipeKind, RenderCaptureCommand


MODULE_ROOT = Path(__file__).resolve().parents[4]


class FixtureCaptureAdapter:
    def __init__(self, *, accepted=True, extra_pass=False):
        self.accepted = accepted
        self.extra_pass = extra_pass
        self.calls = []

    def capabilities(self):
        self.calls.append("capabilities")
        return CaptureCapabilities(
            adapter_id="fixture.capture",
            adapter_version="1.0.0",
            command_ids=["blender.render.capture_aov"],
            supported_passes=list(AovPass),
            supports_dry_run=True,
            supports_cancellation=True,
            execution_mode=ExecutionMode.MOCK,
        )

    def dry_run(self, command):
        self.calls.append("dry_run")
        return CapturePreview(
            render_job_id=command.render_job_id,
            accepted=self.accepted,
            pass_count=len(command.passes),
            estimated_output_count=len(command.passes),
            execution_mode=ExecutionMode.MOCK,
            reason="fixture policy rejection" if not self.accepted else "",
        )

    def execute(self, command, cancellation, on_progress):
        self.calls.append("execute")
        if cancellation.cancelled:
            raise RuntimeError("capture cancelled")
        on_progress(0.5, "capturing deterministic AOVs")
        selected = [item for item in mock_aovs() if item.pass_type in command.passes]
        return CaptureResult(
            render_job_id=command.render_job_id,
            aovs=selected,
            adapter_id="fixture.capture",
            adapter_version="1.0.0",
            execution_mode=ExecutionMode.MOCK,
        )


def capture_command():
    return RenderCaptureCommand(
        command_id="blender.render.capture_aov",
        render_job_id="rjob_capture",
        scene=mock_scene(),
        passes=mock_recipe().required_passes,
        width=4,
        height=4,
        renderer_version="fixture-renderer-1.0.0",
        samples=1,
        execution_mode="mock",
    )


class CaptureAndRecipeTests(unittest.TestCase):
    def test_capture_worker_dry_runs_and_validates_all_passes(self):
        adapter = FixtureCaptureAdapter()
        progress = []
        result = AovCaptureWorker().run(
            command=capture_command(),
            recipe=mock_recipe(),
            adapter=adapter,
            cancellation=CaptureCancellation(),
            on_progress=lambda value, message: progress.append((value, message)),
        )
        self.assertEqual(adapter.calls, ["capabilities", "dry_run", "execute"])
        self.assertEqual({item.pass_type for item in result.aovs}, set(mock_recipe().required_passes))
        self.assertEqual(progress, [(0.5, "capturing deterministic AOVs")])

    def test_capture_worker_rejects_unallowlisted_command(self):
        command = capture_command().model_copy(update={"command_id": "unity.render.capture_aov"})
        with self.assertRaisesRegex(PermissionError, "not allowlisted"):
            AovCaptureWorker().run(
                command=command,
                recipe=mock_recipe(),
                adapter=FixtureCaptureAdapter(),
                cancellation=CaptureCancellation(),
                on_progress=lambda _value, _message: None,
            )

    def test_capture_worker_honors_preflight_cancellation_and_rejection(self):
        cancellation = CaptureCancellation()
        cancellation.cancel()
        with self.assertRaisesRegex(RuntimeError, "cancelled before dry-run"):
            AovCaptureWorker().run(
                command=capture_command(),
                recipe=mock_recipe(),
                adapter=FixtureCaptureAdapter(),
                cancellation=cancellation,
                on_progress=lambda _value, _message: None,
            )
        with self.assertRaisesRegex(PermissionError, "fixture policy rejection"):
            AovCaptureWorker().run(
                command=capture_command(),
                recipe=mock_recipe(),
                adapter=FixtureCaptureAdapter(accepted=False),
                cancellation=CaptureCancellation(),
                on_progress=lambda _value, _message: None,
            )

    def test_catalog_contains_all_portable_recipe_kinds(self):
        catalog = load_recipe_catalog()
        self.assertEqual(
            {item.kind for item in catalog.recipes},
            {
                RecipeKind.ASSET_TURNTABLE,
                RecipeKind.MATERIAL_VARIANT,
                RecipeKind.LIGHTING_VISIBILITY,
                RecipeKind.FIXED_CAMERA_REGRESSION,
                RecipeKind.MARKETING_STILL,
            },
        )
        self.assertTrue(
            all(item.execution_requirement == "live_or_cached_real" for item in catalog.recipes)
        )

    def test_same_recipe_instantiates_for_warehouse_escape_without_source_change(self):
        example = json.loads(
            (MODULE_ROOT / "contracts/examples/warehouse-escape-render-request.json").read_text(
                encoding="utf-8"
            )
        )
        recipe = instantiate_recipe(
            example["recipe_id"],
            workflow_reference=example["workflow_reference"],
            workflow_checksum_sha256=example["workflow_checksum_sha256"],
            parameters=example["parameters"],
        )
        self.assertEqual(recipe.kind, RecipeKind.LIGHTING_VISIBILITY)
        self.assertEqual(recipe.parameters["target_object_ids"], ["sceneops_exit_switch"])

    def test_recipe_rejects_undeclared_project_specific_parameter(self):
        with self.assertRaisesRegex(ValueError, "undeclared portable parameters"):
            instantiate_recipe(
                "render.lighting-visibility",
                workflow_reference="lookdev.lighting-visibility.v1",
                workflow_checksum_sha256="a" * 64,
                parameters={"hardcoded_game_name": "Warehouse Escape"},
            )


if __name__ == "__main__":
    unittest.main()
