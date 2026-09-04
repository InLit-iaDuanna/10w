from __future__ import annotations

from datetime import datetime
from typing import Optional

from .schemas import (
    FailureKind,
    FailureSignal,
    PlaytestRun,
    PlaytestStep,
    RunFailure,
    Severity,
)


def duration_failure(max_duration_ms: int) -> RunFailure:
    return RunFailure(
        code="PLAYTEST_MAX_DURATION",
        message=f"Playtest exceeded max_duration_ms={max_duration_ms}",
        retryable=False,
        suggested_actions=["playtest.run"],
    )


def duration_timeout_signal(
    run: PlaytestRun,
    step_index: Optional[int],
    detected_at: datetime,
) -> FailureSignal:
    return FailureSignal(
        signal_id=f"{run.run_id}:signal:timeout:terminal",
        kind=FailureKind.TIMEOUT,
        severity=Severity.CRITICAL,
        message="Playtest 达到 TestCase 的最大运行时长。",
        detected_at=detected_at,
        step_indices=[] if step_index is None else [step_index],
        details={"max_duration_ms": run.test_case.controls.max_duration_ms},
        producer_id="ai-playtest.runner-limits",
        producer_version="1.1.0",
    )


def max_steps_signal(run: PlaytestRun, step: PlaytestStep) -> FailureSignal:
    return FailureSignal(
        signal_id=f"{run.run_id}:signal:unreachable_goal:terminal",
        kind=FailureKind.UNREACHABLE_GOAL,
        severity=Severity.CRITICAL,
        message="在 TestCase 的最大步数内未达到目标。",
        detected_at=step.completed_at,
        step_indices=[step.step_index],
        evidence_artifact_ids=[
            artifact.artifact_id for artifact in step.evidence.artifacts
        ],
        details={"max_steps": run.test_case.controls.max_steps},
        producer_id="ai-playtest.runner-limits",
        producer_version="1.1.0",
    )


def telemetry_recovery_signal(step: PlaytestStep) -> FailureSignal:
    return FailureSignal(
        signal_id=f"{step.run_id}:signal:telemetry_loss:{step.step_index}",
        kind=FailureKind.TELEMETRY_LOSS,
        severity=Severity.WARNING,
        message="遥测出现缺口；本步使用 adapter 明确恢复的数据。",
        detected_at=step.completed_at,
        step_indices=[step.step_index],
        evidence_artifact_ids=[
            artifact.artifact_id for artifact in step.evidence.artifacts
        ],
        details={"recovered": True},
        producer_id="ai-playtest.telemetry-monitor",
        producer_version="1.0.0",
    )


def terminal_telemetry_recovery_signal(
    run: PlaytestRun, detected_at: datetime
) -> FailureSignal:
    return FailureSignal(
        signal_id=f"{run.run_id}:signal:telemetry_loss:initial",
        kind=FailureKind.TELEMETRY_LOSS,
        severity=Severity.WARNING,
        message="初始遥测出现缺口；运行使用 adapter 明确恢复的数据。",
        detected_at=detected_at,
        step_indices=[],
        details={"recovered": True},
        producer_id="ai-playtest.telemetry-monitor",
        producer_version="1.0.0",
    )


def detected_run_failure(run: PlaytestRun) -> RunFailure:
    critical_kinds = sorted(
        {
            signal.kind.value
            for signal in run.terminal_signals
            + [signal for step in run.steps for signal in step.failure_signals]
            if signal.severity == Severity.CRITICAL
        }
    )
    if critical_kinds:
        code = (
            f"PLAYTEST_{critical_kinds[0].upper()}"
            if len(critical_kinds) == 1
            else "PLAYTEST_CRITICAL_FAILURE"
        )
        return RunFailure(
            code=code,
            message=f"critical failure signals: {', '.join(critical_kinds)}",
            retryable=False,
            suggested_actions=["playtest.issue.open-backpin"],
        )
    return RunFailure(
        code="PLAYTEST_GOAL_NOT_COMPLETED",
        message="TestCase goals were not completed within the declared bounds",
        retryable=False,
        suggested_actions=["playtest.issue.open-backpin"],
    )
