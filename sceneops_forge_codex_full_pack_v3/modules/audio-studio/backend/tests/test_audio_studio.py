import json
import pathlib
import re
import unittest

from audio_studio import (AdapterCapabilities, AdapterHealth, AssetStatus, AudioAsset, AudioMapping,
                          AudioStudioService, AudioValidationError, ChangeSet, ChangeSetStatus,
                          ExecutionMode, MappingResult, Provenance, hero_audio_template,
                          warehouse_escape_template)
from fixtures import malformed_wav, mock_hot_quiet_wav, mock_key_pickup_wav, mock_short_wav


def adapter_mapping_result(mapping, status, mode, message, provenance, *, audio_asset_id=None):
    return MappingResult(
        status, mode, "unity-mock-1", message, mapping.mapping_id, mapping.target_sceneops_id,
        audio_asset_id or mapping.binding.audio_asset_id, mapping.audio_source_name, mapping.mixer_group, provenance,
    )


class MockUnityAdapter:
    def __init__(self): self.calls, self.proposals = [], []
    def get_capabilities(self): return AdapterCapabilities(True, True, "unity-mock-1")
    def health_check(self): return AdapterHealth(True, "mock Unity online", ExecutionMode.MOCK, "unity-mock-1")
    def dry_run_audio_mapping(self, mapping, change_set):
        self.proposals.append((mapping, change_set))
        return adapter_mapping_result(mapping, "proposed", ExecutionMode.MOCK, "dry-run only", None)
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        return adapter_mapping_result(mapping, "published", ExecutionMode.MOCK, "mock mapping published", published_asset_placeholder_provenance())


class InvalidPublishAdapter(MockUnityAdapter):
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        return adapter_mapping_result(mapping, "published", ExecutionMode.MOCK, "missing provenance", None)


class UnrelatedPublishAdapter(MockUnityAdapter):
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        provenance = published_asset_placeholder_provenance()
        unrelated = provenance.__class__(**{**provenance.__dict__, "related_sceneops_ids": ("so_door_home_01",)})
        return adapter_mapping_result(mapping, "published", ExecutionMode.MOCK, "unrelated provenance", unrelated)


class InvalidProvenancePublishAdapter(MockUnityAdapter):
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        provenance = published_asset_placeholder_provenance()
        invalid = provenance.__class__(**{**provenance.__dict__, "sha256": "invalid"})
        return adapter_mapping_result(mapping, "published", ExecutionMode.MOCK, "invalid provenance", invalid)


class PlannedPublishAdapter(MockUnityAdapter):
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        return adapter_mapping_result(mapping, "published", ExecutionMode.PLANNED, "not executed", published_asset_placeholder_provenance())


class VersionMismatchAdapter(MockUnityAdapter):
    def health_check(self): return AdapterHealth(True, "stale health", ExecutionMode.MOCK, "unity-mock-0")


class AssetMismatchResultAdapter(MockUnityAdapter):
    def publish_audio_mapping(self, mapping, change_set):
        self.calls.append((mapping, change_set))
        return adapter_mapping_result(
            mapping, "published", ExecutionMode.MOCK, "wrong clip",
            published_asset_placeholder_provenance(), audio_asset_id="aud_other",
        )


def published_asset_placeholder_provenance():
    return Provenance("unity_mapping_mock_001", "unity_audio_mapping", "prj_home", "v1", "commit-fixture", ("so_key_home_01",), "engine-unity", "unity-adapter", "mock-1", "unity-mock-1", "recipe-1", "test-agent", ExecutionMode.MOCK, "2026-09-04T00:00:00Z", "published", "c" * 64)


def published_asset(analysis):
    provenance = Provenance("aud_key_pickup_v1", "audio", "prj_home", "v1", "commit-fixture", ("so_key_home_01",), "audio-studio", "wav-inspector", "fixture-1", None, "audio-analysis-1", "test-agent", ExecutionMode.MOCK, "2026-09-04T00:00:00Z", "approved", "a" * 64)
    return AudioAsset("aud_key_pickup_v1", AssetStatus.PUBLISHED, provenance, analysis)


def draft_changeset():
    return ChangeSet("cs_audio_001", ChangeSetStatus.DRAFT, "v1", "unity", ("so_key_home_01",), {"AudioSource.clip": None}, {"AudioSource.clip": "aud_key_pickup_v1", "AudioSource.name": "KeyPickupSource", "Mixer": "SFX/Interact"}, "添加钥匙拾取音", "钥匙拾取时播放音效", "so_key_home_01", "low", "运行 key pickup 回归", "移除 AudioSource 映射", ("audio:publish", "human-approval"), ())


def draft_asset_changeset(asset_id, sha256):
    return ChangeSet(
        f"cs_publish_{asset_id}", ChangeSetStatus.DRAFT, "v1", "artifact-store", (asset_id,),
        {"status": "proposal"},
        {"operation": "publish_audio_asset", "asset_id": asset_id, "source_version": "v1", "sha256": sha256},
        "发布已审音频资产", "资产进入可映射状态", asset_id, "low", "核对来源与试听", "恢复 proposal 状态",
        ("audio:publish", "human-approval"), (),
    )


def approved_changeset(service, change_set=None):
    return service.approve_changeset(
        service.submit_changeset(change_set or draft_changeset()), approver_id="usr_reviewer",
        approved_at="2026-09-04T00:01:00Z", approval_evidence=("approval-card:cs_audio_001",),
    )


class AudioStudioTests(unittest.TestCase):
    def setUp(self):
        self.service = AudioStudioService(module_enabled=True, unity_online=True)
        self.analysis = self.service.inspect_wav(mock_key_pickup_wav(), "key-pickup.wav")

    def test_manifest_events_resolve_to_complete_schemas(self):
        root = pathlib.Path(__file__).parents[2]
        events = re.findall(r"- (audio\.[\w.]+)@(\d+)", (root / "module.yaml").read_text())
        self.assertEqual(len(events), 4)
        for event_name, version in events:
            schema = json.loads((root / "contracts/events" / f"{event_name}.v{version}.schema.json").read_text())
            self.assertIn("$id", schema)
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["properties"]["event_type"]["const"], event_name)
            self.assertIn("payload", schema["required"])
            self.assertFalse(schema["properties"]["payload"]["additionalProperties"])

    def test_public_api_and_frontend_editor_are_not_placeholder(self):
        root = pathlib.Path(__file__).parents[2]
        self.assertIn("backend: audio_studio", (root / "module.yaml").read_text())
        editor = (root / "frontend/src/editors/AudioStudioEditor.tsx").read_text()
        self.assertIn("React.ReactElement", editor)
        self.assertIn("重试", editor)
        self.assertIn("波形与格式", editor)
        self.assertIn("事件绑定与 Unity 映射", editor)
        self.assertNotIn("return { state:", editor)
        commands = (root / "frontend/src/commands.ts").read_text()
        self.assertIn("inputSchema: schema", commands)
        self.assertIn("gateway.execute", commands)
        self.assertIn("schema.parse", commands)

    def test_wav_metadata_peak_loudness_waveform_and_warnings(self):
        self.assertEqual((self.analysis.metadata.format, self.analysis.metadata.channels, self.analysis.metadata.sample_rate_hz, self.analysis.metadata.bit_depth, self.analysis.metadata.duration_seconds), ("wav/pcm", 1, 8_000, 16, 1.0))
        self.assertEqual((self.analysis.peak_dbfs, self.analysis.approximate_loudness_dbfs), (-6.021, -6.021))
        self.assertEqual(self.analysis.waveform_peaks, (0.5,) * 16)
        warnings = self.service.inspect_wav(mock_hot_quiet_wav(), "hot-quiet.wav").warnings
        self.assertIn("峰值接近削波（高于 -1 dBFS）。", warnings)
        self.assertIn("近似响度很低（低于 -36 dBFS）。", warnings)

    def test_short_valid_wav_still_has_exactly_sixteen_waveform_bins(self):
        waveform = self.service.inspect_wav(mock_short_wav(), "short.wav").waveform_peaks
        self.assertEqual(len(waveform), 16)
        self.assertEqual(waveform, (0.5,) * 8 + (0.0,) * 8)

    def test_audio_spec_import_and_generation_are_proposals(self):
        spec = self.service.create_spec("spec_key", "prj_home", "钥匙拾取", ("gameplay.key.picked_up",), "SFX/Interact", "import:key.wav")
        self.assertEqual(spec.generation_reference, "import:key.wav")
        self.assertEqual(self.service.create_import_proposal("aud_imported", self.analysis, published_asset(self.analysis).provenance).status, AssetStatus.PROPOSAL)
        provenance = Provenance("aud_generated", "audio", "prj_home", "v1", None, ("so_key_home_01",), "audio-studio", "generator", "1", None, "recipe-1", "agent", ExecutionMode.MOCK, "2026-09-04T00:00:00Z", "proposal", "b" * 64, provider="fixture-generator", model="fixture-model", workflow_hash="d" * 64, prompt="soft key", negative_prompt="no voice", relevant_parameters={"duration_seconds": 1.0}, seed=7)
        generated = self.service.create_generated_proposal("aud_generated", self.analysis, provenance)
        without_negative_prompt = provenance.__class__(**{**provenance.__dict__, "negative_prompt": None})
        self.assertEqual(self.service.create_generated_proposal("aud_generated_no_negative", self.analysis, without_negative_prompt).status, AssetStatus.PROPOSAL)
        asset_change = draft_asset_changeset(generated.asset_id, generated.provenance.sha256)
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_NOT_APPROVED"):
            self.service.publish_asset(generated, asset_change)
        unrelated = approved_changeset(self.service, draft_asset_changeset("aud_other", generated.provenance.sha256))
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_ASSET_CHANGESET_MISMATCH"):
            self.service.publish_asset(generated, unrelated)
        change_set = approved_changeset(self.service, draft_asset_changeset(generated.asset_id, generated.provenance.sha256))
        published = self.service.publish_asset(generated, change_set)
        self.assertEqual((published.status, published.provenance.approval_state), (AssetStatus.PUBLISHED, "published"))
        self.assertEqual(change_set.status, ChangeSetStatus.APPLIED)

    def test_changeset_lifecycle_rejects_invalid_transitions(self):
        draft = draft_changeset()
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_TRANSITION_INVALID"):
            self.service.approve_changeset(draft, approver_id="usr_reviewer", approved_at="2026-09-04T00:01:00Z", approval_evidence=("card",))
        submitted = self.service.submit_changeset(draft)
        approved = self.service.approve_changeset(submitted, approver_id="usr_reviewer", approved_at="2026-09-04T00:01:00Z", approval_evidence=("card",))
        self.assertEqual(self.service.apply_changeset(approved).status, ChangeSetStatus.APPLIED)
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_TRANSITION_INVALID"):
            self.service.submit_changeset(approved)

    def test_changeset_requires_approval_evidence_and_matching_unity_target(self):
        evidence_missing = draft_changeset()
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_APPROVAL_EVIDENCE_REQUIRED"):
            self.service.approve_changeset(self.service.submit_changeset(evidence_missing), approver_id="usr_reviewer", approved_at="2026-09-04T00:01:00Z", approval_evidence=())
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        mismatched = draft_changeset()
        mismatched.target_integration = "engine-unity"
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_TARGET_INVALID"):
            self.service.propose_mapping(MockUnityAdapter(), mapping, published_asset(self.analysis), mismatched)

    def test_ai_provenance_and_checksum_are_complete(self):
        invalid = published_asset(self.analysis).provenance
        invalid_checksum = invalid.__class__(**{**invalid.__dict__, "sha256": "not-a-checksum"})
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_PROVENANCE_INVALID"):
            self.service.create_import_proposal("aud_invalid", self.analysis, invalid_checksum)
        incomplete_ai = invalid.__class__(**{**invalid.__dict__, "provider": "generator", "model": "model", "workflow_hash": None, "prompt": "key", "negative_prompt": "", "relevant_parameters": {}, "seed": None})
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_GENERATION_PROVENANCE_REQUIRED"):
            self.service.create_generated_proposal("aud_generated", self.analysis, incomplete_ai)

    def test_missing_malformed_and_event_failure(self):
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_FILE_MISSING"): self.service.inspect_wav(None, "missing.wav")
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_WAV_INVALID"): self.service.inspect_wav(malformed_wav(), "bad.wav")
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_EVENT_INVALID"): self.service.bind_event("key.picked", "aud")

    def test_hero_and_second_game_contract_fixture(self):
        root = pathlib.Path(__file__).parents[2]
        fixture = json.loads((root / "contracts/examples/warehouse-escape.audio-template.v1.json").read_text())
        self.assertEqual((fixture["fixture_mode"], fixture["bindings"][0]["gameplay_event"]), ("mock", "gameplay.switch.activated"))
        self.assertEqual(hero_audio_template()[1][0], "gameplay.door.unlocked")
        self.assertEqual(warehouse_escape_template()[1][1], "so_exit_warehouse_01")

    def test_disabled_offline_and_unapproved_never_call_adapter(self):
        self.assertEqual(AudioStudioService(module_enabled=False, unity_online=True).availability().state, "disabled")
        offline = AudioStudioService(module_enabled=True, unity_online=False)
        binding = offline.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        adapter = MockUnityAdapter()
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_INTEGRATION_OFFLINE"): offline.publish_mapping(adapter, mapping, published_asset(self.analysis), approved_changeset(offline))
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_NOT_APPROVED"): self.service.publish_mapping(adapter, mapping, published_asset(self.analysis), draft_changeset())
        self.assertEqual((adapter.calls, adapter.proposals), ([], []))

    def test_mapping_rejects_non_sceneops_target_id_without_adapter_call(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_invalid", binding, "obj_legacy_key", "KeyPickupSource", "SFX/Interact")
        adapter = MockUnityAdapter()
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_TARGET_ID_INVALID"):
            self.service.propose_mapping(adapter, mapping, published_asset(self.analysis), draft_changeset())
        self.assertEqual((adapter.calls, adapter.proposals), ([], []))

    def test_mapping_binds_the_validated_asset_identity(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_other")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        adapter = MockUnityAdapter()
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_MAPPING_ASSET_MISMATCH"):
            self.service.propose_mapping(adapter, mapping, published_asset(self.analysis), draft_changeset())
        self.assertEqual(adapter.proposals, [])

    def test_adapter_dry_run_then_approved_publish_contract(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        adapter = MockUnityAdapter()
        proposal = self.service.propose_mapping(adapter, mapping, published_asset(self.analysis), draft_changeset())
        self.assertEqual((proposal.status, proposal.mode, len(adapter.proposals)), ("proposed", ExecutionMode.MOCK, 1))
        published = self.service.publish_mapping(adapter, mapping, published_asset(self.analysis), approved_changeset(self.service))
        self.assertEqual((published.status, published.adapter_version, len(adapter.calls)), ("published", "unity-mock-1", 1))
        self.assertEqual(adapter.calls[0][1].status, ChangeSetStatus.APPLIED)

    def test_invalid_unity_publish_result_does_not_apply_changeset(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        change_set = approved_changeset(self.service)
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_MAPPING_NOT_PUBLISHED"):
            self.service.publish_mapping(InvalidPublishAdapter(), mapping, published_asset(self.analysis), change_set)
        self.assertEqual(change_set.status, ChangeSetStatus.APPROVED)

    def test_unrelated_unity_publish_provenance_does_not_apply_changeset(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        change_set = approved_changeset(self.service)
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_MAPPING_PROVENANCE_INVALID"):
            self.service.publish_mapping(UnrelatedPublishAdapter(), mapping, published_asset(self.analysis), change_set)
        self.assertEqual(change_set.status, ChangeSetStatus.APPROVED)

    def test_invalid_unity_publish_provenance_does_not_apply_changeset(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        change_set = approved_changeset(self.service)
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_PROVENANCE_INVALID"):
            self.service.publish_mapping(InvalidProvenancePublishAdapter(), mapping, published_asset(self.analysis), change_set)
        self.assertEqual(change_set.status, ChangeSetStatus.APPROVED)

    def test_mapping_rejects_unexecuted_mode_and_adapter_version_mismatch(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        change_set = approved_changeset(self.service)
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_MAPPING_MODE_INVALID"):
            self.service.publish_mapping(PlannedPublishAdapter(), mapping, published_asset(self.analysis), change_set)
        self.assertEqual(change_set.status, ChangeSetStatus.APPROVED)
        mismatch = VersionMismatchAdapter()
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_ADAPTER_VERSION_MISMATCH"):
            self.service.propose_mapping(mismatch, mapping, published_asset(self.analysis), draft_changeset())
        self.assertEqual(mismatch.proposals, [])

    def test_approved_content_and_adapter_result_identity_cannot_be_replaced(self):
        binding = self.service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
        mapping = AudioMapping("map_key", binding, "so_key_home_01", "KeyPickupSource", "SFX/Interact")
        mutated = approved_changeset(self.service)
        mutated.change_set_id = "cs_audio_replaced"
        mutated.rationale = "审批后替换为另一项合法说明"
        adapter = MockUnityAdapter()
        with self.assertRaisesRegex(AudioValidationError, "CHANGESET_CONTENT_CHANGED"):
            self.service.publish_mapping(adapter, mapping, published_asset(self.analysis), mutated)
        self.assertEqual(adapter.calls, [])

        clean = approved_changeset(self.service)
        wrong_result = AssetMismatchResultAdapter()
        with self.assertRaisesRegex(AudioValidationError, "AUDIO_MAPPING_RESULT_MISMATCH"):
            self.service.publish_mapping(wrong_result, mapping, published_asset(self.analysis), clean)
        self.assertEqual(clean.status, ChangeSetStatus.APPROVED)
