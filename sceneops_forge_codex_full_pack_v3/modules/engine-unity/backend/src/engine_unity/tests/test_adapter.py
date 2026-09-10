from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from threading import Event

from engine_unity.contracts import (
    ApprovalState,
    CommandName,
    CommandStatus,
    ExecutionMode,
)
from engine_unity.errors import ErrorCode, UnityIntegrationError

from engine_unity.tests.support import (
    SequenceRunner,
    adapter,
    approved_change_set,
    context,
    context_for,
    request,
)


BUILD_PAYLOAD = {
    "build_id": "bld_remember_home_a",
    "profile": "Remember Home A",
    "target": "StandaloneOSX",
    "output_path": "Builds/RememberHomeA.app",
    "scenes": ["Assets/Scenes/RememberHomeA.unity"],
    "source_commit": "1d4f0f3",
    "source_assets": [
        {
            "source_asset_id": "ast_home_key",
            "source_asset_version_id": "astv_home_key_001",
        }
    ],
    "required_test_runs": ["testrun_unity_editmode"],
}


class AdapterTests(unittest.TestCase):
    def test_capabilities_report_security_and_modes(self) -> None:
        capabilities = adapter().capabilities()
        self.assertFalse(capabilities.arbitrary_csharp_execution)
        self.assertEqual(20, len(capabilities.command_allowlist))
        self.assertEqual(set(ExecutionMode), set(capabilities.execution_modes))

    def test_deterministic_mock_success_is_labelled_mock(self) -> None:
        result = adapter().execute(request(CommandName.HEALTH), context())
        self.assertEqual(CommandStatus.SUCCEEDED, result.status)
        self.assertEqual(ExecutionMode.MOCK, result.mode)
        self.assertEqual("mock", result.data["executionMode"])

    def test_dry_run_returns_paths_and_does_not_execute(self) -> None:
        pending = approved_change_set(CommandName.RUN_BUILD, BUILD_PAYLOAD).model_copy(
            update={"approval_state": ApprovalState.PENDING}
        )
        command = request(
            CommandName.RUN_BUILD,
            BUILD_PAYLOAD,
            mode=ExecutionMode.PLANNED,
            change_set=pending,
        )
        result = adapter().execute(command, context())
        self.assertEqual(CommandStatus.PLANNED, result.status)
        self.assertEqual(0, result.attempts)
        self.assertTrue(result.data["target_paths"][0].endswith("RememberHomeA.app"))

    def test_execution_pauses_for_pending_approval(self) -> None:
        pending = approved_change_set(CommandName.RUN_BUILD, BUILD_PAYLOAD).model_copy(
            update={"approval_state": ApprovalState.PENDING}
        )
        command = request(
            CommandName.RUN_BUILD,
            BUILD_PAYLOAD,
            mode=ExecutionMode.MOCK,
            change_set=pending,
        )
        result = adapter().execute(command, context())
        self.assertEqual(CommandStatus.WAITING_APPROVAL, result.status)
        self.assertEqual(ErrorCode.APPROVAL_REQUIRED.value, result.error.code)

    def test_missing_live_runner_is_blocked_not_mocked(self) -> None:
        result = adapter(live_runner=None).execute(
            request(CommandName.HEALTH, mode=ExecutionMode.LIVE), context()
        )
        self.assertEqual(CommandStatus.BLOCKED, result.status)
        self.assertEqual(ExecutionMode.BLOCKED, result.mode)

    def test_duplicate_live_request_replays_as_cached(self) -> None:
        live = SequenceRunner(
            [{"status": "succeeded", "data": {"connected": True}, "logs": []}]
        )
        unity_adapter = adapter(live)
        first = unity_adapter.execute(
            request(CommandName.HEALTH, mode=ExecutionMode.LIVE), context()
        )
        second = unity_adapter.execute(
            request(
                CommandName.HEALTH,
                mode=ExecutionMode.LIVE,
                request_id="req_fixture_002",
            ),
            context(),
        )
        self.assertEqual(ExecutionMode.LIVE, first.mode)
        self.assertEqual(ExecutionMode.CACHED, second.mode)
        self.assertEqual(first.request_id, second.cached_from_request_id)
        self.assertEqual(1, live.calls)

    def test_cached_mode_only_replays_prior_live_result(self) -> None:
        live = SequenceRunner(
            [{"status": "succeeded", "data": {"connected": True}, "logs": []}]
        )
        unity_adapter = adapter(live)
        unity_adapter.execute(request(CommandName.HEALTH, mode=ExecutionMode.LIVE), context())
        replay = unity_adapter.execute(
            request(
                CommandName.HEALTH,
                mode=ExecutionMode.CACHED,
                request_id="req_fixture_003",
                idempotency_key="different-call",
                cache_key="fixture-key-001",
            ),
            context(),
        )
        self.assertEqual(CommandStatus.SUCCEEDED, replay.status)
        self.assertEqual(ExecutionMode.CACHED, replay.mode)

    def test_cancelled_command_preserves_structured_failure(self) -> None:
        cancellation = Event()
        cancellation.set()
        result = adapter().execute(
            request(CommandName.HEALTH), context(), cancellation
        )
        self.assertEqual(CommandStatus.CANCELLED, result.status)
        self.assertEqual(ErrorCode.CANCELLED.value, result.error.code)

    def test_cancelled_build_never_returns_a_build_manifest(self) -> None:
        cancellation = Event()
        cancellation.set()
        command = request(CommandName.RUN_BUILD, BUILD_PAYLOAD)
        result = adapter().execute(
            command,
            context_for(command),
            cancellation,
        )
        self.assertEqual(CommandStatus.CANCELLED, result.status)
        self.assertNotIn("buildManifest", result.data)

    def test_build_timeout_requires_explicit_retry_before_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            build = root / "Builds" / "RememberHomeA.app"
            build.mkdir(parents=True)
            (build / "player").write_bytes(b"live-build")
            live = SequenceRunner(
                [
                    UnityIntegrationError(
                        ErrorCode.TIMEOUT, "first build attempt timed out", retryable=True
                    ),
                    {
                        "status": "succeeded",
                        "data": {"result": "Succeeded", "unityVersion": "2022.3.62f3c1"},
                        "logs": [],
                    },
                ]
            )
            unity_adapter = adapter(live)
            first_command = request(
                CommandName.RUN_BUILD,
                BUILD_PAYLOAD,
                mode=ExecutionMode.LIVE,
                max_attempts=2,
                root=root,
            )
            first = unity_adapter.execute(
                first_command,
                context_for(first_command, root),
            )
            self.assertEqual(CommandStatus.FAILED, first.status)
            self.assertEqual(1, first.attempts)
            self.assertTrue(any(log.code == ErrorCode.TIMEOUT.value for log in first.logs))

            retry_command = request(
                CommandName.RUN_BUILD,
                BUILD_PAYLOAD,
                mode=ExecutionMode.LIVE,
                request_id="req_build_retry",
                max_attempts=2,
                root=root,
            )
            result = unity_adapter.execute(
                retry_command,
                context_for(retry_command, root),
            )
            self.assertEqual(CommandStatus.SUCCEEDED, result.status)
            self.assertEqual(1, result.attempts)
            self.assertEqual(2, live.calls)
            manifest = result.data["buildManifest"]
            self.assertEqual("live", manifest["execution_mode"])
            self.assertEqual(64, len(manifest["artifacts"][0]["sha256"]))
            self.assertEqual("blocked", manifest["tests"][0]["mode"])
            self.assertTrue((root / result.data["buildManifestPath"]).is_file())

    def test_idempotency_key_reuse_with_different_input_is_rejected(self) -> None:
        live = SequenceRunner(
            [{"status": "succeeded", "data": {"sceneCount": 1}, "logs": []}]
        )
        unity_adapter = adapter(live)
        first = unity_adapter.execute(
            request(
                CommandName.SCAN_PROJECT,
                {"include_packages": False},
                mode=ExecutionMode.LIVE,
            ),
            context(),
        )
        conflict = unity_adapter.execute(
            request(
                CommandName.SCAN_PROJECT,
                {"include_packages": True},
                mode=ExecutionMode.LIVE,
                request_id="req_fixture_conflict",
            ),
            context(),
        )
        self.assertEqual(CommandStatus.SUCCEEDED, first.status)
        self.assertEqual(CommandStatus.FAILED, conflict.status)
        self.assertEqual(ErrorCode.IDEMPOTENCY_CONFLICT.value, conflict.error.code)
        self.assertEqual(1, live.calls)

    def test_cached_replay_is_bound_to_actor_and_payload(self) -> None:
        live = SequenceRunner(
            [{"status": "succeeded", "data": {"sceneCount": 1}, "logs": []}]
        )
        unity_adapter = adapter(live)
        original = request(
            CommandName.SCAN_PROJECT,
            {"include_packages": False},
            mode=ExecutionMode.LIVE,
        )
        unity_adapter.execute(original, context(actor_id="usr_alice"))

        other_actor = request(
            CommandName.SCAN_PROJECT,
            {"include_packages": False},
            mode=ExecutionMode.CACHED,
            request_id="req_other_actor",
            cache_key=original.idempotency_key,
        )
        actor_result = unity_adapter.execute(
            other_actor, context(actor_id="usr_bob")
        )
        self.assertEqual(CommandStatus.FAILED, actor_result.status)
        self.assertEqual(ErrorCode.CACHE_MISS.value, actor_result.error.code)

        changed_payload = request(
            CommandName.SCAN_PROJECT,
            {"include_packages": True},
            mode=ExecutionMode.CACHED,
            request_id="req_changed_cached_payload",
            cache_key=original.idempotency_key,
        )
        payload_result = unity_adapter.execute(
            changed_payload, context(actor_id="usr_alice")
        )
        self.assertEqual(CommandStatus.FAILED, payload_result.status)
        self.assertEqual(ErrorCode.IDEMPOTENCY_CONFLICT.value, payload_result.error.code)

    def test_existing_build_manifest_blocks_build_before_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            manifest = root / "Artifacts" / "BuildManifests" / "bld_remember_home_a.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            live = SequenceRunner([])
            command = request(
                CommandName.RUN_BUILD,
                BUILD_PAYLOAD,
                mode=ExecutionMode.LIVE,
                root=root,
            )
            result = adapter(live).execute(command, context_for(command, root))
            self.assertEqual(CommandStatus.FAILED, result.status)
            self.assertEqual(ErrorCode.IDENTITY_CONFLICT.value, result.error.code)
            self.assertEqual(0, live.calls)

    def test_repeated_mock_result_remains_mock_not_cached(self) -> None:
        unity_adapter = adapter()
        unity_adapter.execute(request(CommandName.HEALTH), context())
        second = unity_adapter.execute(
            request(CommandName.HEALTH, request_id="req_mock_repeat"), context()
        )
        self.assertEqual(ExecutionMode.MOCK, second.mode)
        self.assertIsNone(second.cached_from_request_id)

    def test_compile_failure_is_visible_and_keeps_log_tail(self) -> None:
        live = SequenceRunner(
            [
                {
                    "status": "failed",
                    "errorCode": ErrorCode.COMPILE_FAILED.value,
                    "message": "Unity scripts did not compile.",
                    "retryable": False,
                    "unityLogTail": "Assets/Broken.cs(1,1): compiler error CS1002",
                    "logs": [],
                }
            ]
        )
        result = adapter(live).execute(
            request(CommandName.HEALTH, mode=ExecutionMode.LIVE), context()
        )
        self.assertEqual(CommandStatus.FAILED, result.status)
        self.assertEqual(ErrorCode.COMPILE_FAILED.value, result.error.code)
        self.assertIn("CS1002", result.error.details["unity_log_tail"])

    def test_test_failure_is_visible_and_not_retried(self) -> None:
        live = SequenceRunner(
            [
                UnityIntegrationError(
                    ErrorCode.TEST_FAILED,
                    "one Play Mode test failed",
                    details={"failed": 1, "results_path": "Artifacts/TestResults.xml"},
                )
            ]
        )
        result = adapter(live).execute(
            request(
                CommandName.RUN_TESTS,
                {"test_mode": "PlayMode"},
                mode=ExecutionMode.LIVE,
                max_attempts=3,
            ),
            context(),
        )
        self.assertEqual(CommandStatus.FAILED, result.status)
        self.assertEqual(1, result.attempts)
        self.assertEqual(1, live.calls)
        self.assertEqual(1, result.error.details["failed"])

    def test_missing_material_error_is_mapped_without_success_claim(self) -> None:
        live = SequenceRunner(
            [
                {
                    "status": "failed",
                    "errorCode": ErrorCode.MISSING_MATERIAL.value,
                    "message": "Renderer has a missing material.",
                    "retryable": False,
                    "logs": [],
                }
            ]
        )
        result = adapter(live).execute(
            request(CommandName.SCAN_PROJECT, mode=ExecutionMode.LIVE), context()
        )
        self.assertEqual(CommandStatus.FAILED, result.status)
        self.assertEqual(ErrorCode.MISSING_MATERIAL.value, result.error.code)

    def test_missing_script_and_reference_failures_are_preserved(self) -> None:
        for index, code in enumerate(
            [ErrorCode.MISSING_SCRIPT, ErrorCode.MISSING_REFERENCE], start=10
        ):
            with self.subTest(code=code.value):
                live = SequenceRunner(
                    [
                        {
                            "status": "failed",
                            "errorCode": code.value,
                            "message": f"{code.value} fixture",
                            "retryable": False,
                            "logs": [],
                        }
                    ]
                )
                result = adapter(live).execute(
                    request(
                        CommandName.SCAN_PROJECT,
                        mode=ExecutionMode.LIVE,
                        request_id=f"req_fixture_{index}",
                        idempotency_key=f"fixture-{index}",
                    ),
                    context(),
                )
                self.assertEqual(CommandStatus.FAILED, result.status)
                self.assertEqual(code.value, result.error.code)

    @staticmethod
    def _project(root: Path) -> Path:
        (root / "Assets" / "Scenes").mkdir(parents=True)
        (root / "ProjectSettings").mkdir()
        (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
            "m_EditorVersion: 2022.3.62f3c1\n", encoding="utf-8"
        )
        return root


if __name__ == "__main__":
    unittest.main()
