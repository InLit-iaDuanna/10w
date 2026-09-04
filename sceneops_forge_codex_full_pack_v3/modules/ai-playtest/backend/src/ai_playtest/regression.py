from __future__ import annotations

from datetime import datetime
from typing import List

from .issue_identity import IssueKey, signal_issue_key

from .schemas import (
    Issue,
    MetricComparison,
    MetricDirection,
    MetricOutcome,
    PlaytestRun,
    RegressionComparison,
    RegressionMetricSpec,
    RegressionStatus,
    RunStatus,
)


class RegressionError(ValueError):
    code = "REGRESSION_NOT_COMPARABLE"


class TestConfigurationMismatchError(RegressionError):
    code = "TEST_CONFIGURATION_MISMATCH"


class ComparisonIdentityConflictError(RegressionError):
    code = "REGRESSION_COMPARISON_IDENTITY_CONFLICT"


class RegressionComparator:
    def compare(
        self,
        comparison_id: str,
        baseline: PlaytestRun,
        candidate: PlaytestRun,
        compared_at: datetime,
    ) -> RegressionComparison:
        active_statuses = {RunStatus.QUEUED, RunStatus.RUNNING}
        if baseline.status in active_statuses or candidate.status in active_statuses:
            raise RegressionError("only terminal playtest runs can be compared")
        if not baseline.comparison_eligible or not candidate.comparison_eligible:
            raise RegressionError(
                "cancelled, blocked, or integration-interrupted runs cannot be compared"
            )
        if baseline.test_case.model_dump(mode="json") != candidate.test_case.model_dump(
            mode="json"
        ):
            raise TestConfigurationMismatchError(
                "baseline and candidate must use the exact same TestCase"
            )
        if baseline.replay_action_ids != candidate.replay_action_ids:
            raise TestConfigurationMismatchError(
                "baseline and candidate must use the exact same replay action sequence"
            )
        if baseline.adapter_provenance != candidate.adapter_provenance:
            raise TestConfigurationMismatchError(
                "baseline and candidate must use the exact same adapter provenance"
            )
        if baseline.behavior_provenance != candidate.behavior_provenance:
            raise TestConfigurationMismatchError(
                "baseline and candidate must use the exact same playtest behavior versions"
            )
        if baseline.measurement_recipes != candidate.measurement_recipes:
            raise TestConfigurationMismatchError(
                "baseline and candidate must use the exact same measurement recipes"
            )
        if baseline.execution_mode != candidate.execution_mode:
            raise RegressionError("execution modes must match for an honest comparison")
        metrics = [
            self._compare_metric(spec, baseline, candidate)
            for spec in baseline.test_case.regression_metrics
        ]
        status = self._status(metrics)
        baseline_issues = {
            self._issue_key(issue): issue.issue_id for issue in baseline.issues
        }
        candidate_issues = {
            self._issue_key(issue): issue.issue_id for issue in candidate.issues
        }
        new_keys = candidate_issues.keys() - baseline_issues.keys()
        resolved_keys = baseline_issues.keys() - candidate_issues.keys()
        persistent_keys = baseline_issues.keys() & candidate_issues.keys()
        return RegressionComparison(
            comparison_id=comparison_id,
            test_case_id=baseline.test_case.test_case_id,
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            baseline_build_id=baseline.build.build_id,
            candidate_build_id=candidate.build.build_id,
            exact_configuration=True,
            status=status,
            metrics=metrics,
            new_issue_ids=sorted(candidate_issues[key] for key in new_keys),
            resolved_issue_ids=sorted(baseline_issues[key] for key in resolved_keys),
            persistent_issue_ids=sorted(candidate_issues[key] for key in persistent_keys),
            execution_mode=baseline.execution_mode,
            compared_at=compared_at,
            limitation_labels=[
                "AI 回归只按 TestCase 声明的指标比较。",
                "结果不能替代真人可用性、无障碍、乐趣或偏好测试。",
            ],
        )

    def _compare_metric(
        self,
        spec: RegressionMetricSpec,
        baseline: PlaytestRun,
        candidate: PlaytestRun,
    ) -> MetricComparison:
        before = baseline.measurements.get(spec.metric_id)
        after = candidate.measurements.get(spec.metric_id)
        if before is None or after is None:
            return MetricComparison(
                metric_id=spec.metric_id,
                baseline=before,
                candidate=after,
                delta=None,
                direction=spec.direction,
                tolerance=spec.tolerance,
                unit=spec.unit,
                outcome=MetricOutcome.MISSING,
            )
        delta = after - before
        directed_delta = delta if spec.direction == MetricDirection.MAXIMIZE else -delta
        if abs(delta) <= spec.tolerance:
            outcome = MetricOutcome.UNCHANGED
        elif directed_delta > 0:
            outcome = MetricOutcome.IMPROVED
        else:
            outcome = MetricOutcome.REGRESSED
        return MetricComparison(
            metric_id=spec.metric_id,
            baseline=before,
            candidate=after,
            delta=delta,
            direction=spec.direction,
            tolerance=spec.tolerance,
            unit=spec.unit,
            outcome=outcome,
        )

    @staticmethod
    def _status(metrics: List[MetricComparison]) -> RegressionStatus:
        outcomes = {metric.outcome for metric in metrics}
        if MetricOutcome.MISSING in outcomes or not metrics:
            return RegressionStatus.INCOMPARABLE
        improved = MetricOutcome.IMPROVED in outcomes
        regressed = MetricOutcome.REGRESSED in outcomes
        if improved and regressed:
            return RegressionStatus.MIXED
        if improved:
            return RegressionStatus.IMPROVED
        if regressed:
            return RegressionStatus.REGRESSED
        return RegressionStatus.UNCHANGED

    @staticmethod
    def _issue_key(issue: Issue) -> IssueKey:
        return signal_issue_key(issue.failure_signal)
