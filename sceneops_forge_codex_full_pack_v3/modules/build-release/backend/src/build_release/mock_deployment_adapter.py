"""Deterministic deployment adapter used only by fixtures and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .enums import DeploymentTarget, ExecutionMode
from .errors import AdapterExecutionError
from .ports import (
    AdapterCapabilities,
    AdapterProgress,
    AdapterResult,
    CancellationToken,
    DeploymentCommand,
    DeploymentPreview,
    IntegrationHealth,
    ProgressSink,
)


class DeterministicMockDeploymentAdapter:
    adapter_id = "adapter.mock-release"
    adapter_version = "1.0.0"

    def __init__(
        self,
        *,
        targets: Optional[List[DeploymentTarget]] = None,
        fail_attempts: int = 0,
    ) -> None:
        self._targets = targets or [DeploymentTarget.LOCAL, DeploymentTarget.JUDGE]
        self._fail_attempts = fail_attempts
        self._calls: Dict[str, int] = {}
        self.activations: List[str] = []

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            targets=self._targets,
            execution_mode=ExecutionMode.MOCK,
            supports_dry_run=True,
            supports_rollback=True,
        )

    def health_check(self) -> IntegrationHealth:
        return IntegrationHealth(
            healthy=True,
            code="MOCK_READY",
            message="Deterministic mock adapter is ready.",
        )

    def dry_run(self, command: DeploymentCommand) -> DeploymentPreview:
        self._require_target(command.target)
        return DeploymentPreview(
            target=command.target,
            destination=(
                f"mock://{command.target.value}/{command.project_id}/"
                f"{command.game_id}/{command.build_target_id}/{command.candidate_id}"
            ),
            artifact_id=command.artifact.artifact_id,
            source_checksum=command.artifact.checksum,
            would_activate=True,
            mode=ExecutionMode.MOCK,
        )

    def execute(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        return self._result(command, cancellation, progress, "deploy")

    def rollback(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        return self._result(command, cancellation, progress, "rollback")

    def _result(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
        action: str,
    ) -> AdapterResult:
        self._require_target(command.target)
        if cancellation.cancelled:
            raise AdapterExecutionError(
                "Mock operation was cancelled.",
                retryable=True,
                details={"operation_id": command.operation_id},
            )
        calls = self._calls.get(command.operation_id, 0) + 1
        self._calls[command.operation_id] = calls
        progress(
            AdapterProgress(
                operation_id=command.operation_id,
                sequence=1,
                phase="mock",
                percent=100,
                message="确定性模拟发布完成",
                occurred_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            )
        )
        if calls <= self._fail_attempts:
            raise AdapterExecutionError(
                "Configured deterministic mock failure.",
                retryable=True,
                details={"attempt": calls},
            )
        if command.operation_id not in self.activations:
            self.activations.append(command.operation_id)
        return AdapterResult(
            operation_id=command.operation_id,
            mode=ExecutionMode.MOCK,
            deployed_uri=(
                f"mock://{command.target.value}/{command.project_id}/"
                f"{command.game_id}/{command.build_target_id}/{command.candidate_id}"
            ),
            deployed_checksum=command.artifact.checksum,
            logs=[f"mock {action} completed on attempt {calls}"],
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
        )

    def _require_target(self, target: DeploymentTarget) -> None:
        if target not in self._targets:
            raise AdapterExecutionError(
                "Mock deployment target is not configured.",
                retryable=False,
                details={"target": target.value},
            )
