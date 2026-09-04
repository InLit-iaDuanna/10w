"""Typed external-tool boundary with deterministic mock and truthful offline modes."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Protocol

from pydantic import Field

from .animation_models import AnimationClipSpec, FixedPreviewCamera, PreviewArtifact
from .character_models import CharacterSpec
from .common import ApprovalState, ExecutionMode, Provenance, StrictModel
from .errors import AdapterTimeoutError, OperationCancelledError
from .operation_models import (
    ChangeSet,
    IntegrationAvailability,
    PreviewCaptureRequest,
    RetargetPreviewRequest,
    UnityCharacterMapping,
)


class AdapterCapabilities(StrictModel):
    adapter_id: str
    adapter_version: str
    operations: List[Literal["preview.capture", "retarget.preview", "unity.character.map"]]
    maximum_timeout_seconds: float = Field(gt=0)
    max_attempts: int = Field(ge=1)
    supports_cancellation: bool
    supports_rollback: bool


class AdapterDryRun(StrictModel):
    operation: Literal["preview.capture", "retarget.preview", "unity.character.map"]
    target_ids: List[str]
    planned_effects: List[str]
    mode: Literal[ExecutionMode.PLANNED] = ExecutionMode.PLANNED


class RollbackResult(StrictModel):
    snapshot_id: str
    restored: bool
    mode: ExecutionMode
    message: str


class AdapterProgress(StrictModel):
    request_id: str
    state: Literal["planned", "running", "succeeded"]
    progress: float = Field(ge=0, le=1)
    message: str


class AdapterLog(StrictModel):
    request_id: str
    level: Literal["info", "warning", "error"]
    code: str
    message: str
    fields: Dict[str, object] = Field(default_factory=dict)


class AdapterValidation(StrictModel):
    code: str
    passed: bool
    message: str


@dataclass
class CancellationToken:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


class CharacterToolAdapter(Protocol):
    def health_check(self) -> IntegrationAvailability: ...

    def capabilities(self) -> AdapterCapabilities: ...

    def dry_run_preview(self, request: PreviewCaptureRequest) -> AdapterDryRun: ...

    def capture_preview(
        self, request: PreviewCaptureRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact: ...

    def capture_retarget_preview(
        self, request: RetargetPreviewRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact: ...

    def dry_run_retarget_preview(self, request: RetargetPreviewRequest) -> AdapterDryRun: ...

    def dry_run_unity_mapping(self, mapping: UnityCharacterMapping, changeset: ChangeSet) -> AdapterDryRun: ...

    def apply_unity_mapping(
        self,
        mapping: UnityCharacterMapping,
        changeset: ChangeSet,
        request_id: str,
        timeout_seconds: float,
        token: CancellationToken,
    ) -> UnityCharacterMapping: ...

    def rollback(self, snapshot_id: str) -> RollbackResult: ...

    def validate_preview(self, result: PreviewArtifact) -> List[AdapterValidation]: ...

    def validate_unity_mapping(self, result: UnityCharacterMapping) -> List[AdapterValidation]: ...

    def progress_events(self, request_id: str) -> List[AdapterProgress]: ...

    def structured_logs(self, request_id: str) -> List[AdapterLog]: ...


class DeterministicMockCharacterToolAdapter:
    """Fixture adapter; it never represents a Blender or Unity live execution."""

    _maximum_timeout_seconds = 30.0

    def __init__(self) -> None:
        self._preview_results: Dict[str, PreviewArtifact] = {}
        self._mapping_results: Dict[str, UnityCharacterMapping] = {}
        self._progress: Dict[str, List[AdapterProgress]] = {}
        self._logs: Dict[str, List[AdapterLog]] = {}

    def health_check(self) -> IntegrationAvailability:
        return IntegrationAvailability(
            integration_id="character-tool-fixture",
            available=True,
            mode=ExecutionMode.MOCK,
            message="确定性角色工具 fixture 已连接；不会调用 Blender 或 Unity。",
            supported_operations=self.capabilities().operations,
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id="character-tool-fixture",
            adapter_version="1.0.0",
            operations=["preview.capture", "retarget.preview", "unity.character.map"],
            maximum_timeout_seconds=self._maximum_timeout_seconds,
            max_attempts=1,
            supports_cancellation=True,
            supports_rollback=True,
        )

    def dry_run_preview(self, request: PreviewCaptureRequest) -> AdapterDryRun:
        return AdapterDryRun(
            operation="preview.capture",
            target_ids=[request.character.character_id, request.rig.rig_version_id, request.clip.clip_version_id],
            planned_effects=["使用固定相机生成预览 artifact", "记录片段与 Rig provenance"],
        )

    def capture_preview(
        self, request: PreviewCaptureRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact:
        self._guard(request_id, timeout_seconds, token)
        if request_id not in self._preview_results:
            self._start(request_id, "preview.capture")
            self._preview_results[request_id] = self._make_preview(
                request.character,
                request.rig.rig_version_id,
                request.clip,
                request.camera,
                request_id,
                request.baseline_preview,
            )
            self._finish(request_id, "preview.capture")
        return self._preview_results[request_id]

    def capture_retarget_preview(
        self, request: RetargetPreviewRequest, request_id: str, timeout_seconds: float, token: CancellationToken
    ) -> PreviewArtifact:
        self._guard(request_id, timeout_seconds, token)
        if request_id not in self._preview_results:
            self._start(request_id, "retarget.preview")
            self._preview_results[request_id] = self._make_preview(
                request.character,
                request.target_rig.rig_version_id,
                request.source_clip,
                request.camera,
                request_id,
                None,
            )
            self._finish(request_id, "retarget.preview")
        return self._preview_results[request_id]

    def dry_run_retarget_preview(self, request: RetargetPreviewRequest) -> AdapterDryRun:
        return AdapterDryRun(
            operation="retarget.preview",
            target_ids=[
                request.character.character_id,
                request.source_rig.rig_version_id,
                request.target_rig.rig_version_id,
                request.profile.retarget_profile_id,
            ],
            planned_effects=["验证 RetargetProfile", "用固定相机生成目标 Rig 预览"],
        )

    def dry_run_unity_mapping(self, mapping: UnityCharacterMapping, changeset: ChangeSet) -> AdapterDryRun:
        return AdapterDryRun(
            operation="unity.character.map",
            target_ids=[mapping.unity_prefab_id, mapping.unity_game_object_sceneops_id],
            planned_effects=["关联角色版本与 Unity Prefab", "配置 Animator Controller 与片段映射"],
        )

    def apply_unity_mapping(
        self,
        mapping: UnityCharacterMapping,
        changeset: ChangeSet,
        request_id: str,
        timeout_seconds: float,
        token: CancellationToken,
    ) -> UnityCharacterMapping:
        self._guard(request_id, timeout_seconds, token)
        if request_id not in self._mapping_results:
            self._start(request_id, "unity.character.map")
            self._mapping_results[request_id] = mapping.model_copy(
                update={"execution_mode": ExecutionMode.MOCK, "approval_state": ApprovalState.APPROVED}
            )
            self._finish(request_id, "unity.character.map")
        return self._mapping_results[request_id]

    def rollback(self, snapshot_id: str) -> RollbackResult:
        return RollbackResult(
            snapshot_id=snapshot_id,
            restored=True,
            mode=ExecutionMode.MOCK,
            message="fixture 回滚已确认；未修改真实工程。",
        )

    def validate_preview(self, result: PreviewArtifact) -> List[AdapterValidation]:
        return [
            AdapterValidation(
                code="preview.fixed_camera",
                passed=result.camera.coordinate_space == "character_local",
                message="预览使用角色本地固定相机。",
            ),
            AdapterValidation(
                code="preview.truthful_mode",
                passed=result.execution_mode == ExecutionMode.MOCK,
                message="fixture 输出明确标记为 mock。",
            ),
        ]

    def validate_unity_mapping(self, result: UnityCharacterMapping) -> List[AdapterValidation]:
        return [
            AdapterValidation(
                code="unity.identity_chain",
                passed=bool(result.source_provenance_artifact_ids),
                message="Unity 映射保留来源 artifact 身份链。",
            ),
            AdapterValidation(
                code="unity.truthful_mode",
                passed=result.execution_mode == ExecutionMode.MOCK,
                message="fixture Unity 映射明确标记为 mock。",
            ),
        ]

    def progress_events(self, request_id: str) -> List[AdapterProgress]:
        return list(self._progress.get(request_id, []))

    def structured_logs(self, request_id: str) -> List[AdapterLog]:
        return list(self._logs.get(request_id, []))

    def _guard(self, request_id: str, timeout_seconds: float, token: CancellationToken) -> None:
        if token.cancelled:
            raise OperationCancelledError(request_id)
        if timeout_seconds > self._maximum_timeout_seconds:
            raise AdapterTimeoutError(timeout_seconds, self._maximum_timeout_seconds)

    def _make_preview(
        self,
        character: CharacterSpec,
        rig_id: str,
        clip: AnimationClipSpec,
        camera: FixedPreviewCamera,
        request_id: str,
        baseline: Optional[PreviewArtifact],
    ) -> PreviewArtifact:
        character_id = character.character_id
        clip_id = clip.clip_version_id
        preview_id = "preview_{}".format(request_id)
        feature_ids = [link.feature_spec_id for link in character.feature_links]
        task_ids = [task_id for link in character.feature_links for task_id in link.task_ids]
        provenance = Provenance(
            artifact_id=preview_id,
            artifact_type="animation-preview",
            source_project_id=character.provenance.source_project_id,
            source_version=clip.provenance.source_version,
            source_commit=character.provenance.source_commit,
            related_sceneops_ids=[character_id, rig_id, clip_id, *feature_ids, *task_ids],
            tool="sceneops-character-preview-fixture",
            adapter_version="1.0.0",
            recipe_version="fixed-camera-v1",
            creator="fixture_worker",
            execution_mode=ExecutionMode.MOCK,
            created_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            checksum_sha256="b" * 64,
            approval_state=ApprovalState.DRAFT,
        )
        baseline_id = getattr(baseline, "preview_artifact_id", None)
        return PreviewArtifact(
            preview_artifact_id=preview_id,
            character_id=character_id,
            rig_version_id=rig_id,
            clip_version_id=clip_id,
            artifact_uri="mock://character-animation/previews/{}.mp4".format(request_id),
            media_type="video/mp4",
            frame_count=max(1, round(clip.duration_seconds * clip.sample_rate_hz) + 1),
            duration_seconds=clip.duration_seconds,
            camera=camera,
            captured_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            execution_mode=ExecutionMode.MOCK,
            baseline_preview_artifact_id=baseline_id,
            frame_difference_score=0.04 if baseline_id else None,
            provenance=provenance,
        )

    def _start(self, request_id: str, operation: str) -> None:
        self._progress[request_id] = [
            AdapterProgress(request_id=request_id, state="planned", progress=0, message="fixture dry-run 已完成。"),
            AdapterProgress(request_id=request_id, state="running", progress=0.5, message="fixture 操作执行中。"),
        ]
        self._logs[request_id] = [
            AdapterLog(
                request_id=request_id,
                level="info",
                code="FIXTURE_EXECUTION_STARTED",
                message="确定性 fixture 操作开始。",
                fields={"operation": operation, "mode": "mock"},
            )
        ]

    def _finish(self, request_id: str, operation: str) -> None:
        self._progress[request_id].append(
            AdapterProgress(request_id=request_id, state="succeeded", progress=1, message="fixture 操作完成。")
        )
        self._logs[request_id].append(
            AdapterLog(
                request_id=request_id,
                level="info",
                code="FIXTURE_EXECUTION_SUCCEEDED",
                message="确定性 fixture 操作完成。",
                fields={"operation": operation, "mode": "mock"},
            )
        )
