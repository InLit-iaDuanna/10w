from __future__ import annotations

import unittest

from adapters import DeterministicPlaytestRunnerAdapter
from test_support import (
    fixed_clock,
    load_json,
    load_test_case,
    make_adapter,
)

from ai_playtest import AIPlaytestService, InMemoryPlaytestRepository
from ai_playtest.ports import (
    ActionRejectedError,
    AdapterOfflineError,
    DryRunResult,
    ExecutionTruthError,
    RunIdentityConflictError,
    TelemetryLossError,
)
from ai_playtest.runner import AIPlaytestRunner
from ai_playtest.schemas import (
    ExecutionMode,
    FailureKind,
    RunRequest,
    RunStatus,
)


def request_for(adapter, run_id: str, mode: ExecutionMode = ExecutionMode.MOCK):
    return RunRequest(
        run_id=run_id,
        test_case=load_test_case(),
        build=adapter.build,
        execution_mode=mode,
    )


class LyingProvenanceAdapter(DeterministicPlaytestRunnerAdapter):
    def capabilities(self):
        capabilities = super().capabilities()
        return capabilities.model_copy(
            update={"supported_modes": [ExecutionMode.LIVE]}
        )


class LyingEvidenceAdapter(DeterministicPlaytestRunnerAdapter):
    def capabilities(self):
        capabilities = super().capabilities()
        return capabilities.model_copy(
            update={
                "supported_modes": [ExecutionMode.LIVE],
                "provenance": capabilities.provenance.model_copy(
                    update={"execution_mode": ExecutionMode.LIVE}
                ),
            }
        )

    def dry_run(self, test_case, build, mode):
        return DryRunResult(
            accepted=True,
            execution_mode=mode,
            build=build,
            notices=["test adapter deliberately reaches evidence truth gate"],
        )

    def reset(self, test_case, build, mode, run_id):
        session = super().reset(
            test_case, build, ExecutionMode.MOCK, run_id
        )
        return session.model_copy(update={"execution_mode": mode})


class MissingActionCapabilityAdapter(DeterministicPlaytestRunnerAdapter):
    def capabilities(self):
        capabilities = super().capabilities()
        return capabilities.model_copy(update={"supported_action_kinds": []})


class MissingControlCapabilityAdapter(DeterministicPlaytestRunnerAdapter):
    def capabilities(self):
        capabilities = super().capabilities()
        return capabilities.model_copy(
            update={
                "supports_cancellation": False,
                "supports_telemetry_recovery": False,
            }
        )


class LyingEvidenceBuildAdapter(DeterministicPlaytestRunnerAdapter):
    def capture_evidence(self, session, step_index):
        evidence = super().capture_evidence(session, step_index)
        return evidence.model_copy(update={"build_id": "build.unrelated"})


class LyingArtifactProvenanceAdapter(DeterministicPlaytestRunnerAdapter):
    def capture_evidence(self, session, step_index):
        evidence = super().capture_evidence(session, step_index)
        artifacts = [
            artifact.model_copy(update={"source_project_id": "project.unrelated"})
            for artifact in evidence.artifacts
        ]
        return evidence.model_copy(update={"artifacts": artifacts})


class LyingCapabilityIdentityAdapter(DeterministicPlaytestRunnerAdapter):
    def capabilities(self):
        capabilities = super().capabilities()
        return capabilities.model_copy(update={"adapter_version": "9.9.9"})


class LyingObservationChannelAdapter(DeterministicPlaytestRunnerAdapter):
    def get_game_state(self, session):
        return {"contradicts_observation": True}


class GappedSequenceAdapter(DeterministicPlaytestRunnerAdapter):
    def __init__(self, fixture):
        super().__init__(fixture)
        self._gap_injected = False

    def get_observation(self, session):
        observation = super().get_observation(session)
        if observation.telemetry_sequence == 1 and not self._gap_injected:
            self._gap_injected = True
            return observation.model_copy(update={"telemetry_sequence": 2})
        return observation


class ThrowingMeasurementsAdapter(DeterministicPlaytestRunnerAdapter):
    def measurements(self, session):
        raise TelemetryLossError(0)


class ThrowingLogsAdapter(DeterministicPlaytestRunnerAdapter):
    def logs(self, session):
        raise AdapterOfflineError("structured log channel unavailable")


class CapturingTimeoutAdapter(DeterministicPlaytestRunnerAdapter):
    def execute_action(self, session, action, timeout_ms, cancellation):
        self.last_timeout_ms = timeout_ms
        return super().execute_action(session, action, timeout_ms, cancellation)


class RunnerContractEdgeTests(unittest.TestCase):
    def test_step_records_post_action_observation(self):
        adapter = make_adapter("find-my-way-home-after.runtime.json")
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.post-observation")
        )
        first = run.steps[0]
        self.assertNotEqual(
            first.observation.pose.position,
            first.post_observation.pose.position,
        )
        self.assertEqual(first.progress, first.post_observation.goals)

    def test_unrelated_completed_goal_cannot_satisfy_test_case(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][-1]["goals"] = [
            {
                "goal_id": "goal.unrelated",
                "state": "completed",
                "value": 1,
                "detail": "must not satisfy the requested goal",
            }
        ]
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.unrelated-goal")
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertTrue(
            any(
                signal.kind == FailureKind.SOFT_LOCK
                for step in run.steps
                for signal in step.failure_signals
            )
        )

    def test_final_frame_errors_are_detected_after_the_action(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][-1]["runtime_errors"] = [
            {
                "error_id": "runtime.door-open.fatal",
                "code": "FATAL_AFTER_DOOR_OPEN",
                "message": "FatalAfterDoorOpen",
                "source_sceneops_id": "sceneops.home-door",
            }
        ]
        fixture["frames"][-1]["frame_time_ms"] = 999
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.final-frame-errors")
        )
        kinds = {issue.failure_signal.kind for issue in run.issues}
        self.assertIn(FailureKind.RUNTIME_ERROR, kinds)
        self.assertIn(FailureKind.PERFORMANCE_REGRESSION, kinds)
        self.assertEqual(run.status, RunStatus.FAILED)

    def test_post_action_critical_signal_stops_before_another_action(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][1]["goals"] = [
            {
                "goal_id": "goal.key-door",
                "state": "blocked",
                "value": 0.25,
                "detail": "runtime declared the goal unreachable",
            }
        ]
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.stop-on-critical")
        )
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(run.status, RunStatus.FAILED)

    def test_initial_no_action_is_a_structured_soft_lock(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["actions"] = []
        fixture["frames"][0]["results"] = {}
        fixture["frames"][0]["next_frame"] = {}
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.initial-soft-lock")
        )
        self.assertEqual(run.failure.code, "PLAYTEST_SOFT_LOCK")
        self.assertEqual(run.terminal_signals[0].kind, FailureKind.SOFT_LOCK)
        self.assertTrue(run.terminal_evidence)
        self.assertTrue(run.issues)
        self.assertIsNone(run.issues[0].restoration.step_index)
        self.assertEqual(run.issues[0].evidence, run.terminal_evidence[0])
        self.assertEqual(run.status, RunStatus.FAILED)

    def test_goal_relevant_confirm_is_executed_instead_of_false_soft_lock(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["actions"] = [
            {
                "action_id": "action.goal.confirm",
                "kind": "confirm",
                "label": "确认继续目标",
                "advances_goal_ids": ["goal.key-door"],
                "goal_relevance": 1,
            }
        ]
        fixture["frames"][0]["results"] = {
            "action.goal.confirm": {
                "outcome": "succeeded",
                "detail": "goal confirmation accepted",
                "feedback": ["confirmation"],
                "duration_ms": 10,
            }
        }
        fixture["frames"][0]["next_frame"] = {"action.goal.confirm": 4}
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.goal-confirm")
        )
        self.assertEqual(run.status, RunStatus.SUCCEEDED)
        self.assertEqual(
            [step.selected_action.action_id for step in run.steps],
            ["action.goal.confirm"],
        )

    def test_initial_completed_goal_with_runtime_error_is_not_success(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["goals"] = [
            {
                "goal_id": "goal.key-door",
                "state": "completed",
                "value": 1,
                "detail": "already complete",
            }
        ]
        fixture["frames"][0]["runtime_errors"] = [
            {
                "error_id": "runtime.initial.fatal",
                "code": "INITIAL_FATAL",
                "message": "fatal before first action",
            }
        ]
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.initial-runtime-error")
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure.code, "PLAYTEST_RUNTIME_ERROR")
        self.assertEqual(run.terminal_signals[0].kind, FailureKind.RUNTIME_ERROR)
        self.assertTrue(run.issues)

    def test_initial_clean_completion_retains_terminal_evidence(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["goals"] = [
            {
                "goal_id": "goal.key-door",
                "state": "completed",
                "value": 1,
                "detail": "already complete",
            }
        ]
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.initial-clean-completion")
        )
        self.assertEqual(run.status, RunStatus.SUCCEEDED)
        self.assertEqual(run.steps, [])
        self.assertEqual(len(run.terminal_evidence), 1)
        self.assertEqual(run.terminal_evidence[0].step_indices, [])

    def test_duration_before_first_step_is_a_structured_failure(self):
        adapter = make_adapter("find-my-way-home-after.runtime.json")
        readings = iter([0.0, 30_000.0])
        run = AIPlaytestRunner(
            adapter,
            clock=fixed_clock,
            monotonic_clock=lambda: next(readings),
        ).run(request_for(adapter, "run.duration-boundary"))
        self.assertEqual(run.failure.code, "PLAYTEST_MAX_DURATION")
        self.assertEqual(run.terminal_signals[0].kind, FailureKind.TIMEOUT)
        self.assertEqual(run.steps, [])

    def test_action_timeout_is_clamped_to_remaining_run_duration(self):
        adapter = CapturingTimeoutAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        case = load_test_case()
        case = case.model_copy(
            update={
                "controls": case.controls.model_copy(
                    update={"max_steps": 1, "max_duration_ms": 5_000}
                )
            }
        )
        readings = iter([0.0, 0.0, 4_900.0, 4_900.0])
        run = AIPlaytestRunner(
            adapter,
            clock=fixed_clock,
            monotonic_clock=lambda: next(readings),
        ).run(
            RunRequest(
                run_id="run.remaining-duration",
                test_case=case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        self.assertEqual(adapter.last_timeout_ms, 100)
        self.assertEqual(run.steps[0].result.outcome.value, "timed_out")
        self.assertEqual(run.failure.code, "PLAYTEST_MAX_DURATION")

    def test_between_step_duration_is_append_only_terminal_evidence(self):
        adapter = make_adapter("find-my-way-home-after.runtime.json")
        readings = iter([0.0, 0.0, 0.0, 0.0, 30_000.0])
        published = []
        run = AIPlaytestRunner(
            adapter,
            clock=fixed_clock,
            monotonic_clock=lambda: next(readings),
        ).run(
            request_for(adapter, "run.between-step-duration"),
            on_step=published.append,
        )
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0], run.steps[0])
        self.assertEqual(run.terminal_signals[0].kind, FailureKind.TIMEOUT)
        self.assertEqual(run.terminal_evidence[0].step_indices, [])
        timeout_issue = next(
            issue
            for issue in run.issues
            if issue.failure_signal.kind == FailureKind.TIMEOUT
        )
        self.assertGreater(timeout_issue.restoration.timeline_time_seconds, 0)

    def test_initial_warning_and_later_timeout_keep_unique_evidence(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["frame_time_ms"] = 999
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        readings = iter([0.0, 0.0, 0.0, 0.0, 30_000.0])
        run = AIPlaytestRunner(
            adapter,
            clock=fixed_clock,
            monotonic_clock=lambda: next(readings),
        ).run(request_for(adapter, "run.warning-then-duration"))
        evidence_ids = [
            evidence.evidence_id
            for evidence in run.terminal_evidence
            + [step.evidence for step in run.steps]
        ]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))
        self.assertEqual(len(run.terminal_evidence), 2)
        self.assertEqual(run.status, RunStatus.FAILED)

    def test_adapter_cannot_claim_live_with_mock_provenance(self):
        adapter = LyingProvenanceAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        with self.assertRaises(ExecutionTruthError):
            AIPlaytestRunner(adapter, clock=fixed_clock).run(
                request_for(adapter, "run.lying-provenance", ExecutionMode.LIVE)
            )

    def test_adapter_capability_identity_must_match_saved_provenance(self):
        adapter = LyingCapabilityIdentityAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        with self.assertRaises(ExecutionTruthError):
            AIPlaytestRunner(adapter, clock=fixed_clock).run(
                request_for(adapter, "run.lying-capability-identity")
            )

    def test_observation_side_channels_must_share_one_snapshot(self):
        adapter = LyingObservationChannelAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.lying-observation-channel")
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure.code, "EXECUTION_MODE_CONTRADICTION")
        self.assertEqual(run.steps, [])

    def test_test_case_action_kinds_must_fit_adapter_capabilities(self):
        adapter = MissingActionCapabilityAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        with self.assertRaises(ActionRejectedError):
            AIPlaytestRunner(adapter, clock=fixed_clock).run(
                request_for(adapter, "run.unsupported-actions")
            )

    def test_adapter_must_support_cancel_and_telemetry_recovery(self):
        adapter = MissingControlCapabilityAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        with self.assertRaises(ActionRejectedError):
            AIPlaytestRunner(adapter, clock=fixed_clock).run(
                request_for(adapter, "run.missing-control-capabilities")
            )

    def test_mock_evidence_cannot_be_returned_inside_live_run(self):
        adapter = LyingEvidenceAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.lying-evidence", ExecutionMode.LIVE)
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure.code, "EXECUTION_MODE_CONTRADICTION")
        self.assertEqual(run.steps, [])

    def test_wrong_evidence_build_returns_typed_failure(self):
        adapter = LyingEvidenceBuildAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.lying-evidence-build")
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure.code, "PLAYTEST_BUILD_MISMATCH")

    def test_wrong_artifact_project_returns_typed_execution_truth_failure(self):
        adapter = LyingArtifactProvenanceAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.lying-artifact-project")
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(run.failure.code, "EXECUTION_MODE_CONTRADICTION")

    def test_unannounced_telemetry_gap_uses_exact_recovery_sequence(self):
        adapter = GappedSequenceAdapter(
            load_json("find-my-way-home-after.runtime.json")
        )
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.sequence-gap")
        )
        kinds = {
            signal.kind for step in run.steps for signal in step.failure_signals
        }
        self.assertIn(FailureKind.TELEMETRY_LOSS, kinds)
        self.assertEqual(run.status, RunStatus.SUCCEEDED)

    def test_initial_recovered_telemetry_remains_visible_on_terminal_state(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["telemetry_loss_on_reads"] = [0]
        fixture["frames"][0]["goals"] = [
            {
                "goal_id": "goal.key-door",
                "state": "completed",
                "value": 1,
                "detail": "already complete",
            }
        ]
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter, clock=fixed_clock).run(
            request_for(adapter, "run.initial-recovery")
        )
        self.assertEqual(run.status, RunStatus.SUCCEEDED)
        self.assertIn(
            FailureKind.TELEMETRY_LOSS,
            {signal.kind for signal in run.terminal_signals},
        )
        self.assertTrue(run.terminal_evidence)

    def test_measurement_or_log_adapter_errors_return_typed_failed_runs(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        measurements_adapter = ThrowingMeasurementsAdapter(fixture)
        measurement_run = AIPlaytestRunner(
            measurements_adapter, clock=fixed_clock
        ).run(request_for(measurements_adapter, "run.measurement-error"))
        self.assertEqual(measurement_run.failure.code, "TELEMETRY_LOSS")
        self.assertTrue(measurement_run.adapter_logs)

        logs_adapter = ThrowingLogsAdapter(fixture)
        log_run = AIPlaytestRunner(logs_adapter, clock=fixed_clock).run(
            request_for(logs_adapter, "run.log-error")
        )
        self.assertEqual(log_run.failure.code, "INTEGRATION_OFFLINE")
        self.assertTrue(log_run.measurements)

    def test_registered_running_job_can_be_cancelled(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        service = AIPlaytestService(
            adapter, InMemoryPlaytestRepository(), clock=fixed_clock
        )
        cancel_results = []

        def cancel_after_first_step(_):
            cancel_results.append(service.cancel("run.service-cancel"))

        run = service.run(
            request_for(adapter, "run.service-cancel"),
            on_step=cancel_after_first_step,
        )
        self.assertTrue(cancel_results[0].accepted)
        self.assertEqual(run.status, RunStatus.CANCELLED)
        self.assertEqual(len(run.steps), 1)

    def test_completed_run_id_is_idempotent_and_conflicts_are_rejected(self):
        adapter = make_adapter("find-my-way-home-after.runtime.json")
        service = AIPlaytestService(
            adapter, InMemoryPlaytestRepository(), clock=fixed_clock
        )
        request = request_for(adapter, "run.idempotent")
        first = service.run(request)
        reads_after_first = adapter._observation_reads
        second = service.run(request)
        self.assertEqual(second, first)
        self.assertEqual(adapter._observation_reads, reads_after_first)
        changed = request.model_copy(
            update={"build": request.build.model_copy(update={"version": "other"})}
        )
        with self.assertRaises(RunIdentityConflictError):
            service.run(changed)


if __name__ == "__main__":
    unittest.main()
