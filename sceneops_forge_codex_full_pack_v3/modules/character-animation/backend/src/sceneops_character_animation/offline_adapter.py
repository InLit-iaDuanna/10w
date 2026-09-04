"""Truthful default adapter used while optional external tools are disconnected."""

from typing import List

from .adapter import (
    AdapterCapabilities,
    AdapterDryRun,
    AdapterLog,
    AdapterProgress,
    AdapterValidation,
    CancellationToken,
    RollbackResult,
)
from .animation_models import PreviewArtifact
from .common import ExecutionMode
from .errors import IntegrationOfflineError
from .operation_models import (
    ChangeSet,
    IntegrationAvailability,
    PreviewCaptureRequest,
    RetargetPreviewRequest,
    UnityCharacterMapping,
)


class OfflineCharacterToolAdapter:
    def health_check(self) -> IntegrationAvailability:
        return IntegrationAvailability(
            integration_id="character-tools",
            available=False,
            mode=ExecutionMode.BLOCKED,
            message="未连接角色预览、重定向或 Unity 适配器。导入数据仍可本地检查。",
            supported_operations=[],
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id="character-tools-offline",
            adapter_version="1.0.0",
            operations=[],
            maximum_timeout_seconds=30,
            max_attempts=1,
            supports_cancellation=True,
            supports_rollback=False,
        )

    def dry_run_preview(self, request: PreviewCaptureRequest) -> AdapterDryRun:
        raise IntegrationOfflineError("character-tools", "preview.capture")

    def capture_preview(
        self, request: PreviewCaptureRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact:
        raise IntegrationOfflineError("character-tools", "preview.capture")

    def dry_run_retarget_preview(self, request: RetargetPreviewRequest) -> AdapterDryRun:
        raise IntegrationOfflineError("retargeting", "retarget.preview")

    def capture_retarget_preview(
        self, request: RetargetPreviewRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact:
        raise IntegrationOfflineError("retargeting", "retarget.preview")

    def dry_run_unity_mapping(self, mapping: UnityCharacterMapping, changeset: ChangeSet) -> AdapterDryRun:
        raise IntegrationOfflineError("unity", "unity.character.map")

    def apply_unity_mapping(
        self,
        mapping: UnityCharacterMapping,
        changeset: ChangeSet,
        request_id: str,
        timeout_seconds: float,
        token: CancellationToken,
    ) -> UnityCharacterMapping:
        raise IntegrationOfflineError("unity", "unity.character.map")

    def rollback(self, snapshot_id: str) -> RollbackResult:
        raise IntegrationOfflineError("character-tools", "rollback")

    def validate_preview(self, result: PreviewArtifact) -> List[AdapterValidation]:
        raise IntegrationOfflineError("character-tools", "preview.validate")

    def validate_unity_mapping(self, result: UnityCharacterMapping) -> List[AdapterValidation]:
        raise IntegrationOfflineError("unity", "unity.character.validate")

    def progress_events(self, request_id: str) -> List[AdapterProgress]:
        return []

    def structured_logs(self, request_id: str) -> List[AdapterLog]:
        return []
