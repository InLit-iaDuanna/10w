from __future__ import annotations

import unittest

from build_release.enums import (
    ApprovalAction,
    ApprovalDecision,
    CandidateStatus,
    DeploymentStatus,
    DeploymentTarget,
    ExecutionMode,
    RollbackStatus,
)
from build_release.errors import PolicyError
from build_release.models_common import Approval
from build_release.requests import (
    CreateRollbackPlanRequest,
    DeployRequest,
    ExecuteRollbackRequest,
    PrepareDeploymentRequest,
)

from support import (
    BASE_TIME,
    create_patch_note,
    create_ready_candidate,
    make_build_pair,
    make_service,
    record_pair,
)
from test_deployment import deployment_approvals


def deploy_known_good(service, pair, candidate_id, note_id, deployment_id):
    candidate = create_ready_candidate(service, pair, candidate_id)
    note = create_patch_note(service, pair, candidate, note_id)
    prepared = PrepareDeploymentRequest(
        deployment_id=deployment_id,
        candidate_id=candidate.candidate_id,
        target=DeploymentTarget.LOCAL,
        patch_note_id=note.patch_note_id,
        patch_note_revision=note.revision,
        idempotency_key=f"key-{deployment_id}",
        expected_mode=ExecutionMode.MOCK,
        mark_known_good=True,
    )
    plan = service.prepare_deployment(prepared)
    deployment = service.deploy(
        DeployRequest(
            **prepared.model_dump(),
            approvals=deployment_approvals(
                plan, deployment_id, known_good=True
            ),
        )
    )
    return candidate, deployment


class RollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.catalog, self.adapter, _ = make_service()
        self.previous_pair = make_build_pair(
            "rollback.previous", commit="1" * 40, output_seed="previous-player"
        )
        self.current_pair = make_build_pair(
            "rollback.current", commit="2" * 40, output_seed="current-player"
        )
        record_pair(self.service, self.catalog, self.previous_pair)
        record_pair(self.service, self.catalog, self.current_pair)
        self.previous_candidate, self.previous = deploy_known_good(
            self.service,
            self.previous_pair,
            "candidate.rollback.previous",
            "patch-note.rollback.previous",
            "deployment.rollback.previous",
        )
        self.current_candidate, self.current = deploy_known_good(
            self.service,
            self.current_pair,
            "candidate.rollback.current",
            "patch-note.rollback.current",
            "deployment.rollback.current",
        )

    def test_selects_previous_known_good_and_executes_append_only_rollback(self) -> None:
        plan = self.service.create_rollback_plan(
            CreateRollbackPlanRequest(
                rollback_plan_id="rollback-plan.previous",
                activation_deployment_id="deployment.rollback.activation",
                current_deployment_id=self.current.deployment_id,
                reason="Current candidate regressed the home-door interaction.",
                idempotency_key="key-rollback-activation",
            )
        )
        self.assertEqual(plan.target_candidate_id, self.previous_candidate.candidate_id)
        self.assertEqual(plan.status, RollbackStatus.WAITING_APPROVAL)
        approvals = [
            Approval(
                approval_id=f"approval.rollback.execute.{index}",
                action=ApprovalAction.ROLLBACK,
                target_id=plan.rollback_plan_id,
                scope_fingerprint=plan.operation_scope_fingerprint,
                role=role,
                actor_id=f"user.{role}",
                decision=ApprovalDecision.APPROVED,
                rationale="Approve exact rollback plan.",
                decided_at=BASE_TIME,
            )
            for index, role in enumerate(plan.required_approval_roles)
        ]
        executed = self.service.execute_rollback(
            ExecuteRollbackRequest(
                rollback_plan_id=plan.rollback_plan_id,
                activation_deployment_id=plan.activation_deployment_id,
                idempotency_key="key-rollback-activation",
                approvals=approvals,
            )
        )
        self.assertEqual(executed.status, RollbackStatus.SUCCEEDED)
        activation = self.service.repository.get_deployment(
            executed.activation_deployment_id
        )
        self.assertEqual(activation.candidate_id, self.previous_candidate.candidate_id)
        self.assertEqual(
            activation.rollback_of_deployment_id, self.current.deployment_id
        )
        self.assertEqual(
            self.service.repository.get_deployment(self.current.deployment_id).status,
            DeploymentStatus.ROLLED_BACK,
        )
        self.assertEqual(
            self.service.repository.get_candidate(
                self.current_candidate.candidate_id
            ).status,
            CandidateStatus.ROLLED_BACK,
        )
        self.assertEqual(len(self.service.repository.list_deployments()), 3)

    def test_rollback_requires_separate_exact_approval(self) -> None:
        plan = self.service.create_rollback_plan(
            CreateRollbackPlanRequest(
                rollback_plan_id="rollback-plan.needs-approval",
                activation_deployment_id="deployment.rollback.needs-approval",
                current_deployment_id=self.current.deployment_id,
                reason="Exercise explicit rollback approval.",
                idempotency_key="key-rollback-no-approval",
            )
        )
        with self.assertRaisesRegex(PolicyError, "Explicit approval"):
            self.service.execute_rollback(
                ExecuteRollbackRequest(
                    rollback_plan_id=plan.rollback_plan_id,
                    activation_deployment_id=plan.activation_deployment_id,
                    idempotency_key="key-rollback-no-approval",
                    approvals=[],
                )
            )

    def test_no_previous_same_game_known_good_is_blocked(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair(
            "rollback.only",
            project_id="project.warehouse-escape",
            game_id="game.warehouse-escape",
        )
        record_pair(service, catalog, pair)
        _, only = deploy_known_good(
            service,
            pair,
            "candidate.rollback.only",
            "patch-note.rollback.only",
            "deployment.rollback.only",
        )
        with self.assertRaisesRegex(PolicyError, "No previous verified"):
            service.create_rollback_plan(
                CreateRollbackPlanRequest(
                    rollback_plan_id="rollback-plan.none",
                    activation_deployment_id="deployment.rollback.none",
                    current_deployment_id=only.deployment_id,
                    reason="No earlier Warehouse Escape candidate exists.",
                    idempotency_key="key-rollback-none",
                )
            )

    def test_failed_rollback_preserves_active_and_retry_appends_attempt(self) -> None:
        plan = self.service.create_rollback_plan(
            CreateRollbackPlanRequest(
                rollback_plan_id="rollback-plan.retry",
                activation_deployment_id="deployment.rollback.retry",
                current_deployment_id=self.current.deployment_id,
                reason="Exercise rollback failure and retry evidence.",
                idempotency_key="key-rollback-retry",
            )
        )
        approvals = [
            Approval(
                approval_id=f"approval.rollback.retry.{index}",
                action=ApprovalAction.ROLLBACK,
                target_id=plan.rollback_plan_id,
                scope_fingerprint=plan.operation_scope_fingerprint,
                role=role,
                actor_id=f"user.{role}",
                decision=ApprovalDecision.APPROVED,
                rationale="Approve exact rollback retry fixture.",
                decided_at=BASE_TIME,
            )
            for index, role in enumerate(plan.required_approval_roles)
        ]
        self.adapter._fail_attempts = 1
        request = ExecuteRollbackRequest(
            rollback_plan_id=plan.rollback_plan_id,
            activation_deployment_id=plan.activation_deployment_id,
            idempotency_key="key-rollback-retry",
            approvals=approvals,
        )
        failed = self.service.execute_rollback(request)
        self.assertEqual(failed.status, RollbackStatus.FAILED)
        self.assertEqual(
            self.service.repository.get_deployment(self.current.deployment_id).status,
            DeploymentStatus.SUCCEEDED,
        )
        succeeded = self.service.execute_rollback(request)
        self.assertEqual(succeeded.status, RollbackStatus.SUCCEEDED)
        self.assertEqual([item.attempt for item in succeeded.attempts], [1, 2])

    def test_rollback_execution_cannot_change_planned_idempotency_key(self) -> None:
        plan = self.service.create_rollback_plan(
            CreateRollbackPlanRequest(
                rollback_plan_id="rollback-plan.fixed-key",
                activation_deployment_id="deployment.rollback.fixed-key",
                current_deployment_id=self.current.deployment_id,
                reason="Bind retry identity into the approved rollback plan.",
                idempotency_key="key-rollback-fixed",
            )
        )

        with self.assertRaisesRegex(PolicyError, "idempotency key differs"):
            self.service.execute_rollback(
                ExecuteRollbackRequest(
                    rollback_plan_id=plan.rollback_plan_id,
                    activation_deployment_id=plan.activation_deployment_id,
                    idempotency_key="key-rollback-changed",
                    approvals=[],
                )
            )


if __name__ == "__main__":
    unittest.main()
