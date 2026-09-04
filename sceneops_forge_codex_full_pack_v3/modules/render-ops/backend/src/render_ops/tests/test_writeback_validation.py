import unittest

from render_ops.fixtures import FIXTURE_TIME, mock_manifest
from render_ops.schemas import (
    ExecutionMode,
    WritebackOperation,
    WritebackProperty,
    WritebackTarget,
)
from pydantic import ValidationError
from render_ops.validation import (
    compare_pixel_bytes,
    compare_protected_region,
    make_comparison,
    validate_writeback_result,
)
from render_ops.writeback import (
    ChangePreview,
    WritebackCapabilities,
    WritebackExecution,
    WritebackExecutor,
    WritebackResult,
    approve_writeback,
)


class RecordingAdapter:
    def __init__(self, extra_object=False):
        self.calls = []
        self.extra_object = extra_object
        self.executions = {}

    def capabilities(self):
        self.calls.append("capabilities")
        return WritebackCapabilities(
            adapter_id="fixture.blender",
            adapter_version="1.0.0",
            target=WritebackTarget.BLENDER,
            supported_properties=[
                WritebackProperty.LIGHT_INTENSITY,
                WritebackProperty.MATERIAL_SCALAR,
            ],
            named_parameters={WritebackProperty.MATERIAL_SCALAR: ["roughness"]},
            supports_dry_run=True,
            supports_validation_capture=True,
            supports_idempotent_changesets=True,
        )

    def dry_run(self, proposal):
        self.calls.append("dry_run")
        return ChangePreview(
            proposal_id=proposal.proposal_id,
            accepted=True,
            summaries=["light intensity: 600 -> 850"],
            target_object_ids=[item.target_object_id for item in proposal.operations],
            base_scene_version=proposal.base_scene_version,
            execution_mode=ExecutionMode.MOCK,
        )

    def apply(self, proposal):
        self.calls.append("apply")
        changed = [proposal.operations[0].target_object_id]
        if self.extra_object:
            changed.append("sceneops_unapproved")
        return WritebackResult(
            proposal_id=proposal.proposal_id,
            changeset_id=proposal.changeset_id,
            target=WritebackTarget.BLENDER,
            resulting_scene_version="scene-v18",
            changed_object_ids=changed,
            execution_mode=ExecutionMode.MOCK,
            adapter_id="fixture.blender",
            adapter_version="1.0.0",
            rollback_reference="fixture-rollback-1",
        )

    def capture_validation(self, proposal, result):
        self.calls.append("capture_validation")
        comparison = mock_manifest().comparisons[0].model_copy(
            update={
                "comparison_id": "capture:" + result.changeset_id,
                "scene": proposal.scene,
                "changed_object_ids": result.changed_object_ids,
                "execution_mode": result.execution_mode,
            }
        )
        execution = WritebackExecution(result=result, validation_capture=comparison)
        self.executions[result.changeset_id] = execution
        return comparison

    def find_execution(self, changeset_id):
        self.calls.append("find_execution")
        return self.executions.get(changeset_id)


class FixtureApprovalVerifier:
    def verify(self, proposal):
        if not proposal.changeset_id or proposal.approved_by != "usr_fixture_reviewer":
            raise PermissionError("fixture ChangeSet approval is not authoritative")


def executor():
    return WritebackExecutor(approval_verifier=FixtureApprovalVerifier())


class WritebackValidationTests(unittest.TestCase):
    def test_writeback_requires_approved_changeset(self):
        proposal = mock_manifest().writeback_proposals[0].model_copy(
            update={
                "approval_state": "pending",
                "changeset_id": None,
                "approved_by": None,
                "approved_at": None,
                "approval_snapshot": None,
            }
        )
        with self.assertRaisesRegex(PermissionError, "approved ChangeSet"):
            executor().apply(proposal, RecordingAdapter())

    def test_approved_writeback_dry_runs_then_applies(self):
        proposal = mock_manifest().writeback_proposals[0]
        adapter = RecordingAdapter()
        execution = executor().apply(proposal, adapter)
        self.assertEqual(
            adapter.calls,
            ["capabilities", "find_execution", "dry_run", "apply", "capture_validation"],
        )
        self.assertEqual(execution.result.execution_mode, ExecutionMode.MOCK)
        self.assertEqual(execution.result.changed_object_ids, ["sceneops_light_porch"])

    def test_parameter_allowlist_rejects_unapproved_name(self):
        proposal = mock_manifest().writeback_proposals[0]
        payload = proposal.model_dump(mode="python")
        payload.update(
            changeset_id=None,
            approval_state="pending",
            approved_by=None,
            approved_at=None,
            approval_snapshot=None,
        )
        payload["operations"] = [
            WritebackOperation(
                target=WritebackTarget.BLENDER,
                target_object_id="sceneops_light_porch",
                property=WritebackProperty.MATERIAL_SCALAR,
                parameter_name="arbitrary_shader_expression",
                previous_value=0.2,
                proposed_value=1.0,
            )
        ]
        payload["impact_scope"] = ["sceneops_light_porch"]
        from render_ops.schemas import WritebackProposal

        pending = WritebackProposal.model_validate(payload)
        unsafe = approve_writeback(
            pending,
            changeset_id="changeset-unsafe-name",
            approved_by="usr_fixture_reviewer",
            approved_at=FIXTURE_TIME,
        )
        with self.assertRaisesRegex(PermissionError, "not allowlisted"):
            executor().apply(unsafe, RecordingAdapter())

    def test_writeback_values_are_typed_and_texture_paths_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "numeric value"):
            WritebackOperation(
                target=WritebackTarget.BLENDER,
                target_object_id="sceneops_light_porch",
                property=WritebackProperty.LIGHT_INTENSITY,
                previous_value=600.0,
                proposed_value="run_expression()",
            )
        with self.assertRaisesRegex(ValidationError, "stable artifact ID"):
            WritebackOperation(
                target=WritebackTarget.BLENDER,
                target_object_id="sceneops_light_porch",
                property=WritebackProperty.PBR_TEXTURE,
                previous_value=None,
                proposed_value="../textures/unsafe.png",
            )

    def test_adapter_cannot_expand_approved_object_scope(self):
        proposal = mock_manifest().writeback_proposals[0]
        with self.assertRaisesRegex(PermissionError, "outside the approved scope"):
            executor().apply(proposal, RecordingAdapter(extra_object=True))

    def test_fixed_camera_diff_is_deterministic_and_not_quality_score(self):
        metrics = compare_pixel_bytes(bytes([0, 10, 20, 30]), bytes([0, 20, 20, 50]))
        self.assertAlmostEqual(metrics.mean_absolute_difference, 30 / (4 * 255))
        self.assertEqual(metrics.changed_pixel_ratio, 0.5)
        self.assertFalse(metrics.artistic_quality_measured)

    def test_protected_region_and_geometry_checks(self):
        manifest = mock_manifest()
        protected = compare_protected_region(
            "region_home_door",
            bytes([0, 0, 0, 0]),
            bytes([0, 0, 255, 0]),
            [True, True, False, False],
            0.0,
        )
        comparison = make_comparison(
            comparison_id="compare-validation-test",
            before_artifact_id="before",
            after_artifact_id="after",
            scene=manifest.brief.scene,
            before=bytes([0, 0, 0, 0]),
            after=bytes([0, 0, 255, 0]),
            protected_regions=[protected],
            changed_object_ids=["sceneops_light_porch"],
            execution_mode=ExecutionMode.MOCK,
        )
        passed = validate_writeback_result(
            validation_id="validation-pass",
            proposal=manifest.writeback_proposals[0],
            brief=manifest.brief,
            comparison=comparison,
            deterministic_recipe_id="render.fixed-camera-regression",
            geometry_revision_before="geometry-v8",
            geometry_revision_after="geometry-v8",
            camera_revision_before="camera-v4",
            camera_revision_after="camera-v4",
            execution_mode=ExecutionMode.MOCK,
            completed_at=FIXTURE_TIME,
        )
        self.assertTrue(passed.passed)

        failed = validate_writeback_result(
            validation_id="validation-fail",
            proposal=manifest.writeback_proposals[0],
            brief=manifest.brief,
            comparison=comparison.model_copy(
                update={"changed_object_ids": ["sceneops_unapproved"]}
            ),
            deterministic_recipe_id="render.fixed-camera-regression",
            geometry_revision_before="geometry-v8",
            geometry_revision_after="geometry-v9",
            camera_revision_before="camera-v4",
            camera_revision_after="camera-v5",
            execution_mode=ExecutionMode.MOCK,
            completed_at=FIXTURE_TIME,
        )
        self.assertFalse(failed.passed)
        self.assertEqual(len(failed.failures), 3)

    def test_approval_snapshot_rejects_post_approval_operation_replacement(self):
        proposal = mock_manifest().writeback_proposals[0]
        replacement = WritebackOperation(
            target=WritebackTarget.BLENDER,
            target_object_id="sceneops_light_porch",
            property=WritebackProperty.LIGHT_INTENSITY,
            previous_value=600.0,
            proposed_value=900.0,
        )
        mutated = proposal.model_copy(update={"operations": (replacement,)})
        with self.assertRaisesRegex(ValidationError, "approval snapshot"):
            executor().apply(mutated, RecordingAdapter())
        renamed = proposal.model_copy(update={"changeset_id": "changeset-replaced"})
        with self.assertRaisesRegex(ValidationError, "approval snapshot"):
            executor().apply(renamed, RecordingAdapter())

    def test_protected_region_evidence_cannot_be_omitted_or_forged(self):
        manifest = mock_manifest()
        empty = manifest.comparisons[0].model_copy(update={"protected_regions": []})
        result = validate_writeback_result(
            validation_id="missing-regions",
            proposal=manifest.writeback_proposals[0],
            brief=manifest.brief,
            comparison=empty,
            deterministic_recipe_id="render.fixed-camera-regression",
            geometry_revision_before="geometry-v8",
            geometry_revision_after="geometry-v8",
            camera_revision_before="camera-v4",
            camera_revision_after="camera-v4",
            execution_mode=ExecutionMode.MOCK,
            completed_at=FIXTURE_TIME,
        )
        self.assertFalse(result.passed)
        with self.assertRaises(ValidationError):
            from render_ops.schemas import ProtectedRegionResult

            ProtectedRegionResult(
                region_id="region_home_door",
                changed_pixel_ratio=1.0,
                threshold=0.0,
                passed=True,
            )

    def test_repeated_changeset_uses_durable_adapter_result(self):
        proposal = mock_manifest().writeback_proposals[0]
        adapter = RecordingAdapter()
        first = executor().apply(proposal, adapter)
        second = executor().apply(proposal, adapter)
        self.assertFalse(first.reused_changeset)
        self.assertTrue(second.reused_changeset)
        self.assertEqual(adapter.calls.count("apply"), 1)


if __name__ == "__main__":
    unittest.main()
