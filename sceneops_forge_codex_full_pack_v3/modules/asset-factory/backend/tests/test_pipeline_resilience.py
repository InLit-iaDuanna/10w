import tempfile
import unittest
from pathlib import Path

from asset_factory import (
    AssetPipelineService,
    InMemoryFinalizedCandidateStore,
    PipelineConflictError,
    PipelineNotFoundError,
    PipelineRequest,
    PipelineState,
    RetryPolicy,
    canonical_command_scope,
)
from asset_library import ExecutionMode, PublicationRequest
from sceneops_blender import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    DeterministicMockBlenderAdapter,
    LiveBlenderAdapter,
)

from factories import make_pipeline_service, make_record_and_request


class FlakyMockAdapter(DeterministicMockBlenderAdapter):
    def __init__(self, project_root):
        super().__init__(project_root)
        self.remaining_failures = 1

    def execute(self, command, timeout_seconds, **kwargs):
        if command.operation == BlenderOperation.SCAN_SCENE and self.remaining_failures:
            self.remaining_failures -= 1
            raise BlenderAdapterError("BLENDER_HEALTH_FAILED", "transient fixture", retryable=True)
        return super().execute(command, timeout_seconds, **kwargs)


class TimeoutMockAdapter(DeterministicMockBlenderAdapter):
    def execute(self, command, timeout_seconds, **kwargs):
        if command.operation == BlenderOperation.SCAN_SCENE:
            raise BlenderAdapterError("BLENDER_TIMEOUT", "fixture timeout", retryable=False)
        return super().execute(command, timeout_seconds, **kwargs)


class CancellingHealthAdapter(DeterministicMockBlenderAdapter):
    def __init__(self, project_root, cancel):
        super().__init__(project_root)
        self._cancel = cancel

    def health_check(self, timeout_seconds=5):
        self._cancel()
        return super().health_check(timeout_seconds)


class MissingLodMockAdapter(DeterministicMockBlenderAdapter):
    def _result_data(self, command):
        if command.operation == BlenderOperation.GENERATE_LOD:
            return {"created_sceneops_ids": []}
        return super()._result_data(command)


class PipelineResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def service_and_request(self, **request_options):
        record, request = make_record_and_request(self.root, **request_options)
        service, catalog = make_pipeline_service(self.root, record, request)
        return service, catalog, request

    def test_failed_preflight_blocks_snapshot_export_and_publication(self):
        service, catalog, request = self.service_and_request(triangle_budget=100)
        adapter = DeterministicMockBlenderAdapter(self.root, triangle_count=840)
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.FAILED)
        self.assertEqual(run.error_code, "QUALITY_GATE_FAILED")
        self.assertNotIn(BlenderOperation.SAVE_SNAPSHOT, adapter.call_counts)
        self.assertNotIn(BlenderOperation.EXPORT_ASSET, adapter.call_counts)
        self.assertEqual(catalog.get(request.spec.asset_id).versions, [])

    def test_missing_required_lod_blocks_before_export_and_publication(self):
        service, catalog, request = self.service_and_request(requires_lods=True)
        adapter = MissingLodMockAdapter(self.root)
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.ROLLED_BACK)
        self.assertEqual(run.error_code, "QUALITY_GATE_FAILED")
        self.assertIn("requires at least one LOD", run.error_message)
        self.assertNotIn(BlenderOperation.EXPORT_ASSET, adapter.call_counts)
        self.assertEqual(catalog.get(request.spec.asset_id).versions, [])

    def test_retryable_adapter_error_retries_then_succeeds(self):
        service, _, request = self.service_and_request()
        request = request.model_copy(
            update={"retry_policy": RetryPolicy(max_attempts=2, backoff_seconds=0)}, deep=True
        )
        adapter = FlakyMockAdapter(self.root)
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.SUCCEEDED)
        preflight = next(step for step in run.steps if step.kind.value == "preflight")
        self.assertGreaterEqual(preflight.attempts, 3)
        self.assertIn("BLENDER_HEALTH_FAILED", [log.code for log in preflight.logs])

    def test_idempotency_replays_exact_request_and_rejects_key_reuse(self):
        service, _, request = self.service_and_request()
        adapter = DeterministicMockBlenderAdapter(self.root)
        first = service.run(request, adapter)
        counts = dict(adapter.call_counts)
        replay = service.run(request, adapter)
        self.assertEqual(replay.model_dump(), first.model_dump())
        self.assertEqual(adapter.call_counts, counts)
        conflicting = request.model_copy(update={"pipeline_run_id": "run_conflict"}, deep=True)
        with self.assertRaisesRegex(PipelineConflictError, "IDEMPOTENCY_CONFLICT"):
            service.run(conflicting, adapter)

    def test_cancellation_stops_before_first_adapter_command(self):
        service, _, request = self.service_and_request()
        adapter = CancellingHealthAdapter(
            self.root, lambda: service.cancel(request.pipeline_run_id)
        )
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.CANCELLED)
        self.assertEqual(run.error_code, "PIPELINE_CANCELLED")
        self.assertEqual(adapter.call_counts, {})

    def test_unknown_run_cannot_plant_a_future_cancellation(self):
        service, _, request = self.service_and_request()
        with self.assertRaises(PipelineNotFoundError):
            service.cancel(request.pipeline_run_id)
        run = service.run(request, DeterministicMockBlenderAdapter(self.root))
        self.assertEqual(run.state, PipelineState.SUCCEEDED)

    def test_timeout_is_visible_and_retryable(self):
        service, _, request = self.service_and_request()
        run = service.run(request, TimeoutMockAdapter(self.root))
        self.assertEqual(run.state, PipelineState.TIMED_OUT)
        self.assertEqual(run.error_code, "BLENDER_TIMEOUT")

    def test_failure_after_snapshot_rolls_back_and_preserves_logs(self):
        service, catalog, request = self.service_and_request()
        adapter = DeterministicMockBlenderAdapter(
            self.root,
            fail_operations={
                BlenderOperation.SET_NORMALS: BlenderAdapterError(
                    "NORMALS_FAILED", "deterministic failure", retryable=False
                )
            },
        )
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.ROLLED_BACK)
        self.assertEqual(run.error_code, "NORMALS_FAILED")
        self.assertEqual(adapter.rollback_count, 1)
        self.assertTrue((self.root / run.rollback_snapshot_path).is_file())
        clean = next(step for step in run.steps if step.kind.value == "clean")
        self.assertIn("NORMALS_FAILED", [log.code for log in clean.logs])
        self.assertEqual(catalog.get(request.spec.asset_id).versions, [])

        unrelated_request = request.model_copy(
            update={"pipeline_run_id": "run_unrelated_rollback"}, deep=True
        )
        with self.assertRaisesRegex(PipelineConflictError, "target run"):
            service.rollback(run.pipeline_run_id, unrelated_request, adapter)

    def test_requested_live_mode_is_blocked_without_silent_mock_fallback(self):
        service, _, request = self.service_and_request(requested_mode=ExecutionMode.LIVE)
        live = LiveBlenderAdapter(self.root, discover_executable=False)
        run = service.run(request, live)
        self.assertEqual(run.state, PipelineState.BLOCKED)
        self.assertEqual(run.execution_mode, ExecutionMode.BLOCKED)
        self.assertEqual(run.error_code, "BLENDER_NOT_FOUND")

    def test_self_asserted_changeset_edit_is_rejected_before_blender_runs(self):
        service, _, request = self.service_and_request()
        tampered = request.model_copy(
            update={
                "change_set": request.change_set.model_copy(
                    update={"proposed_values": {"outputs": ["fbx"]}}, deep=True
                )
            },
            deep=True,
        )
        adapter = DeterministicMockBlenderAdapter(self.root)
        run = service.run(tampered, adapter)
        self.assertEqual(run.state, PipelineState.BLOCKED)
        self.assertEqual(run.error_code, "CHANGESET_APPROVAL_UNVERIFIED")
        self.assertEqual(adapter.call_counts, {})

    def test_caller_cannot_replace_the_catalog_asset_spec(self):
        service, _, request = self.service_and_request()
        tampered = request.model_copy(
            update={
                "spec": request.spec.model_copy(
                    update={"description": "caller-controlled metadata"}, deep=True
                )
            },
            deep=True,
        )
        adapter = DeterministicMockBlenderAdapter(self.root)
        run = service.run(tampered, adapter)
        self.assertEqual(run.state, PipelineState.BLOCKED)
        self.assertEqual(run.error_code, "ASSET_INPUT_MISMATCH")
        self.assertEqual(adapter.call_counts, {})

    def test_existing_published_output_is_never_overwritten(self):
        service, catalog, request = self.service_and_request()
        existing = self.root / request.output_directory / "v1" / "asset.glb"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"immutable published version")
        run = service.run(request, DeterministicMockBlenderAdapter(self.root))
        self.assertEqual(run.state, PipelineState.ROLLED_BACK)
        self.assertEqual(existing.read_bytes(), b"immutable published version")
        self.assertEqual(catalog.get(request.spec.asset_id).versions, [])

    def test_failed_publication_can_discard_and_replace_a_finalized_candidate(self):
        service, _, request = self.service_and_request()
        run = service.run(request, DeterministicMockBlenderAdapter(self.root))
        candidate = run.candidate_version
        self.assertIsNotNone(candidate)
        store = InMemoryFinalizedCandidateStore()
        store.finalize(request.change_set.change_set_id, candidate)
        store.discard(request.change_set.change_set_id, candidate)
        replacement = candidate.model_copy(
            update={
                "metrics": candidate.metrics.model_copy(
                    update={"triangle_count": candidate.metrics.triangle_count - 1},
                    deep=True,
                )
            },
            deep=True,
        )
        store.finalize(request.change_set.change_set_id, replacement)
        resolved = store.resolve(
            PublicationRequest(
                asset_id=request.spec.asset_id,
                asset_version_id=request.asset_version_id,
                change_set_id=request.change_set.change_set_id,
                approval_id=request.change_set.approval_id,
                approved_by=request.change_set.approved_by,
            )
        )
        self.assertEqual(resolved.metrics.triangle_count, replacement.metrics.triangle_count)

    def test_approval_scope_normalizes_only_structural_run_paths(self):
        approved = BlenderCommand(
            request_id="approved:01:scan_scene",
            project_id="prj_home",
            operation=BlenderOperation.SCAN_SCENE,
            source_path="Assets/approved.blend",
        )
        other = approved.model_copy(
            update={
                "request_id": "evil:01:scan_scene",
                "source_path": "Assets/evil.blend",
            },
            deep=True,
        )
        self.assertNotEqual(
            canonical_command_scope([approved], "approved"),
            canonical_command_scope([other], "evil"),
        )

    def test_blocked_run_can_retry_with_new_explicit_mock_request(self):
        service, _, blocked_request = self.service_and_request(requested_mode=ExecutionMode.LIVE)
        blocked = service.run(blocked_request, LiveBlenderAdapter(self.root, discover_executable=False))
        retry = blocked_request.model_copy(
            update={
                "pipeline_run_id": "run_hero_key_retry",
                "idempotency_key": "idem_hero_key_retry",
                "retry_of_run_id": blocked.pipeline_run_id,
                "requested_mode": ExecutionMode.MOCK,
            },
            deep=True,
        )
        result = service.retry(
            blocked.pipeline_run_id,
            retry,
            DeterministicMockBlenderAdapter(self.root),
        )
        self.assertEqual(result.state, PipelineState.SUCCEEDED)
        self.assertEqual(result.execution_mode, ExecutionMode.MOCK)


if __name__ == "__main__":
    unittest.main()
