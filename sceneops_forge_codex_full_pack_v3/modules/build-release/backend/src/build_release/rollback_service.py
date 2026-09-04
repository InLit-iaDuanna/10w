"""Previous-known-good selection and separately approved rollback activation."""

from __future__ import annotations

from typing import List

from .checksum import canonical_sha256
from .enums import (
    ApprovalAction,
    CandidateStatus,
    DeploymentStatus,
    ExecutionMode,
    RollbackStatus,
)
from .errors import ConflictError, PolicyError
from .models_release import Deployment, ReleaseCandidate, RollbackPlan
from .operation_support import OperationSupport
from .policies import required_approval_roles, validate_approvals
from .ports import DeploymentCommand
from .requests import CreateRollbackPlanRequest, ExecuteRollbackRequest


class RollbackService(OperationSupport):
    def create_plan(self, request: CreateRollbackPlanRequest) -> RollbackPlan:
        current = self.repository.get_deployment(request.current_deployment_id)
        active = self.active_deployment(
            current.project_id,
            current.game_id,
            current.target,
            current.build_target_id,
        )
        if active is None or active.deployment_id != current.deployment_id:
            raise ConflictError(
                "Rollback can only target the currently active deployment.",
                details={"current_deployment_id": current.deployment_id},
            )
        candidates = self._eligible_known_good(current)
        if not candidates:
            raise PolicyError(
                "NO_PREVIOUS_KNOWN_GOOD",
                "No previous verified known-good deployment is available.",
                details={"current_deployment_id": current.deployment_id},
            )
        target_deployment = max(
            candidates, key=lambda item: (item.completed_at, item.candidate_id)
        )
        target_candidate = self.repository.get_candidate(target_deployment.candidate_id)
        adapter = self.adapter(current.target)
        self.require_healthy_adapter(adapter, current.target)
        command = DeploymentCommand(
            operation_id=request.activation_deployment_id,
            candidate_id=target_candidate.candidate_id,
            project_id=current.project_id,
            game_id=current.game_id,
            build_target_id=current.build_target_id,
            target=current.target,
            artifact=target_candidate.release_artifact,
            idempotency_key=request.idempotency_key,
        )
        capabilities, preview = self.preview(
            adapter, command, require_rollback=True
        )
        scope = self._plan_scope(
            request,
            current,
            target_deployment,
            target_candidate,
            capabilities,
            preview,
        )
        plan = RollbackPlan(
            rollback_plan_id=request.rollback_plan_id,
            activation_deployment_id=request.activation_deployment_id,
            current_deployment_id=current.deployment_id,
            target_deployment_id=target_deployment.deployment_id,
            target_candidate_id=target_candidate.candidate_id,
            project_id=current.project_id,
            game_id=current.game_id,
            deployment_target=current.target,
            profile=current.profile,
            current_scope_fingerprint=current.operation_scope_fingerprint,
            operation_scope_fingerprint=scope,
            idempotency_key=request.idempotency_key,
            adapter_id=capabilities.adapter_id,
            adapter_version=capabilities.adapter_version,
            expected_mode=capabilities.execution_mode,
            destination=preview.destination,
            target_patch_note_checksum=target_deployment.patch_note_checksum,
            reason=request.reason,
            required_approval_roles=required_approval_roles(
                current.profile, ApprovalAction.ROLLBACK, current.target
            ),
            approvals=[],
            status=RollbackStatus.WAITING_APPROVAL,
            mode=ExecutionMode.PLANNED,
            attempts=[],
            created_at=self.clock.now(),
        )
        self.repository.add_rollback_plan(plan)
        return plan

    def execute(self, request: ExecuteRollbackRequest) -> RollbackPlan:
        plan = self.repository.get_rollback_plan(request.rollback_plan_id)
        self._require_request_matches_plan(request, plan)
        with self.repository.deployment_operation(
            plan.activation_deployment_id, plan.idempotency_key
        ):
            plan = self.repository.get_rollback_plan(request.rollback_plan_id)
            self._require_request_matches_plan(request, plan)
            return self._execute_locked(request, plan)

    @staticmethod
    def _require_request_matches_plan(
        request: ExecuteRollbackRequest, plan: RollbackPlan
    ) -> None:
        if request.activation_deployment_id != plan.activation_deployment_id:
            raise PolicyError(
                "ROLLBACK_SCOPE_MISMATCH",
                "Rollback activation ID differs from the approved plan.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )
        if request.idempotency_key != plan.idempotency_key:
            raise PolicyError(
                "ROLLBACK_SCOPE_MISMATCH",
                "Rollback idempotency key differs from the approved plan.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )

    def _execute_locked(self, request: ExecuteRollbackRequest, plan: RollbackPlan) -> RollbackPlan:
        if plan.status == RollbackStatus.SUCCEEDED:
            return plan
        if (
            plan.status == RollbackStatus.FAILED
            and plan.attempts
            and not plan.attempts[-1].retryable
        ):
            raise PolicyError(
                "ROLLBACK_NOT_RETRYABLE",
                "The previous rollback failure is not retryable.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )
        validate_approvals(
            request.approvals,
            action=ApprovalAction.ROLLBACK,
            target_id=plan.rollback_plan_id,
            scope_fingerprint=plan.operation_scope_fingerprint,
            required_roles=plan.required_approval_roles,
        )
        current = self.repository.get_deployment(plan.current_deployment_id)
        active = self.active_deployment(
            plan.project_id,
            plan.game_id,
            plan.deployment_target,
            current.build_target_id,
        )
        if (
            active is None
            or active.deployment_id != current.deployment_id
            or current.operation_scope_fingerprint != plan.current_scope_fingerprint
        ):
            raise ConflictError(
                "Active deployment changed after rollback planning.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )
        target_candidate = self.repository.get_candidate(plan.target_candidate_id)
        self.require_artifact(target_candidate.release_artifact)
        adapter = self.adapter(plan.deployment_target)
        self.require_healthy_adapter(adapter, plan.deployment_target)
        command = DeploymentCommand(
            operation_id=plan.activation_deployment_id,
            candidate_id=target_candidate.candidate_id,
            project_id=plan.project_id,
            game_id=plan.game_id,
            build_target_id=current.build_target_id,
            target=plan.deployment_target,
            artifact=target_candidate.release_artifact,
            idempotency_key=request.idempotency_key,
        )
        capabilities, preview = self.preview(
            adapter, command, require_rollback=True
        )
        if (
            capabilities.adapter_id != plan.adapter_id
            or capabilities.adapter_version != plan.adapter_version
            or capabilities.execution_mode != plan.expected_mode
            or preview.destination != plan.destination
        ):
            raise ConflictError(
                "Rollback destination or adapter changed after planning.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )
        target_deployment = self.repository.get_deployment(plan.target_deployment_id)
        planned_request = CreateRollbackPlanRequest(
            rollback_plan_id=plan.rollback_plan_id,
            activation_deployment_id=plan.activation_deployment_id,
            current_deployment_id=plan.current_deployment_id,
            reason=plan.reason,
            idempotency_key=plan.idempotency_key,
        )
        expected_scope = self._plan_scope(
            planned_request,
            current,
            target_deployment,
            target_candidate,
            capabilities,
            preview,
        )
        if expected_scope != plan.operation_scope_fingerprint:
            raise ConflictError(
                "Rollback destination or adapter changed after planning.",
                details={"rollback_plan_id": plan.rollback_plan_id},
            )
        if capabilities.execution_mode == ExecutionMode.LIVE:
            self.require_verified_approvals(request.approvals)
        self.repository.assert_deployment_slot(
            plan.activation_deployment_id, plan.idempotency_key
        )
        started_at = self.clock.now()
        result, error, logs = self.invoke(adapter.rollback, command, capabilities)
        attempt = self.attempt(
            len(plan.attempts) + 1,
            started_at,
            capabilities.execution_mode,
            result,
            error,
            logs,
        )
        if attempt.status == DeploymentStatus.FAILED:
            updated = plan.model_copy(
                update={
                    "approvals": self.merge_approvals(plan.approvals, request.approvals),
                    "status": RollbackStatus.FAILED,
                    "mode": attempt.mode,
                    "attempts": [*plan.attempts, attempt],
                }
            )
            updated = RollbackPlan.model_validate(updated.model_dump())
            self.repository.save_rollback_plan(updated)
            return updated

        activation = self._activation(
            plan,
            request,
            current,
            target_deployment,
            target_candidate,
            attempt,
        )
        current_update = current.model_copy(
            update={"status": DeploymentStatus.ROLLED_BACK}
        )
        current_candidate = self.repository.get_candidate(current.candidate_id)
        current_candidate_update = current_candidate.model_copy(
            update={
                "status": (
                    CandidateStatus.DEPLOYED
                    if self._candidate_is_active_elsewhere(
                        current_candidate.candidate_id, current.deployment_id
                    )
                    else CandidateStatus.ROLLED_BACK
                )
            }
        )
        target_candidate_update = target_candidate.model_copy(
            update={"status": CandidateStatus.DEPLOYED}
        )
        updated = plan.model_copy(
            update={
                "approvals": self.merge_approvals(plan.approvals, request.approvals),
                "status": RollbackStatus.SUCCEEDED,
                "mode": attempt.mode,
                "attempts": [*plan.attempts, attempt],
                "executed_at": attempt.finished_at,
                "activation_deployment_id": activation.deployment_id,
            }
        )
        updated = RollbackPlan.model_validate(updated.model_dump())
        self.repository.commit_rollback(
            activation,
            current_update,
            current_candidate_update,
            target_candidate_update,
            updated,
        )
        return updated

    def _candidate_is_active_elsewhere(
        self, candidate_id: str, excluded_deployment_id: str
    ) -> bool:
        for deployment in self.repository.list_deployments():
            if (
                deployment.deployment_id == excluded_deployment_id
                or deployment.candidate_id != candidate_id
                or deployment.status != DeploymentStatus.SUCCEEDED
            ):
                continue
            active = self.active_deployment(
                deployment.project_id,
                deployment.game_id,
                deployment.target,
                deployment.build_target_id,
            )
            if active and active.deployment_id == deployment.deployment_id:
                return True
        return False

    def _eligible_known_good(self, current: Deployment) -> List[Deployment]:
        eligible: List[Deployment] = []
        for item in self.repository.list_deployments():
            if (
                item.deployment_id == current.deployment_id
                or item.status != DeploymentStatus.SUCCEEDED
                or not item.known_good
                or item.project_id != current.project_id
                or item.game_id != current.game_id
                or item.target != current.target
                or item.profile != current.profile
                or item.build_target_id != current.build_target_id
                or item.completed_at is None
                or current.completed_at is None
                or item.completed_at >= current.completed_at
            ):
                continue
            candidate = self.repository.get_candidate(item.candidate_id)
            try:
                self.require_artifact(candidate.release_artifact)
            except PolicyError:
                continue
            eligible.append(item)
        return eligible

    @staticmethod
    def _plan_scope(
        request,
        current,
        target_deployment,
        target_candidate,
        capabilities,
        preview,
    ) -> str:
        return canonical_sha256(
            {
                "rollback_plan_id": request.rollback_plan_id,
                "activation_deployment_id": request.activation_deployment_id,
                "current_deployment_id": current.deployment_id,
                "current_scope": current.operation_scope_fingerprint,
                "target_deployment_id": target_deployment.deployment_id,
                "target_candidate_scope": target_candidate.scope_fingerprint,
                "target_artifact_checksum": target_candidate.release_artifact.checksum,
                "target_patch_note_checksum": target_deployment.patch_note_checksum,
                "target": current.target.value,
                "reason": request.reason,
                "idempotency_key": request.idempotency_key,
                "adapter_id": capabilities.adapter_id,
                "adapter_version": capabilities.adapter_version,
                "destination": preview.destination,
                "preview_artifact_id": preview.artifact_id,
                "preview_source_checksum": preview.source_checksum,
                "preview_mode": preview.mode.value,
                "preview_would_activate": preview.would_activate,
            }
        )

    @staticmethod
    def _activation(
        plan,
        request,
        current,
        target_deployment,
        target_candidate,
        attempt,
    ) -> Deployment:
        return Deployment(
            deployment_id=plan.activation_deployment_id,
            candidate_id=target_candidate.candidate_id,
            project_id=plan.project_id,
            game_id=plan.game_id,
            profile=plan.profile,
            build_target_id=current.build_target_id,
            target=plan.deployment_target,
            source_commit=target_candidate.source_commit,
            candidate_scope_fingerprint=target_candidate.scope_fingerprint,
            operation_scope_fingerprint=plan.operation_scope_fingerprint,
            base_deployment_id=current.deployment_id,
            idempotency_key=request.idempotency_key,
            patch_note_id=target_deployment.patch_note_id,
            patch_note_revision=target_deployment.patch_note_revision,
            patch_note_checksum=target_deployment.patch_note_checksum,
            requested_known_good=True,
            status=DeploymentStatus.SUCCEEDED,
            mode=attempt.mode,
            artifact_source_mode=target_candidate.release_artifact.mode,
            approvals=list(request.approvals),
            attempts=[*plan.attempts, attempt],
            known_good=True,
            rollback_of_deployment_id=current.deployment_id,
            created_at=(plan.attempts[0].started_at if plan.attempts else attempt.started_at),
            completed_at=attempt.finished_at,
        )
