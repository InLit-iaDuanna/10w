import unittest

from pydantic import ValidationError

from sceneops_character_animation.adapter import (
    CancellationToken,
    DeterministicMockCharacterToolAdapter,
)
from sceneops_character_animation.offline_adapter import OfflineCharacterToolAdapter
from sceneops_character_animation.common import ApprovalState, ExecutionMode
from sceneops_character_animation.errors import (
    AdapterTimeoutError,
    ApprovalRequiredError,
    IntegrationOfflineError,
    OperationCancelledError,
    InvalidVersionError,
)
from sceneops_character_animation.fixtures import fixed_preview_camera, remember_home_bundle
from sceneops_character_animation.operation_models import (
    PreviewCaptureRequest,
    UnityCharacterMapping,
    UnityMappingExecutionRequest,
    UnityMappingProposalRequest,
)
from sceneops_character_animation.service import CharacterAnimationService


def preview_request():
    bundle = remember_home_bundle()
    return PreviewCaptureRequest(
        request_id="adapter_preview",
        character=bundle.character,
        rig=bundle.rig,
        clip=bundle.clips[0],
        camera=fixed_preview_camera(),
    )


class AdapterContractTests(unittest.TestCase):
    def test_offline_adapter_is_truthful_and_structured(self):
        adapter = OfflineCharacterToolAdapter()
        health = adapter.health_check()
        self.assertFalse(health.available)
        self.assertEqual(health.mode, ExecutionMode.BLOCKED)
        with self.assertRaises(IntegrationOfflineError) as context:
            adapter.capture_preview(preview_request(), "req_offline", 10, CancellationToken())
        self.assertEqual(context.exception.code, "INTEGRATION_OFFLINE")

    def test_mock_adapter_supports_cancellation_timeout_and_idempotency(self):
        adapter = DeterministicMockCharacterToolAdapter()
        request = preview_request()
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(OperationCancelledError):
            adapter.capture_preview(request, "req_cancel", 10, token)
        with self.assertRaises(AdapterTimeoutError):
            adapter.capture_preview(request, "req_timeout", 31, CancellationToken())
        first = adapter.capture_preview(request, "req_same", 10, CancellationToken())
        second = adapter.capture_preview(request, "req_same", 10, CancellationToken())
        self.assertEqual(first, second)
        self.assertEqual([event.state for event in adapter.progress_events("req_same")], ["planned", "running", "succeeded"])
        self.assertEqual(adapter.structured_logs("req_same")[-1].code, "FIXTURE_EXECUTION_SUCCEEDED")
        self.assertTrue(all(item.passed for item in adapter.validate_preview(first)))
        self.assertEqual(adapter.dry_run_preview(request).mode, ExecutionMode.PLANNED)
        self.assertTrue(adapter.rollback("snapshot_fixture").restored)


class UnityMappingTests(unittest.TestCase):
    def setUp(self):
        self.bundle = remember_home_bundle()
        self.service = CharacterAnimationService(adapter=DeterministicMockCharacterToolAdapter())
        self.proposal = self.service.propose_unity_mapping(
            UnityMappingProposalRequest(
                request_id="unity_homekeeper_v1",
                bundle=self.bundle,
                unity_prefab_id="prefab_homekeeper_v1",
                unity_game_object_sceneops_id="sceneobj_player_homekeeper",
                unity_animator_controller_id="animator_homekeeper_v1",
                base_unity_version="unity_project_12",
            )
        )

    def test_mapping_proposal_preserves_distinct_identity_and_is_planned(self):
        mapping = self.proposal.mapping
        self.assertEqual(self.proposal.mode, ExecutionMode.PLANNED)
        self.assertEqual(self.proposal.changeset.approval_state, ApprovalState.WAITING_APPROVAL)
        self.assertNotEqual(mapping.character_id, mapping.unity_prefab_id)
        self.assertNotEqual(mapping.unity_prefab_id, mapping.unity_game_object_sceneops_id)
        self.assertEqual(mapping.changeset_id, self.proposal.changeset.changeset_id)
        self.assertEqual(
            mapping.source_provenance_artifact_ids,
            ["rig_homekeeper_v1", "skin_homekeeper_v1", "clip_idle_v1", "clip_walk_v1"],
        )
        self.assertEqual(len(mapping.source_provenance_artifact_ids), len(mapping.source_provenance_checksums))

    def test_execution_requires_approved_changeset(self):
        with self.assertRaises(ApprovalRequiredError):
            self.service.execute_unity_mapping(
                UnityMappingExecutionRequest(
                    request_id="unity_apply_denied",
                    mapping=self.proposal.mapping,
                    changeset=self.proposal.changeset,
                )
            )

    def test_approved_mock_execution_is_idempotent_and_never_live(self):
        approved = self.proposal.changeset.model_copy(update={"approval_state": ApprovalState.APPROVED})
        request = UnityMappingExecutionRequest(
            request_id="unity_apply_fixture",
            mapping=self.proposal.mapping,
            changeset=approved,
        )
        first = self.service.execute_unity_mapping(request)
        second = self.service.execute_unity_mapping(request)
        self.assertEqual(first, second)
        self.assertEqual(first.execution_mode, ExecutionMode.MOCK)
        self.assertEqual(first.approval_state, ApprovalState.APPROVED)

    def test_execution_rejects_mapping_that_differs_from_approved_changeset(self):
        approved = self.proposal.changeset.model_copy(update={"approval_state": ApprovalState.APPROVED})
        changed_mapping = self.proposal.mapping.model_copy(update={"unity_animator_controller_id": "animator_other_v1"})
        with self.assertRaises(InvalidVersionError):
            self.service.execute_unity_mapping(
                UnityMappingExecutionRequest(
                    request_id="unity_apply_tampered",
                    mapping=changed_mapping,
                    changeset=approved,
                )
            )

    def test_mapping_contract_rejects_reused_stable_identity(self):
        values = self.proposal.mapping.model_dump(mode="python")
        values["unity_prefab_id"] = values["character_id"]
        with self.assertRaises(ValidationError):
            UnityCharacterMapping.model_validate(values)


if __name__ == "__main__":
    unittest.main()
