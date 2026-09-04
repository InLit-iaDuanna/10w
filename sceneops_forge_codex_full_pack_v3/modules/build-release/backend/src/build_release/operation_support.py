"""Shared release-operation checks and append-only attempt construction."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .adapter_support import NeverCancelled
from .enums import CandidateStatus, DeploymentStatus, DeploymentTarget, ExecutionMode
from .errors import AdapterExecutionError, PolicyError
from .models_common import Approval, ArtifactRef
from .models_release import Deployment, DeploymentAttempt, ReleaseCandidate
from .policies import evaluate_release_gates
from .ports import (
    AdapterResult,
    AdapterCapabilities,
    ArtifactCatalog,
    Clock,
    DeploymentAdapter,
    DeploymentCommand,
    DeploymentPreview,
    ReleaseAuthority,
)
from .repository import InMemoryReleaseRepository


class OperationSupport:
    def __init__(
        self,
        repository: InMemoryReleaseRepository,
        artifact_catalog: ArtifactCatalog,
        adapters: Dict[DeploymentTarget, DeploymentAdapter],
        clock: Clock,
        authority: ReleaseAuthority,
    ) -> None:
        self.repository = repository
        self.artifact_catalog = artifact_catalog
        self.adapters = dict(adapters)
        self.clock = clock
        self.authority = authority

    def require_deployable_candidate(self, candidate_id: str):
        candidate = self.repository.get_candidate(candidate_id)
        if candidate.status not in {CandidateStatus.READY, CandidateStatus.DEPLOYED}:
            raise PolicyError(
                "CANDIDATE_NOT_READY",
                "Only a ready candidate can be deployed.",
                details={"candidate_id": candidate_id, "status": candidate.status.value},
            )
        manifests = [
            self.repository.get_manifest(item) for item in candidate.build_manifest_ids
        ]
        if any(item.source_dirty for item in manifests):
            raise PolicyError(
                "DIRTY_SOURCE",
                "Candidate source is dirty and cannot be deployed.",
                details={"candidate_id": candidate_id},
            )
        primary = manifests[0]
        report = evaluate_release_gates(
            primary, candidate.gates, self.artifact_catalog, self.clock.now()
        )
        if not report.can_release:
            raise PolicyError(
                "RELEASE_GATES_BLOCKED",
                "Release gates no longer pass for this candidate.",
                details={"blockers": [item.code for item in report.blockers]},
            )
        self.require_artifact(candidate.release_artifact)
        return candidate, primary

    def active_deployment(
        self,
        project_id: str,
        game_id: str,
        target: DeploymentTarget,
        build_target_id: str,
    ) -> Optional[Deployment]:
        candidates = [
            item
            for item in self.repository.list_deployments()
            if item.project_id == project_id
            and item.game_id == game_id
            and item.target == target
            and item.build_target_id == build_target_id
            and item.status == DeploymentStatus.SUCCEEDED
            and item.completed_at is not None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item.completed_at, item.deployment_id))

    def require_artifact(self, artifact: ArtifactRef) -> None:
        inspection = self.artifact_catalog.inspect(artifact)
        if not inspection.available or not inspection.checksum_matches or not inspection.size_matches:
            raise PolicyError(
                "ARTIFACT_INTEGRITY_FAILED",
                "Release artifact is missing or corrupt.",
                details={"artifact_id": artifact.artifact_id, "reason": inspection.reason},
            )

    def adapter(self, target: DeploymentTarget) -> DeploymentAdapter:
        adapter = self.adapters.get(target)
        if adapter is None:
            raise PolicyError(
                "DEPLOYMENT_TARGET_UNAVAILABLE",
                "No typed adapter is configured for this deployment target.",
                details={"target": target.value},
            )
        if target not in adapter.capabilities().targets:
            raise PolicyError(
                "DEPLOYMENT_TARGET_UNSUPPORTED",
                "Configured adapter does not support this deployment target.",
                details={"target": target.value},
            )
        return adapter

    def preview(
        self,
        adapter: DeploymentAdapter,
        command: DeploymentCommand,
        *,
        require_rollback: bool = False,
    ) -> tuple[AdapterCapabilities, DeploymentPreview]:
        capabilities = adapter.capabilities()
        if capabilities.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.MOCK,
        }:
            raise PolicyError(
                "DEPLOYMENT_MODE_NOT_EXECUTABLE",
                "Deployment adapters must execute in live or mock mode.",
                details={"mode": capabilities.execution_mode.value},
            )
        if not capabilities.supports_dry_run:
            raise PolicyError(
                "DEPLOYMENT_DRY_RUN_UNSUPPORTED",
                "Deployment approval requires an adapter dry run.",
                details={"adapter_id": capabilities.adapter_id},
            )
        if require_rollback and not capabilities.supports_rollback:
            raise PolicyError(
                "ROLLBACK_UNSUPPORTED",
                "Configured adapter does not support rollback.",
                details={"adapter_id": capabilities.adapter_id},
            )
        preview = adapter.dry_run(command)
        if (
            preview.target != command.target
            or preview.artifact_id != command.artifact.artifact_id
            or preview.source_checksum != command.artifact.checksum
            or preview.mode != capabilities.execution_mode
            or not preview.would_activate
        ):
            raise AdapterExecutionError(
                "Adapter dry-run evidence does not match the requested operation.",
                retryable=False,
                details={"operation_id": command.operation_id},
            )
        return capabilities, preview

    @staticmethod
    def require_healthy_adapter(
        adapter: DeploymentAdapter, target: DeploymentTarget
    ) -> None:
        health = adapter.health_check()
        if not health.healthy:
            raise PolicyError(
                "DEPLOYMENT_ADAPTER_OFFLINE",
                health.message,
                details={"code": health.code, "target": target.value},
            )

    def invoke(
        self,
        operation,
        command: DeploymentCommand,
        capabilities: AdapterCapabilities,
    ):
        progress_messages: List[str] = []
        try:
            result = operation(
                command,
                NeverCancelled(),
                lambda item: progress_messages.append(
                    f"{item.sequence}:{item.phase}:{item.percent}:{item.message}"
                ),
            )
            if result.operation_id != command.operation_id:
                raise AdapterExecutionError(
                    "Adapter returned evidence for another operation.",
                    retryable=False,
                    details={"operation_id": command.operation_id},
                )
            if result.deployed_checksum != command.artifact.checksum:
                raise AdapterExecutionError(
                    "Adapter result checksum does not match the approved artifact.",
                    retryable=False,
                    details={"artifact_id": command.artifact.artifact_id},
                )
            if (
                result.mode != capabilities.execution_mode
                or result.adapter_id != capabilities.adapter_id
                or result.adapter_version != capabilities.adapter_version
            ):
                raise AdapterExecutionError(
                    "Adapter result identity differs from its approved capability report.",
                    retryable=False,
                    details={"operation_id": command.operation_id},
                )
            return result, None, progress_messages
        except AdapterExecutionError as error:
            return None, error, progress_messages

    def attempt(
        self,
        number: int,
        started_at,
        mode: ExecutionMode,
        result: Optional[AdapterResult],
        error: Optional[AdapterExecutionError],
        progress_logs: List[str],
    ) -> DeploymentAttempt:
        finished_at = self.clock.now()
        if result is not None and result.mode != mode:
            error = AdapterExecutionError(
                "Adapter result mode differs from its capability report.",
                retryable=False,
                details={"expected": mode.value, "actual": result.mode.value},
            )
            result = None
        if result is not None:
            return DeploymentAttempt(
                attempt=number,
                status=DeploymentStatus.SUCCEEDED,
                mode=result.mode,
                started_at=started_at,
                finished_at=finished_at,
                deployed_uri=result.deployed_uri,
                deployed_checksum=result.deployed_checksum,
                logs=[*progress_logs, *result.logs],
            )
        assert error is not None
        return DeploymentAttempt(
            attempt=number,
            status=DeploymentStatus.FAILED,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            error_code=error.code,
            error_message=error.message,
            retryable=error.retryable,
            logs=progress_logs,
        )

    def mark_candidate_deployed(self, candidate: ReleaseCandidate) -> None:
        if candidate.status != CandidateStatus.DEPLOYED:
            self.repository.save_candidate(
                candidate.model_copy(update={"status": CandidateStatus.DEPLOYED})
            )

    def require_verified_approvals(self, approvals: Sequence[Approval]) -> None:
        for approval in approvals:
            verification = self.authority.verify_approval(approval)
            if not verification.verified:
                raise PolicyError(
                    verification.code,
                    verification.message,
                    details={"approval_id": approval.approval_id},
                )

    @staticmethod
    def merge_approvals(
        existing: Sequence[Approval], additions: Sequence[Approval]
    ) -> List[Approval]:
        merged = {item.approval_id: item for item in existing}
        for item in additions:
            merged[item.approval_id] = item
        return [merged[key] for key in sorted(merged)]
