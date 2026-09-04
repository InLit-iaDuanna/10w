"""Dependency-free Audio Studio vertical slice."""
from __future__ import annotations

import math
import io
import re
import struct
import wave
from dataclasses import dataclass, replace

from .models import (AssetStatus, AudioAnalysis, AudioAsset, AudioMapping, AudioMetadata, AudioSpec,
                     ChangeSet, ChangeSetStatus, EngineUnityAudioAdapter, EventBinding, ExecutionMode,
                     MappingResult, ModuleState, Provenance)


class AudioValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AnalysisJob:
    job_id: str
    state: str
    mode: ExecutionMode
    asset_id: str


class AudioStudioService:
    def __init__(self, *, module_enabled: bool, unity_online: bool) -> None:
        self.module_enabled = module_enabled
        self.unity_online = unity_online

    def availability(self) -> ModuleState:
        if not self.module_enabled:
            return ModuleState("disabled", "音频工作室已被功能开关禁用。", ExecutionMode.BLOCKED)
        if not self.unity_online:
            return ModuleState("offline", "Unity 未连接；可以分析和准备提案，不能发布映射。", ExecutionMode.BLOCKED)
        return ModuleState("ready", "音频工作室可用。", ExecutionMode.PLANNED)

    def inspect_wav(self, data: bytes | None, filename: str) -> AudioAnalysis:
        if data is None or not data:
            raise AudioValidationError("AUDIO_FILE_MISSING: 未提供音频文件。")
        if not filename.lower().endswith(".wav"):
            raise AudioValidationError("AUDIO_FORMAT_UNSUPPORTED: 当前纵切只支持 WAV。")
        if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise AudioValidationError("AUDIO_WAV_INVALID: WAV 文件头无效。")
        try:
            with wave.open(io.BytesIO(data), "rb") as source:
                channels, sample_rate = source.getnchannels(), source.getframerate()
                bit_depth = source.getsampwidth() * 8
                frames = source.getnframes()
                samples = source.readframes(frames)
        except (wave.Error, EOFError, struct.error) as error:
            raise AudioValidationError("AUDIO_WAV_INVALID: 无法读取 PCM WAV 数据块。") from error
        if bit_depth != 16 or channels not in (1, 2) or sample_rate <= 0:
            raise AudioValidationError("AUDIO_FORMAT_UNSUPPORTED: 需要 16-bit PCM 单声道或立体声 WAV。")
        data_size = frames * channels * 2
        if len(samples) != data_size or data_size == 0:
            raise AudioValidationError("AUDIO_WAV_INVALID: PCM 数据不完整。")
        values = struct.unpack("<" + "h" * (data_size // 2), samples)
        peak = max(abs(value) for value in values) / 32768
        rms = math.sqrt(sum(value * value for value in values) / len(values)) / 32768
        peak_dbfs = _dbfs(peak)
        loudness = _dbfs(rms)
        duration = len(values) / channels / sample_rate
        warnings = tuple(message for message, condition in (
            ("峰值接近削波（高于 -1 dBFS）。", peak_dbfs > -1),
            ("近似响度很低（低于 -36 dBFS）。", loudness < -36),
        ) if condition)
        return AudioAnalysis(AudioMetadata("wav/pcm", channels, sample_rate, bit_depth, duration), peak_dbfs, loudness,
                             _waveform_peaks(values, 16), warnings)

    def create_analysis_job(self, asset_id: str, mode: ExecutionMode = ExecutionMode.PLANNED) -> AnalysisJob:
        return AnalysisJob(f"job_audio_analysis_{asset_id}", "queued", mode, asset_id)

    def create_spec(self, spec_id: str, project_id: str, purpose: str, intended_events: tuple[str, ...],
                    mixer_group: str, generation_reference: str | None = None) -> AudioSpec:
        if not project_id or not purpose or not intended_events or not mixer_group:
            raise AudioValidationError("AUDIO_SPEC_INVALID: 项目、用途、事件和 Mixer 组均为必填项。")
        if any(not event.startswith("gameplay.") for event in intended_events):
            raise AudioValidationError("AUDIO_SPEC_INVALID: 音频事件必须使用 gameplay. 命名空间。")
        return AudioSpec(spec_id, project_id, purpose, intended_events, mixer_group, generation_reference)

    def create_import_proposal(self, asset_id: str, analysis: AudioAnalysis,
                               provenance: Provenance) -> AudioAsset:
        self._validate_provenance(provenance)
        return AudioAsset(asset_id, AssetStatus.PROPOSAL, replace(provenance, approval_state="proposal"), analysis)

    def create_generated_proposal(self, asset_id: str, analysis: AudioAnalysis,
                                  provenance: Provenance) -> AudioAsset:
        """Keep generated media unpublishable until an approved ChangeSet promotes it."""
        self._validate_provenance(provenance, require_ai_fields=True)
        if provenance.producing_module != "audio-studio":
            raise AudioValidationError("AUDIO_GENERATION_PROVENANCE_REQUIRED: 生成提案必须由 audio-studio 产生。")
        return AudioAsset(asset_id, AssetStatus.PROPOSAL, replace(provenance, approval_state="proposal"), analysis)

    def publish_asset(self, proposal: AudioAsset, change_set: ChangeSet) -> AudioAsset:
        if proposal.status is not AssetStatus.PROPOSAL:
            raise AudioValidationError("AUDIO_ASSET_NOT_PROPOSAL: 只能发布待审音频提案。")
        self._validate_changeset(change_set, proposal.provenance.source_version)
        if change_set.status is not ChangeSetStatus.APPROVED:
            raise AudioValidationError("CHANGESET_NOT_APPROVED: 发布音频需要已批准 ChangeSet。")
        self._validate_approval_snapshot(change_set)
        expected_change = {
            "operation": "publish_audio_asset", "asset_id": proposal.asset_id,
            "source_version": proposal.provenance.source_version, "sha256": proposal.provenance.sha256,
        }
        if (change_set.target_integration != "artifact-store" or
                change_set.target_object_ids != (proposal.asset_id,) or
                change_set.proposed_values != expected_change):
            raise AudioValidationError("AUDIO_ASSET_CHANGESET_MISMATCH: ChangeSet 未批准发布此音频资产。")
        self._validate_provenance(proposal.provenance, require_ai_fields=proposal.provenance.provider is not None)
        provenance = replace(proposal.provenance, approval_state="published")
        self.apply_changeset(change_set)
        return AudioAsset(proposal.asset_id, AssetStatus.PUBLISHED, provenance, proposal.analysis)

    def submit_changeset(self, change_set: ChangeSet) -> ChangeSet:
        self._validate_changeset(change_set, change_set.base_version)
        return self._transition_changeset(change_set, ChangeSetStatus.DRAFT, ChangeSetStatus.SUBMITTED)

    def approve_changeset(self, change_set: ChangeSet, *, approver_id: str, approved_at: str,
                          approval_evidence: tuple[str, ...]) -> ChangeSet:
        if (not approver_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", approved_at)
                or not approval_evidence or any(not item for item in approval_evidence)):
            raise AudioValidationError("CHANGESET_APPROVAL_EVIDENCE_REQUIRED: 批准需要审批证据。")
        approved = self._transition_changeset(change_set, ChangeSetStatus.SUBMITTED, ChangeSetStatus.APPROVED)
        approved.approved_by = approver_id
        approved.approved_at = approved_at
        approved.approval_evidence = approval_evidence
        approved._record_approval()
        return approved

    def apply_changeset(self, change_set: ChangeSet) -> ChangeSet:
        self._validate_approval_snapshot(change_set)
        return self._transition_changeset(change_set, ChangeSetStatus.APPROVED, ChangeSetStatus.APPLIED)

    def bind_event(self, gameplay_event: str, audio_asset_id: str) -> EventBinding:
        if not gameplay_event.startswith("gameplay."):
            raise AudioValidationError("AUDIO_EVENT_INVALID: 事件必须使用 gameplay. 命名空间。")
        if not audio_asset_id:
            raise AudioValidationError("AUDIO_ASSET_REQUIRED: 音频资产 ID 不能为空。")
        return EventBinding(f"bind_{gameplay_event.replace('.', '_')}_{audio_asset_id}", gameplay_event, audio_asset_id)

    def propose_mapping(self, adapter: EngineUnityAudioAdapter, mapping: AudioMapping,
                        asset: AudioAsset, change_set: ChangeSet) -> MappingResult:
        self._validate_mapping(asset, change_set, mapping, require_approval=False)
        capabilities = adapter.get_capabilities()
        health = adapter.health_check()
        if not capabilities.supports_audio_mapping or not capabilities.supports_dry_run:
            raise AudioValidationError("AUDIO_ADAPTER_CAPABILITY_MISSING: Unity 适配器不支持音频映射 dry-run。")
        if not health.online:
            raise AudioValidationError("AUDIO_ADAPTER_OFFLINE: Unity 适配器健康检查失败。")
        if capabilities.adapter_version != health.adapter_version:
            raise AudioValidationError("AUDIO_ADAPTER_VERSION_MISMATCH: Unity 适配器能力与健康状态版本不一致。")
        result = adapter.dry_run_audio_mapping(mapping, change_set)
        self._validate_mapping_result(result, mapping, capabilities.adapter_version, require_published=False)
        return result

    def publish_mapping(self, adapter: EngineUnityAudioAdapter, mapping: AudioMapping,
                        asset: AudioAsset, change_set: ChangeSet) -> MappingResult:
        self._validate_mapping(asset, change_set, mapping, require_approval=True)
        capabilities = adapter.get_capabilities()
        health = adapter.health_check()
        if not capabilities.supports_audio_mapping or not health.online:
            raise AudioValidationError("AUDIO_ADAPTER_UNAVAILABLE: Unity 适配器不可用。")
        if capabilities.adapter_version != health.adapter_version:
            raise AudioValidationError("AUDIO_ADAPTER_VERSION_MISMATCH: Unity 适配器能力与健康状态版本不一致。")
        result = adapter.publish_audio_mapping(mapping, change_set)
        self._validate_mapping_result(result, mapping, capabilities.adapter_version, require_published=True)
        self.apply_changeset(change_set)
        return result

    def _validate_mapping(self, asset: AudioAsset, change_set: ChangeSet, mapping: AudioMapping, *, require_approval: bool) -> None:
        state = self.availability()
        if state.state != "ready":
            raise AudioValidationError(f"AUDIO_INTEGRATION_{state.state.upper()}: {state.user_message}")
        if asset.status is not AssetStatus.PUBLISHED:
            raise AudioValidationError("AUDIO_ASSET_UNPUBLISHED: AI 或导入素材必须先获批并发布。")
        self._validate_provenance(asset.provenance, require_ai_fields=asset.provenance.provider is not None)
        if mapping.binding.audio_asset_id != asset.asset_id:
            raise AudioValidationError("AUDIO_MAPPING_ASSET_MISMATCH: 事件绑定必须引用已验证并获批的音频资产。")
        if not mapping.target_sceneops_id.startswith("so_"):
            raise AudioValidationError("AUDIO_TARGET_ID_INVALID: AudioMapping 目标必须是 so_ 前缀的 sceneops_id。")
        self._validate_changeset(change_set, asset.provenance.source_version)
        if (change_set.target_integration != "unity" or
                change_set.target_object_ids != (mapping.target_sceneops_id,)):
            raise AudioValidationError("CHANGESET_TARGET_INVALID: 映射 ChangeSet 必须定位 unity 与映射目标。")
        if (change_set.proposed_values.get("AudioSource.clip") != asset.asset_id or
                change_set.proposed_values.get("AudioSource.name") != mapping.audio_source_name or
                change_set.proposed_values.get("Mixer") != mapping.mixer_group):
            raise AudioValidationError("CHANGESET_MUTATION_MISMATCH: ChangeSet 前后值不匹配 AudioSource/Mixer 映射。")
        if require_approval and change_set.status is not ChangeSetStatus.APPROVED:
            raise AudioValidationError("CHANGESET_NOT_APPROVED: Unity 映射需要已批准 ChangeSet。")
        if require_approval:
            self._validate_approval_snapshot(change_set)

    @staticmethod
    def _validate_changeset(change_set: ChangeSet, expected_base_version: str) -> None:
        required_text = (change_set.change_set_id, change_set.base_version, change_set.target_integration,
                         change_set.rationale, change_set.expected_result, change_set.impact_scope,
                         change_set.risk, change_set.validation_plan, change_set.rollback_plan)
        if (any(not value for value in required_text) or not change_set.target_object_ids or
                not change_set.previous_values or not change_set.proposed_values or not change_set.approval_requirements):
            raise AudioValidationError("CHANGESET_INVALID: ChangeSet 缺少必填变更字段。")
        if change_set.base_version != expected_base_version:
            raise AudioValidationError("CHANGESET_TARGET_INVALID: ChangeSet 基线版本不匹配。")

    def _validate_mapping_result(self, result: MappingResult, mapping: AudioMapping,
                                 expected_adapter_version: str, *, require_published: bool) -> None:
        if result.mapping_id != mapping.mapping_id or result.target_sceneops_id != mapping.target_sceneops_id:
            raise AudioValidationError("AUDIO_MAPPING_RESULT_MISMATCH: Unity 返回的映射身份不匹配。")
        if (result.audio_asset_id != mapping.binding.audio_asset_id or
                result.audio_source_name != mapping.audio_source_name or
                result.mixer_group != mapping.mixer_group):
            raise AudioValidationError("AUDIO_MAPPING_RESULT_MISMATCH: Unity 返回的音频资产、AudioSource 或 Mixer 不匹配。")
        if result.adapter_version != expected_adapter_version:
            raise AudioValidationError("AUDIO_ADAPTER_VERSION_MISMATCH: Unity 返回的适配器版本不匹配。")
        if result.mode in (ExecutionMode.PLANNED, ExecutionMode.BLOCKED):
            raise AudioValidationError("AUDIO_MAPPING_MODE_INVALID: 已执行的适配器结果不能标记为 planned 或 blocked。")
        if require_published:
            if result.status != "published" or result.provenance is None:
                raise AudioValidationError("AUDIO_MAPPING_NOT_PUBLISHED: Unity 未确认带来源记录的映射发布。")
            self._validate_provenance(result.provenance)
            if (result.provenance.approval_state != "published" or
                    mapping.target_sceneops_id not in result.provenance.related_sceneops_ids or
                    result.provenance.adapter_version != result.adapter_version or
                    result.provenance.mode is not result.mode):
                raise AudioValidationError("AUDIO_MAPPING_PROVENANCE_INVALID: Unity 返回来源记录不匹配映射。")
        else:
            if result.status != "proposed":
                raise AudioValidationError("AUDIO_MAPPING_DRY_RUN_INVALID: dry-run 必须返回 proposed 状态。")
            if result.provenance is not None:
                self._validate_provenance(result.provenance)
                if result.provenance.adapter_version != result.adapter_version:
                    raise AudioValidationError("AUDIO_MAPPING_PROVENANCE_INVALID: dry-run 来源记录版本不匹配。")

    @staticmethod
    def _validate_provenance(provenance: Provenance, *, require_ai_fields: bool = False) -> None:
        required = (provenance.artifact_id, provenance.artifact_type, provenance.source_project_id,
                    provenance.source_version, provenance.producing_module, provenance.tool_name,
                    provenance.tool_version, provenance.creator, provenance.occurred_at,
                    provenance.approval_state)
        if any(not value for value in required) or not provenance.related_sceneops_ids:
            raise AudioValidationError("AUDIO_PROVENANCE_INCOMPLETE: 来源记录缺少必填字段。")
        if (not re.fullmatch(r"[a-fA-F0-9]{64}", provenance.sha256) or
                not re.fullmatch(r"[a-z][a-z0-9_]*", provenance.artifact_id) or
                not re.fullmatch(r"prj_[a-z0-9_]+", provenance.source_project_id) or
                any(not item.startswith("so_") for item in provenance.related_sceneops_ids)):
            raise AudioValidationError("AUDIO_PROVENANCE_INVALID: 来源 ID 或 checksum 无效。")
        if (not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", provenance.occurred_at) or
                not isinstance(provenance.mode, ExecutionMode) or
                (provenance.source_commit is not None and not provenance.source_commit)):
            raise AudioValidationError("AUDIO_PROVENANCE_INVALID: 来源时间、模式或提交无效。")
        ai_values = (provenance.provider, provenance.model, provenance.workflow_hash, provenance.prompt,
                     provenance.negative_prompt, provenance.relevant_parameters, provenance.seed)
        if (require_ai_fields or any(value is not None for value in ai_values)) and (
                not all((provenance.provider, provenance.model, provenance.workflow_hash, provenance.prompt)) or
                provenance.seed is None or not provenance.relevant_parameters or
                not re.fullmatch(r"[a-fA-F0-9]{64}", provenance.workflow_hash or "")):
            raise AudioValidationError("AUDIO_GENERATION_PROVENANCE_REQUIRED: AI 提案缺少完整生成参数。")

    @staticmethod
    def _validate_approval_snapshot(change_set: ChangeSet) -> None:
        if (not change_set.approved_by or
                not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", change_set.approved_at or "") or
                not change_set.approval_matches_content):
            raise AudioValidationError("CHANGESET_CONTENT_CHANGED: ChangeSet 内容在审批后发生变化。")

    @staticmethod
    def _transition_changeset(change_set: ChangeSet, expected: ChangeSetStatus,
                              target: ChangeSetStatus) -> ChangeSet:
        if change_set.status is not expected:
            raise AudioValidationError(f"CHANGESET_TRANSITION_INVALID: {change_set.status.value} 不能转换为 {target.value}。")
        change_set.status = target
        return change_set


def _dbfs(value: float) -> float:
    return -120.0 if value == 0 else round(20 * math.log10(value), 3)


def _waveform_peaks(values: tuple[int, ...], bins: int) -> tuple[float, ...]:
    """A bounded deterministic envelope for UI previews, never raw audio storage."""
    return tuple(round(max(abs(sample) for sample in values[(index * len(values)) // bins:
                                                            max((index + 1) * len(values) // bins, (index * len(values)) // bins + 1)]) / 32768, 4)
                 for index in range(bins))


def hero_audio_template() -> tuple[tuple[str, str, str], ...]:
    return (("gameplay.key.picked_up", "so_key_home_01", "SFX/Interact"),
            ("gameplay.door.unlocked", "so_door_home_01", "SFX/Environment"))


def warehouse_escape_template() -> tuple[tuple[str, str, str], ...]:
    return (("gameplay.switch.activated", "so_switch_warehouse_01", "SFX/Interact"),
            ("gameplay.exit.unlocked", "so_exit_warehouse_01", "SFX/Environment"))
