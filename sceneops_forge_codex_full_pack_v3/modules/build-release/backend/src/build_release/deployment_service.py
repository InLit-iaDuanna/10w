"""Approved deployment preparation, execution, and retry behavior."""

from __future__ import annotations

from typing import Sequence

from .checksum import canonical_sha256
from .enums import (
    ApprovalAction,
    CandidateStatus,
    DeploymentStatus,
    ExecutionMode,
    PatchNoteStatus,
)
from .errors import ConflictError, PolicyError
from .models_common import Approval
from .models_release import Deployment, DeploymentPlan, ReleaseCandidate
from .operation_support import OperationSupport
from .policies import required_approval_roles, validate_approvals
from .ports import DeploymentCommand
from .requests import DeployRequest, PrepareDeploymentRequest, RetryDeploymentRequest


class DeploymentService(OperationSupport):
    def prepare_deployment(self, request: PrepareDeploymentRequest) -> DeploymentPlan:
        candidate, manifest = self.require_deployable_candidate(request.candidate_id)
        note = self.repository.get_patch_note(request.patch_note_id)
        if note.candidate_id != candidate.candidate_id or note.revision != request.patch_note_revision:
            raise PolicyError(
                "PATCH_NOTE_SCOPE_MISMATCH",
                "Deployment patch note or revision does not match the candidate.",
                details={"patch_note_id": note.patch_note_id, "revision": note.revision},
            )
        adapter = self.adapter(request.target)
        self.require_healthy_adapter(adapter, request.target)
        command = self._command(request, candidate)
        capabilities, preview = self.preview(adapter, command)
        if capabilities.execution_mode != request.expected_mode:
            raise PolicyError(
                "EXECUTION_MODE_MISMATCH",
                "Configured adapter cannot provide the requested execution mode.",
                details={
                    "expected": request.expected_mode.value,
                    "actual": capabilities.execution_mode.value,
                },
            )
        base = self.active_deployment(
            candidate.project_id, candidate.game_id, request.target, manifest.target_id
        )
        scope = self._deployment_scope(
            request, candidate, base, capabilities, preview, note
        )
        return DeploymentPlan(
            deployment_id=request.deployment_id,
            candidate_id=candidate.candidate_id,
            target=request.target,
            patch_note_id=note.patch_note_id,
            patch_note_revision=note.revision,
            patch_note_checksum=note.content_checksum,
            base_deployment_id=base.deployment_id if base else None,
            operation_scope_fingerprint=scope,
            required_approval_roles=required_approval_roles(
                candidate.profile, ApprovalAction.DEPLOY, request.target
            ),
            mark_known_good_approval_roles=(
                required_approval_roles(
                    candidate.profile,
                    ApprovalAction.MARK_KNOWN_GOOD,
                    request.target,
                )
                if request.mark_known_good
                else []
            ),
            expected_mode=request.expected_mode,
            adapter_id=capabilities.adapter_id,
            adapter_version=capabilities.adapter_version,
            destination=preview.destination,
            created_at=self.clock.now(),
        )

    def deploy(self, request: DeployRequest) -> Deployment:
        with self.repository.deployment_operation(
            request.deployment_id, request.idempotency_key
        ):
            existing = self.repository.deployment_for_key(request.idempotency_key)
            if existing is not None:
                self._require_same_intent(existing, request)
                return existing
            self.repository.assert_deployment_slot(
                request.deployment_id, request.idempotency_key
            )
            plan = self.prepare_deployment(
                PrepareDeploymentRequest(**request.model_dump(exclude={"approvals"}))
            )
            candidate = self.repository.get_candidate(request.candidate_id)
            self._validate_approvals(request.approvals, request, plan, candidate)
            adapter = self.adapter(request.target)
            capabilities = adapter.capabilities()
            self._require_planned_adapter(plan, capabilities)
            if capabilities.execution_mode == ExecutionMode.LIVE:
                self.require_verified_approvals(request.approvals)
            note = self.repository.get_patch_note(request.patch_note_id)
            if note.status != PatchNoteStatus.APPROVED:
                self.repository.save_patch_note(
                    note.model_copy(update={"status": PatchNoteStatus.APPROVED})
                )
            started_at = self.clock.now()
            result, error, logs = self.invoke(
                adapter.execute,
                self._command(request, candidate),
                capabilities,
            )
            attempt = self.attempt(
                1,
                started_at,
                capabilities.execution_mode,
                result,
                error,
                logs,
            )
            deployment = self._deployment_record(request, plan, candidate, attempt)
            candidate_update = (
                candidate.model_copy(update={"status": CandidateStatus.DEPLOYED})
                if deployment.status == DeploymentStatus.SUCCEEDED
                else None
            )
            self.repository.commit_new_deployment(deployment, candidate_update)
            return deployment

    def retry_deployment(self, request: RetryDeploymentRequest) -> Deployment:
        initial = self.repository.get_deployment(request.deployment_id)
        with self.repository.deployment_operation(
            initial.deployment_id, initial.idempotency_key
        ):
            deployment = self.repository.get_deployment(request.deployment_id)
            if (
                deployment.status != DeploymentStatus.FAILED
                or not deployment.attempts[-1].retryable
            ):
                raise PolicyError(
                    "DEPLOYMENT_NOT_RETRYABLE",
                    "Only a retryable failed deployment can be retried.",
                    details={"deployment_id": deployment.deployment_id},
                )
            candidate, manifest = self.require_deployable_candidate(
                deployment.candidate_id
            )
            active = self.active_deployment(
                deployment.project_id,
                deployment.game_id,
                deployment.target,
                manifest.target_id,
            )
            active_id = active.deployment_id if active else None
            if active_id != deployment.base_deployment_id:
                raise ConflictError(
                    "Deployment base changed after the failed attempt.",
                    details={
                        "expected": deployment.base_deployment_id,
                        "actual": active_id,
                    },
                )
            deploy_request = self._retry_request(deployment, request.approvals)
            plan = self.prepare_deployment(
                PrepareDeploymentRequest(
                    **deploy_request.model_dump(exclude={"approvals"})
                )
            )
            if plan.operation_scope_fingerprint != deployment.operation_scope_fingerprint:
                raise ConflictError(
                    "Deployment inputs changed after the failed attempt.",
                    details={"deployment_id": deployment.deployment_id},
                )
            self._validate_approvals(
                request.approvals, deploy_request, plan, candidate
            )
            adapter = self.adapter(deployment.target)
            capabilities = adapter.capabilities()
            self._require_planned_adapter(plan, capabilities)
            if capabilities.execution_mode == ExecutionMode.LIVE:
                self.require_verified_approvals(request.approvals)
            started_at = self.clock.now()
            result, error, logs = self.invoke(
                adapter.execute,
                self._command(deploy_request, candidate),
                capabilities,
            )
            attempt = self.attempt(
                len(deployment.attempts) + 1,
                started_at,
                capabilities.execution_mode,
                result,
                error,
                logs,
            )
            updated = deployment.model_copy(
                update={
                    "status": attempt.status,
                    "mode": attempt.mode,
                    "approvals": self.merge_approvals(
                        deployment.approvals, request.approvals
                    ),
                    "attempts": [*deployment.attempts, attempt],
                    "known_good": deployment.requested_known_good
                    and attempt.status == DeploymentStatus.SUCCEEDED,
                    "completed_at": attempt.finished_at,
                }
            )
            updated = Deployment.model_validate(updated.model_dump())
            candidate_update = (
                candidate.model_copy(update={"status": CandidateStatus.DEPLOYED})
                if updated.status == DeploymentStatus.SUCCEEDED
                else None
            )
            self.repository.commit_deployment_update(updated, candidate_update)
            return updated

    def _deployment_record(self, request, plan, candidate, attempt) -> Deployment:
        manifest = self.repository.get_manifest(candidate.build_manifest_ids[0])
        return Deployment(
            deployment_id=request.deployment_id,
            candidate_id=candidate.candidate_id,
            project_id=candidate.project_id,
            game_id=candidate.game_id,
            profile=candidate.profile,
            build_target_id=manifest.target_id,
            target=request.target,
            source_commit=candidate.source_commit,
            candidate_scope_fingerprint=candidate.scope_fingerprint,
            operation_scope_fingerprint=plan.operation_scope_fingerprint,
            base_deployment_id=plan.base_deployment_id,
            idempotency_key=request.idempotency_key,
            patch_note_id=request.patch_note_id,
            patch_note_revision=request.patch_note_revision,
            patch_note_checksum=self.repository.get_patch_note(
                request.patch_note_id
            ).content_checksum,
            requested_known_good=request.mark_known_good,
            status=attempt.status,
            mode=attempt.mode,
            artifact_source_mode=candidate.release_artifact.mode,
            approvals=list(request.approvals),
            attempts=[attempt],
            known_good=request.mark_known_good
            and attempt.status == DeploymentStatus.SUCCEEDED,
            created_at=attempt.started_at,
            completed_at=attempt.finished_at,
        )

    def _validate_approvals(
        self,
        approvals: Sequence[Approval],
        request: DeployRequest,
        plan: DeploymentPlan,
        candidate: ReleaseCandidate,
    ) -> None:
        allowed_actions = {ApprovalAction.DEPLOY}
        if request.mark_known_good:
            allowed_actions.add(ApprovalAction.MARK_KNOWN_GOOD)
        if any(item.action not in allowed_actions for item in approvals):
            raise PolicyError(
                "APPROVAL_SCOPE_MISMATCH",
                "Deployment received an approval for another action.",
                details={"deployment_id": request.deployment_id},
            )
        validate_approvals(
            [item for item in approvals if item.action == ApprovalAction.DEPLOY],
            action=ApprovalAction.DEPLOY,
            target_id=request.deployment_id,
            scope_fingerprint=plan.operation_scope_fingerprint,
            required_roles=plan.required_approval_roles,
        )
        if request.mark_known_good:
            validate_approvals(
                [
                    item
                    for item in approvals
                    if item.action == ApprovalAction.MARK_KNOWN_GOOD
                ],
                action=ApprovalAction.MARK_KNOWN_GOOD,
                target_id=request.deployment_id,
                scope_fingerprint=plan.operation_scope_fingerprint,
                required_roles=plan.mark_known_good_approval_roles,
            )

    @staticmethod
    def _deployment_scope(
        request, candidate, base, capabilities, preview, note
    ) -> str:
        return canonical_sha256(
            {
                "deployment_id": request.deployment_id,
                "candidate_scope": candidate.scope_fingerprint,
                "target": request.target.value,
                "patch_note_id": request.patch_note_id,
                "patch_note_revision": request.patch_note_revision,
                "base_deployment_id": base.deployment_id if base else None,
                "idempotency_key": request.idempotency_key,
                "expected_mode": request.expected_mode.value,
                "mark_known_good": request.mark_known_good,
                "patch_note_checksum": note.content_checksum,
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
    def _require_same_intent(existing: Deployment, request: DeployRequest) -> None:
        if (
            existing.deployment_id != request.deployment_id
            or existing.candidate_id != request.candidate_id
            or existing.target != request.target
            or existing.patch_note_id != request.patch_note_id
            or existing.patch_note_revision != request.patch_note_revision
            or existing.requested_known_good != request.mark_known_good
            or existing.mode != request.expected_mode
        ):
            raise ConflictError(
                "Deployment idempotency key was reused with different immutable inputs.",
                details={"idempotency_key": request.idempotency_key},
            )

    def _command(self, request, candidate) -> DeploymentCommand:
        manifest = self.repository.get_manifest(candidate.build_manifest_ids[0])
        return DeploymentCommand(
            operation_id=request.deployment_id,
            candidate_id=candidate.candidate_id,
            project_id=candidate.project_id,
            game_id=candidate.game_id,
            build_target_id=manifest.target_id,
            target=request.target,
            artifact=candidate.release_artifact,
            idempotency_key=request.idempotency_key,
        )

    @staticmethod
    def _require_planned_adapter(plan, capabilities) -> None:
        if (
            capabilities.adapter_id != plan.adapter_id
            or capabilities.adapter_version != plan.adapter_version
            or capabilities.execution_mode != plan.expected_mode
        ):
            raise ConflictError(
                "Deployment adapter changed after dry-run approval planning.",
                details={"deployment_id": plan.deployment_id},
            )

    @staticmethod
    def _retry_request(deployment: Deployment, approvals) -> DeployRequest:
        return DeployRequest(
            deployment_id=deployment.deployment_id,
            candidate_id=deployment.candidate_id,
            target=deployment.target,
            patch_note_id=deployment.patch_note_id,
            patch_note_revision=deployment.patch_note_revision,
            idempotency_key=deployment.idempotency_key,
            expected_mode=deployment.mode,
            mark_known_good=deployment.requested_known_good,
            approvals=approvals,
        )
