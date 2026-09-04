import unittest

from pydantic import ValidationError

from render_ops.fixtures import (
    FIXTURE_TIME,
    MODEL_CHECKSUM,
    mock_artifact,
    mock_dependency_snapshot,
    mock_recipe,
    mock_scene,
)
from render_ops.jobs import RenderJobRepository, RenderQueue
from render_ops.schemas import (
    AovPass,
    ApprovalState,
    ArtifactApprovalState,
    ExecutionMode,
    RenderBrief,
    RenderJobState,
    WorkflowProvenance,
    WritebackOperation,
    WritebackProperty,
    WritebackTarget,
)
from render_ops.service import RenderOpsService
from render_ops.writeback import approve_writeback


class RenderOpsFlowTests(unittest.TestCase):
    def setUp(self):
        self.service = RenderOpsService()
        self.scene = mock_scene()
        self.recipe = mock_recipe()
        self.brief = RenderBrief(
            brief_id="rbrief_flow",
            scene=self.scene,
            intent="Increase target visibility while preserving the door.",
            target_object_ids=["sceneops_light_porch"],
            protected_regions=[],
            requested_by="usr_test",
            created_at=FIXTURE_TIME,
        )

    def make_started_job(self):
        job = self.service.create_job(
            job_id="rjob_flow",
            brief=self.brief,
            recipe=self.recipe,
            dependency_snapshot=mock_dependency_snapshot(),
            existing_aovs={},
            previous_snapshot=None,
            execution_mode=ExecutionMode.MOCK,
            created_at=FIXTURE_TIME,
        )
        repository = RenderJobRepository([job])
        queue = RenderQueue(repository, clock=lambda: FIXTURE_TIME)
        return queue.start(job.job_id)

    def make_variant(self, job):
        return self.service.create_variant(
            variant_id="rvariant_flow",
            job=job,
            recipe=self.recipe,
            output=mock_artifact(
                "variant_flow", "render.variant", ArtifactApprovalState.PENDING
            ),
            provenance=WorkflowProvenance(
                provider="deterministic-fixture",
                workflow_reference=self.recipe.workflow_reference,
                workflow_checksum_sha256=self.recipe.workflow_checksum_sha256,
                model_reference="fixture/lookdev-model-v1",
                model_checksum_sha256=MODEL_CHECKSUM,
                seed=12,
                prompt="reveal the target",
                negative_prompt="camera move",
                parameters={},
                adapter_version="0.1.0",
            ),
            constraint_passes=[AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID],
        )

    def test_mock_flow_requires_variant_and_changeset_approval(self):
        job = self.make_started_job()
        self.assertEqual(job.cache_plan.capture_passes, self.recipe.required_passes)
        variant = self.make_variant(job)
        self.assertEqual(variant.approval_state, ApprovalState.PENDING)
        operation = WritebackOperation(
            target=WritebackTarget.BLENDER,
            target_object_id="sceneops_light_porch",
            property=WritebackProperty.LIGHT_INTENSITY,
            previous_value=600.0,
            proposed_value=850.0,
        )
        with self.assertRaisesRegex(PermissionError, "approved variant"):
            self.service.propose_writeback(
                proposal_id="proposal-flow",
                brief=self.brief,
                variant=variant,
                operations=[operation],
                rationale="target visibility",
                expected_result="target is visible",
                risk="low",
                validation_plan="fixed camera render",
                rollback_plan="restore 600",
            )

        approved_variant = self.service.approve_variant(
            variant, approved_by="usr_reviewer", approved_at=FIXTURE_TIME
        )
        altered_variant = approved_variant.model_copy(
            update={"provenance": approved_variant.provenance.model_copy(
                update={"prompt": "unapproved replacement"}
            )}
        )
        with self.assertRaisesRegex(ValidationError, "approval snapshot"):
            self.service.propose_writeback(
                proposal_id="proposal-altered-variant",
                brief=self.brief,
                variant=altered_variant,
                operations=[operation],
                rationale="target visibility",
                expected_result="target is visible",
                risk="low",
                validation_plan="fixed camera render",
                rollback_plan="restore 600",
            )
        proposal = self.service.propose_writeback(
            proposal_id="proposal-flow",
            brief=self.brief,
            variant=approved_variant,
            operations=[operation],
            rationale="target visibility",
            expected_result="target is visible",
            risk="low",
            validation_plan="fixed camera render",
            rollback_plan="restore 600",
        )
        self.assertEqual(proposal.approval_state, ApprovalState.PENDING)
        approved = approve_writeback(
            proposal,
            changeset_id="changeset-flow",
            approved_by="usr_reviewer",
            approved_at=FIXTURE_TIME,
        )
        self.assertEqual(approved.approval_state, ApprovalState.APPROVED)
        self.assertEqual(approved.changeset_id, "changeset-flow")

        outside = operation.model_copy(update={"target_object_id": "sceneops_door_home"})
        with self.assertRaisesRegex(PermissionError, "render brief"):
            self.service.propose_writeback(
                proposal_id="proposal-outside-brief",
                brief=self.brief,
                variant=approved_variant,
                operations=[outside],
                rationale="out of scope",
                expected_result="not allowed",
                risk="high",
                validation_plan="fixed camera render",
                rollback_plan="restore",
            )

    def test_offline_job_is_truthfully_blocked(self):
        queued = self.service.create_job(
            job_id="rjob_offline",
            brief=self.brief,
            recipe=self.recipe,
            dependency_snapshot=mock_dependency_snapshot(),
            existing_aovs={},
            previous_snapshot=None,
            execution_mode=ExecutionMode.PLANNED,
            created_at=FIXTURE_TIME,
        )
        blocked = self.service.block_job(
            queued,
            code="INTEGRATION_OFFLINE",
            message="ComfyUI is not connected.",
            retryable=True,
            updated_at=FIXTURE_TIME,
        )
        self.assertEqual(blocked.state, RenderJobState.FAILED)
        self.assertEqual(blocked.execution_mode, ExecutionMode.BLOCKED)
        self.assertEqual(blocked.failure.code, "INTEGRATION_OFFLINE")

    def test_variant_rejects_recipe_workflow_provenance_mismatch(self):
        job = self.make_started_job()
        provenance = WorkflowProvenance(
            provider="deterministic-fixture",
            workflow_reference="untrusted.workflow",
            workflow_checksum_sha256="f" * 64,
            model_reference="fixture/model",
            model_checksum_sha256=MODEL_CHECKSUM,
            seed=1,
            prompt="test",
            negative_prompt="",
            parameters={},
            adapter_version="0.1.0",
        )
        with self.assertRaisesRegex(ValueError, "workflow reference"):
            self.service.create_variant(
                variant_id="rvariant_bad",
                job=job,
                recipe=self.recipe,
                output=mock_artifact(
                    "bad_variant", "render.variant", ArtifactApprovalState.PENDING
                ),
                provenance=provenance,
                constraint_passes=[AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID],
            )


if __name__ == "__main__":
    unittest.main()
