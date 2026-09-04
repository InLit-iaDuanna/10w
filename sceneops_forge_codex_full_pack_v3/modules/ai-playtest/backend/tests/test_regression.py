from __future__ import annotations

import unittest

from test_support import FIXED_NOW, fixed_clock, load_test_case, make_adapter, run_fixture

from ai_playtest import AIPlaytestService, InMemoryPlaytestRepository
from ai_playtest.regression import (
    ComparisonIdentityConflictError,
    RegressionComparator,
    RegressionError,
    TestConfigurationMismatchError,
)
from ai_playtest.schemas import FailureKind, MetricOutcome, RegressionStatus


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryPlaytestRepository()
        self.before, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.regression.before",
            repository=self.repository,
        )
        self.after, adapter, self.service, _ = run_fixture(
            "find-my-way-home-after.runtime.json",
            "run.regression.after",
            repository=self.repository,
        )

    def test_same_test_before_after_uses_declared_metric_directions(self):
        comparison = self.service.compare(
            "comparison.hero-door", self.before.run_id, self.after.run_id
        )
        self.assertTrue(comparison.exact_configuration)
        self.assertEqual(comparison.status, RegressionStatus.IMPROVED)
        self.assertEqual(comparison.baseline_build_id, "build.hero.before")
        self.assertEqual(comparison.candidate_build_id, "build.hero.after")
        self.assertTrue(
            all(metric.outcome == MetricOutcome.IMPROVED for metric in comparison.metrics)
        )
        self.assertTrue(comparison.resolved_issue_ids)
        self.assertIn("不能替代真人", " ".join(comparison.limitation_labels))

    def test_comparison_id_is_idempotent_and_cannot_be_reassigned(self):
        first = self.service.compare(
            "comparison.idempotent", self.before.run_id, self.after.run_id
        )
        second = self.service.compare(
            "comparison.idempotent", self.before.run_id, self.after.run_id
        )
        self.assertEqual(second, first)
        with self.assertRaises(ComparisonIdentityConflictError):
            self.service.compare(
                "comparison.idempotent", self.after.run_id, self.before.run_id
            )
        self.assertEqual(
            self.repository.get_comparison("comparison.idempotent"), first
        )

    def test_mixed_result_is_not_hard_coded_as_improvement(self):
        candidate = self.after.model_copy(
            update={
                "measurements": {
                    "goal_completion": 1.0,
                    "failed_interactions": 0,
                    "max_frame_time_ms": 40.0,
                }
            }
        )
        comparison = RegressionComparator().compare(
            "comparison.mixed", self.before, candidate, FIXED_NOW
        )
        self.assertEqual(comparison.status, RegressionStatus.MIXED)

    def test_missing_declared_metric_is_incomparable(self):
        candidate = self.after.model_copy(update={"measurements": {}})
        comparison = RegressionComparator().compare(
            "comparison.missing", self.before, candidate, FIXED_NOW
        )
        self.assertEqual(comparison.status, RegressionStatus.INCOMPARABLE)
        self.assertTrue(
            any(metric.outcome == MetricOutcome.MISSING for metric in comparison.metrics)
        )

    def test_changed_seed_rejects_same_test_claim(self):
        changed_case = self.after.test_case.model_copy(update={"seed": 999})
        changed_run = self.after.model_copy(update={"test_case": changed_case})
        with self.assertRaises(TestConfigurationMismatchError):
            RegressionComparator().compare(
                "comparison.invalid", self.before, changed_run, FIXED_NOW
            )

    def test_active_run_cannot_be_compared_as_a_finished_regression(self):
        active = self.after.model_copy(
            update={"status": "running", "finished_at": None}
        )
        with self.assertRaises(RegressionError):
            RegressionComparator().compare(
                "comparison.active", self.before, active, FIXED_NOW
            )

    def test_interrupted_or_cancelled_run_cannot_claim_regression_direction(self):
        interrupted = self.after.model_copy(
            update={"comparison_eligible": False}
        )
        with self.assertRaises(RegressionError):
            RegressionComparator().compare(
                "comparison.interrupted", self.before, interrupted, FIXED_NOW
            )
        cancelled = self.after.model_copy(
            update={
                "status": "cancelled",
                "finished_at": FIXED_NOW,
                "comparison_eligible": False,
            }
        )
        with self.assertRaises(RegressionError):
            RegressionComparator().compare(
                "comparison.cancelled", self.before, cancelled, FIXED_NOW
            )

    def test_changed_replay_sequence_rejects_exact_configuration_claim(self):
        changed_run = self.after.model_copy(
            update={"replay_action_ids": ["action.key.move"]}
        )
        with self.assertRaises(TestConfigurationMismatchError):
            RegressionComparator().compare(
                "comparison.changed-replay", self.before, changed_run, FIXED_NOW
            )

    def test_changed_adapter_version_rejects_exact_configuration_claim(self):
        changed_run = self.after.model_copy(
            update={
                "adapter_provenance": self.after.adapter_provenance.model_copy(
                    update={"adapter_version": "2.0.0"}
                )
            }
        )
        with self.assertRaises(TestConfigurationMismatchError):
            RegressionComparator().compare(
                "comparison.changed-adapter", self.before, changed_run, FIXED_NOW
            )

    def test_changed_measurement_recipe_rejects_exact_configuration_claim(self):
        first = self.after.measurement_recipes[0]
        changed_recipe = first.model_copy(
            update={"implementation_version": "2.0.0"}
        )
        changed_run = self.after.model_copy(
            update={
                "measurement_recipes": [
                    changed_recipe,
                    *self.after.measurement_recipes[1:],
                ]
            }
        )
        with self.assertRaises(TestConfigurationMismatchError):
            RegressionComparator().compare(
                "comparison.changed-measurement-recipe",
                self.before,
                changed_run,
                FIXED_NOW,
            )

    def test_distinct_global_runtime_errors_are_new_and_resolved(self):
        baseline_issue = self.before.issues[0].model_copy(
            update={
                "failure_signal": self.before.issues[0].failure_signal.model_copy(
                    update={
                        "kind": FailureKind.RUNTIME_ERROR,
                        "target_sceneops_id": None,
                        "details": {
                            "error_id": "runtime.door-controller",
                            "code": "DOOR_CONTROLLER_FAILURE",
                        },
                    }
                )
            }
        )
        candidate_issue = self.before.issues[0].model_copy(
            update={
                "issue_id": "issue.runtime.candidate",
                "failure_signal": self.before.issues[0].failure_signal.model_copy(
                    update={
                        "kind": FailureKind.RUNTIME_ERROR,
                        "target_sceneops_id": None,
                        "details": {
                            "error_id": "runtime.inventory",
                            "code": "INVENTORY_FAILURE",
                        },
                    }
                ),
            }
        )
        baseline = self.before.model_copy(update={"issues": [baseline_issue]})
        candidate = self.after.model_copy(update={"issues": [candidate_issue]})
        comparison = RegressionComparator().compare(
            "comparison.runtime-identity", baseline, candidate, FIXED_NOW
        )
        self.assertEqual(comparison.new_issue_ids, [candidate_issue.issue_id])
        self.assertEqual(comparison.resolved_issue_ids, [baseline_issue.issue_id])
        self.assertEqual(comparison.persistent_issue_ids, [])

    def test_same_global_failure_at_different_steps_is_not_false_persistent(self):
        baseline_issue = self.before.issues[0].model_copy(
            update={
                "failure_signal": self.before.issues[0].failure_signal.model_copy(
                    update={
                        "kind": FailureKind.SOFT_LOCK,
                        "target_sceneops_id": None,
                        "step_indices": [1],
                        "details": {},
                    }
                )
            }
        )
        candidate_issue = baseline_issue.model_copy(
            update={
                "issue_id": "issue.soft-lock.candidate",
                "failure_signal": baseline_issue.failure_signal.model_copy(
                    update={"step_indices": [2]}
                ),
            }
        )
        baseline = self.before.model_copy(update={"issues": [baseline_issue]})
        candidate = self.after.model_copy(update={"issues": [candidate_issue]})
        comparison = RegressionComparator().compare(
            "comparison.soft-lock-phase", baseline, candidate, FIXED_NOW
        )
        self.assertEqual(comparison.new_issue_ids, [candidate_issue.issue_id])
        self.assertEqual(comparison.resolved_issue_ids, [baseline_issue.issue_id])
        self.assertEqual(comparison.persistent_issue_ids, [])


if __name__ == "__main__":
    unittest.main()
