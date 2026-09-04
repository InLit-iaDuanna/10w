from __future__ import annotations

import unittest

from test_support import load_test_case, make_adapter, run_fixture

from ai_playtest.ports import CancellationToken
from ai_playtest.runner import AIPlaytestRunner
from ai_playtest.schemas import (
    ExecutionMode,
    FailureKind,
    RegressionMetricSpec,
    RunRequest,
    RunStatus,
    TestCase,
)


class AdapterContractTests(unittest.TestCase):
    def test_fixture_adapter_reports_full_typed_capability_surface(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        health = adapter.health_check()
        capabilities = adapter.capabilities()
        self.assertTrue(health.available)
        self.assertEqual(capabilities.supported_modes, [ExecutionMode.MOCK])
        self.assertTrue(capabilities.supports_cancellation)
        self.assertTrue(capabilities.supports_telemetry_recovery)
        self.assertFalse(capabilities.retry_policy.action_retry)
        self.assertEqual(capabilities.provenance.execution_mode, ExecutionMode.MOCK)

    def test_dry_run_never_mislabels_live_as_mock(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        result = adapter.dry_run(load_test_case(), adapter.build, ExecutionMode.LIVE)
        self.assertFalse(result.accepted)
        self.assertEqual(result.execution_mode, ExecutionMode.LIVE)
        self.assertIsNotNone(result.blocked_reason)

    def test_evidence_carries_camera_trajectory_logs_and_mock_mode(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.evidence"
        )
        evidence = run.steps[-1].evidence
        self.assertEqual(evidence.execution_mode, ExecutionMode.MOCK)
        self.assertIsNotNone(evidence.camera.screenshot_artifact_id)
        self.assertEqual(len(evidence.trajectory), len(run.steps) + 1)
        self.assertEqual(
            [step.evidence.trajectory[-1] for step in run.steps],
            [step.post_observation.pose for step in run.steps],
        )
        self.assertTrue(evidence.structured_log_ids)
        self.assertEqual(evidence.run_id, run.run_id)
        artifact = evidence.artifacts[0]
        self.assertEqual(artifact.source_project_id, run.test_case.project_id)
        self.assertEqual(artifact.producing_module, "ai-playtest")
        self.assertEqual(artifact.approval_state, "unreviewed")
        self.assertEqual(artifact.execution_mode, run.execution_mode)
        self.assertIn("sceneops.home-door", artifact.related_sceneops_ids)
        self.assertTrue(run.adapter_logs)
        self.assertEqual(
            {log.log_id for log in run.adapter_logs},
            set(evidence.structured_log_ids),
        )

    def test_sparse_unvisited_measurement_is_missing_instead_of_crashing(self):
        from test_support import load_json
        from adapters import DeterministicPlaytestRunnerAdapter

        fixture = load_json("find-my-way-home-after.runtime.json")
        for frame in fixture["frames"]:
            frame["memory_mb"] = None
        fixture["frames"][-1]["memory_mb"] = 512
        fixture["metric_rules"]["peak_memory_mb"] = {
            "source": "max_observation",
            "observation_field": "memory_mb",
        }
        test_case = load_test_case()
        test_case = test_case.model_copy(
            update={
                "regression_metrics": test_case.regression_metrics
                + [
                    RegressionMetricSpec(
                        metric_id="peak_memory_mb",
                        direction="minimize",
                        unit="MB",
                    )
                ]
            }
        )
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        token = CancellationToken()
        token.cancel()
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.sparse-memory",
                test_case=test_case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            ),
            token,
        )
        self.assertEqual(run.status, RunStatus.CANCELLED)
        self.assertNotIn("peak_memory_mb", run.measurements)
        self.assertNotIn("goal_completion", run.measurements)
        self.assertNotIn("max_frame_time_ms", run.measurements)
        self.assertEqual(run.measurements["failed_interactions"], 0)

    def test_adapter_measurement_superset_is_filtered_to_test_case_contract(self):
        from test_support import load_json
        from adapters import DeterministicPlaytestRunnerAdapter

        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["metric_rules"]["optional_debug_actions"] = {
            "source": "action_count"
        }
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.metric-superset",
                test_case=load_test_case(),
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        self.assertEqual(run.status, RunStatus.SUCCEEDED)
        self.assertNotIn("optional_debug_actions", run.measurements)


class ReuseTests(unittest.TestCase):
    def test_warehouse_escape_runs_from_project_configuration_only(self):
        warehouse = TestCase.model_validate_json(
            (
                __import__("test_support").EXAMPLES
                / "warehouse-escape.test-case.json"
            ).read_text(encoding="utf-8")
        )
        run, _, service, _ = run_fixture(
            "warehouse-escape.runtime.json",
            "run.warehouse",
            test_case=warehouse,
        )
        self.assertEqual(run.test_case.project_id, "project.warehouse-escape")
        self.assertEqual(run.execution_mode, ExecutionMode.MOCK)
        kinds = {issue.failure_signal.kind for issue in run.issues}
        self.assertIn(FailureKind.NAVIGATION_ERROR, kinds)
        self.assertIn(FailureKind.UNREACHABLE_GOAL, kinds)
        backpinned = [
            issue
            for issue in run.issues
            if issue.backpin.target_id == "scene-object.warehouse-obstacle"
        ]
        self.assertTrue(backpinned)
        self.assertEqual(backpinned[0].backpin.sceneops_id, "sceneops.warehouse-obstacle")
        self.assertIn(
            "因果关系",
            " ".join(backpinned[0].backpin.reasons),
        )
        restored = service.restore_issue(backpinned[0].issue_id)
        self.assertEqual(
            restored.context.selected_sceneops_ids[0],
            "sceneops.warehouse-obstacle",
        )
        self.assertEqual(run.status, RunStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
