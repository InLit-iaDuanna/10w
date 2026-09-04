"""Character-animation application service."""

from typing import List, Protocol, Union

from .adapter import AdapterValidation, CancellationToken, CharacterToolAdapter
from .animation_models import AnimationClipSpec, PreviewArtifact
from .character_models import RigVersion
from .common import ApprovalRecord, ApprovalState, ExecutionMode, ReviewDecision
from .comparison import compare_clip_versions, compare_rig_versions
from .errors import ApprovalRequiredError, CharacterAnimationError, InvalidVersionError
from .operation_models import (
    ChangeSet,
    CharacterInspectionRequest,
    CharacterInspectionResult,
    ClipVersionDiff,
    IntegrationAvailability,
    IntegrationStatusResult,
    PreviewCaptureRequest,
    PreviewRegressionResult,
    RetargetPreviewRequest,
    RetargetPreviewResult,
    RigVersionDiff,
    UnityCharacterMapping,
    UnityMappingExecutionRequest,
    UnityMappingProposalRequest,
    UnityMappingProposalResult,
    VersionComparisonRequest,
    VersionComparisonResult,
    VersionReviewRequest,
    VersionReviewResult,
)
from .offline_adapter import OfflineCharacterToolAdapter
from .repository import InMemoryVersionRepository, VersionRepository
from .validation import validate_bundle, validate_clip, validate_retarget_profile


class CharacterAnimationServiceProtocol(Protocol):
    def inspect(self, request: CharacterInspectionRequest) -> CharacterInspectionResult: ...

    def compare_versions(self, request: VersionComparisonRequest) -> VersionComparisonResult: ...

    def review_version(self, request: VersionReviewRequest) -> VersionReviewResult: ...

    def capture_preview(self, request: PreviewCaptureRequest) -> PreviewArtifact: ...

    def preview_retarget(self, request: RetargetPreviewRequest) -> RetargetPreviewResult: ...

    def compare_previews(self, baseline: PreviewArtifact, candidate: PreviewArtifact) -> PreviewRegressionResult: ...

    def propose_unity_mapping(self, request: UnityMappingProposalRequest) -> UnityMappingProposalResult: ...

    def execute_unity_mapping(self, request: UnityMappingExecutionRequest) -> UnityCharacterMapping: ...

    def integration_status(self) -> IntegrationStatusResult: ...


class CharacterAnimationService:
    def __init__(
        self,
        repository: VersionRepository = None,
        adapter: CharacterToolAdapter = None,
    ) -> None:
        self._repository = repository or InMemoryVersionRepository()
        self._adapter = adapter or OfflineCharacterToolAdapter()

    def inspect(self, request: CharacterInspectionRequest) -> CharacterInspectionResult:
        self._repository.save_rig(request.bundle.rig)
        for clip in request.bundle.clips:
            self._repository.save_clip(clip)
        report = validate_bundle(request.bundle, request.mode)
        return CharacterInspectionResult(bundle=request.bundle, report=report)

    def compare_versions(self, request: VersionComparisonRequest) -> VersionComparisonResult:
        if request.entity_type == "rig":
            if not isinstance(request.base, RigVersion) or not isinstance(request.proposed, RigVersion):
                raise InvalidVersionError("Rig comparison requires two RigVersion objects.")
            diff: Union[RigVersionDiff, ClipVersionDiff] = compare_rig_versions(request.base, request.proposed)
        else:
            if not isinstance(request.base, AnimationClipSpec) or not isinstance(request.proposed, AnimationClipSpec):
                raise InvalidVersionError("Clip comparison requires two AnimationClipSpec objects.")
            diff = compare_clip_versions(request.base, request.proposed)
        return VersionComparisonResult(entity_type=request.entity_type, diff=diff)

    def review_version(self, request: VersionReviewRequest) -> VersionReviewResult:
        entity = self._get_version(request.entity_type, request.entity_id)
        if entity.approval.state in {ApprovalState.APPROVED, ApprovalState.REJECTED}:
            raise InvalidVersionError(
                "Reviewed versions are immutable; create a new version for another decision.",
                {"entity_id": request.entity_id, "state": entity.approval.state.value},
            )
        state = ApprovalState.APPROVED if request.decision == ReviewDecision.APPROVE else ApprovalState.REJECTED
        approval = ApprovalRecord(
            state=state,
            reviewed_by=request.reviewer_id,
            reviewed_at=request.reviewed_at,
            comment=request.comment,
        )
        provenance = entity.provenance.model_copy(update={"approval_state": state})
        reviewed = entity.model_copy(update={"approval": approval, "provenance": provenance})
        self._save_version(request.entity_type, reviewed)
        return VersionReviewResult(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            approval=approval,
            rollback_version_id=entity.previous_version_id,
        )

    def capture_preview(self, request: PreviewCaptureRequest) -> PreviewArtifact:
        self._require_previewable_clip(request.clip)
        self._adapter.dry_run_preview(request)
        preview = self._adapter.capture_preview(
            request,
            request.request_id,
            request.timeout_seconds,
            CancellationToken(),
        )
        self._require_adapter_validation(self._adapter.validate_preview(preview))
        return preview

    def preview_retarget(self, request: RetargetPreviewRequest) -> RetargetPreviewResult:
        self._require_previewable_clip(request.source_clip)
        checks = validate_retarget_profile(request.profile, request.source_rig, request.target_rig)
        if any(item.status.value == "fail" for item in checks):
            return RetargetPreviewResult(profile_valid=False, checks=checks, preview=None, mode=ExecutionMode.BLOCKED)
        self._adapter.dry_run_retarget_preview(request)
        preview = self._adapter.capture_retarget_preview(
            request,
            request.request_id,
            request.timeout_seconds,
            CancellationToken(),
        )
        self._require_adapter_validation(self._adapter.validate_preview(preview))
        return RetargetPreviewResult(profile_valid=True, checks=checks, preview=preview, mode=preview.execution_mode)

    def compare_previews(self, baseline: PreviewArtifact, candidate: PreviewArtifact) -> PreviewRegressionResult:
        same_camera = baseline.camera == candidate.camera
        score = candidate.frame_difference_score if same_camera else None
        if not same_camera or score is None:
            outcome = "blocked"
        else:
            outcome = "passed" if score <= 0.1 else "warning"
        return PreviewRegressionResult(
            baseline_preview_artifact_id=baseline.preview_artifact_id,
            candidate_preview_artifact_id=candidate.preview_artifact_id,
            same_fixed_camera=same_camera,
            frame_difference_score=score,
            outcome=outcome,
            limitation="帧差只提供固定相机回归信号，不表示动作质量获得人工批准。",
        )

    def propose_unity_mapping(self, request: UnityMappingProposalRequest) -> UnityMappingProposalResult:
        self._require_approved_versions(request)
        changeset_id = "changeset_{}".format(request.request_id)
        mapping = self._make_mapping(request, changeset_id)
        changeset = self._make_changeset(request, mapping, changeset_id)
        return UnityMappingProposalResult(mapping=mapping, changeset=changeset, mode=ExecutionMode.PLANNED)

    def execute_unity_mapping(self, request: UnityMappingExecutionRequest) -> UnityCharacterMapping:
        self._validate_mapping_execution(request)
        approved_mapping = request.mapping.model_copy(update={"approval_state": ApprovalState.APPROVED})
        self._adapter.dry_run_unity_mapping(approved_mapping, request.changeset)
        result = self._adapter.apply_unity_mapping(
            approved_mapping,
            request.changeset,
            request.request_id,
            request.timeout_seconds,
            CancellationToken(),
        )
        self._require_adapter_validation(self._adapter.validate_unity_mapping(result))
        return result

    def integration_status(self) -> IntegrationStatusResult:
        health = self._adapter.health_check()
        operations = set(self._adapter.capabilities().operations)
        integrations = [
            self._operation_status("character-preview", "preview.capture", health, operations),
            self._operation_status("retargeting", "retarget.preview", health, operations),
            self._operation_status("unity", "unity.character.map", health, operations),
            IntegrationAvailability(
                integration_id="automatic-rigging",
                available=False,
                mode=ExecutionMode.BLOCKED,
                message="未配置自动绑定适配器；可继续使用导入的 Rig。",
                supported_operations=[],
            ),
        ]
        return IntegrationStatusResult(
            integrations=integrations,
            generated_sources_message="生成源为可选输入；本模块不承诺自动绑定质量，导入路径不依赖生成。",
        )

    def _get_version(self, entity_type: str, entity_id: str) -> Union[RigVersion, AnimationClipSpec]:
        return self._repository.get_rig(entity_id) if entity_type == "rig" else self._repository.get_clip(entity_id)

    def _save_version(self, entity_type: str, entity: object) -> None:
        if entity_type == "rig":
            self._repository.save_rig(entity)
        else:
            self._repository.save_clip(entity)

    def _require_approved_versions(self, request: UnityMappingProposalRequest) -> None:
        versions = [request.bundle.rig, request.bundle.skin, *request.bundle.clips]
        unapproved = [
            item.provenance.artifact_id
            for item in versions
            if item.approval.state != ApprovalState.APPROVED
            or item.provenance.approval_state != ApprovalState.APPROVED
        ]
        if unapproved:
            raise InvalidVersionError("Unity mapping requires approved rig, skin, and clip versions.", {"ids": unapproved})

    def _make_mapping(self, request: UnityMappingProposalRequest, changeset_id: str) -> UnityCharacterMapping:
        bundle = request.bundle
        source_versions = [bundle.rig, bundle.skin, *bundle.clips]
        return UnityCharacterMapping(
            mapping_id="mapping_{}".format(request.request_id),
            character_id=bundle.character.character_id,
            rig_version_id=bundle.rig.rig_version_id,
            skin_version_id=bundle.skin.skin_version_id,
            clip_version_ids=[clip.clip_version_id for clip in bundle.clips],
            unity_prefab_id=request.unity_prefab_id,
            unity_game_object_sceneops_id=request.unity_game_object_sceneops_id,
            unity_animator_controller_id=request.unity_animator_controller_id,
            source_provenance_artifact_ids=[item.provenance.artifact_id for item in source_versions],
            source_provenance_checksums=[item.provenance.checksum_sha256 for item in source_versions],
            changeset_id=changeset_id,
            approval_state=ApprovalState.WAITING_APPROVAL,
            execution_mode=ExecutionMode.PLANNED,
        )

    def _make_changeset(
        self, request: UnityMappingProposalRequest, mapping: UnityCharacterMapping, changeset_id: str
    ) -> ChangeSet:
        return ChangeSet(
            changeset_id=changeset_id,
            base_version=request.base_unity_version,
            target_integration="unity",
            target_object_ids=[request.unity_prefab_id, request.unity_game_object_sceneops_id],
            previous_values={},
            proposed_values=mapping.model_dump(mode="json"),
            rationale="将已批准角色、Rig、Skin 与动画片段映射到 Unity Prefab。",
            expected_result="Unity Prefab 保留独立身份并引用指定 Animator Controller。",
            impact_scope="character",
            risk="medium",
            validation_plan=["重新扫描 Prefab 身份", "运行固定相机动画回归", "验证 Animator 状态引用"],
            rollback_plan=["恢复 base Unity 版本", "移除本 ChangeSet 新增的角色映射"],
            approval_requirements=["character:review", "unity:write"],
        )

    def _validate_mapping_execution(self, request: UnityMappingExecutionRequest) -> None:
        if request.mapping.changeset_id != request.changeset.changeset_id:
            raise InvalidVersionError("Mapping and ChangeSet identities do not match.")
        if request.changeset.approval_state != ApprovalState.APPROVED:
            raise ApprovalRequiredError(request.changeset.changeset_id)
        expected = {request.mapping.unity_prefab_id, request.mapping.unity_game_object_sceneops_id}
        if expected != set(request.changeset.target_object_ids):
            raise InvalidVersionError("ChangeSet targets do not match the Unity mapping.")
        if request.changeset.proposed_values != request.mapping.model_dump(mode="json"):
            raise InvalidVersionError("ChangeSet proposed values do not match the Unity mapping.")

    @staticmethod
    def _operation_status(
        integration_id: str, operation: str, health: IntegrationAvailability, operations: set
    ) -> IntegrationAvailability:
        available = health.available and operation in operations
        return IntegrationAvailability(
            integration_id=integration_id,
            available=available,
            mode=health.mode if available else ExecutionMode.BLOCKED,
            message=health.message if available else "{} 操作当前不可用。".format(operation),
            supported_operations=[operation] if available else [],
        )

    @staticmethod
    def _require_adapter_validation(validations: List[AdapterValidation]) -> None:
        failed = [item.code for item in validations if not item.passed]
        if failed:
            raise CharacterAnimationError(
                "ADAPTER_RESULT_INVALID",
                "Adapter result failed validation.",
                details={"failed_checks": failed},
            )

    @staticmethod
    def _require_previewable_clip(clip: AnimationClipSpec) -> None:
        blocking = [item.code for item in validate_clip(clip) if item.status.value in {"fail", "blocked"}]
        if blocking:
            raise InvalidVersionError(
                "Animation clip lacks valid evidence required for preview capture.",
                {"clip_version_id": clip.clip_version_id, "blocking_checks": blocking},
            )
