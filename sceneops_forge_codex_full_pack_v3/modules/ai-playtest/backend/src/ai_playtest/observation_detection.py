from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from .schemas import (
    ActionKind,
    AvailableAction,
    FailureKind,
    FailureSignal,
    GoalState,
    Observation,
    Severity,
    TestControls,
)


def detect_observation_failures(
    run_id: str,
    observation: Observation,
    controls: TestControls,
    expected_goal_ids: Sequence[str],
    permitted_actions: Sequence[AvailableAction],
    detected_at: datetime,
    step_indices: List[int],
    evidence_artifact_ids: Sequence[str] = (),
    signal_position: str = "initial",
    producer_version: str = "1.1.0",
) -> List[FailureSignal]:
    signals: List[FailureSignal] = []
    signals.extend(
        _soft_lock(
            run_id,
            observation,
            expected_goal_ids,
            permitted_actions,
            detected_at,
            step_indices,
            evidence_artifact_ids,
            signal_position,
            producer_version,
        )
    )
    signals.extend(
        _telemetry_failures(
            run_id,
            observation,
            controls,
            expected_goal_ids,
            detected_at,
            step_indices,
            evidence_artifact_ids,
            signal_position,
            producer_version,
        )
    )
    return signals


def _soft_lock(
    run_id: str,
    observation: Observation,
    expected_goal_ids: Sequence[str],
    permitted_actions: Sequence[AvailableAction],
    detected_at: datetime,
    step_indices: List[int],
    evidence_ids: Sequence[str],
    position: str,
    producer_version: str,
) -> List[FailureSignal]:
    states = {goal.goal_id: goal.state for goal in observation.goals}
    incomplete = any(
        states.get(goal_id) != GoalState.COMPLETED for goal_id in expected_goal_ids
    )
    expected = set(expected_goal_ids)
    meaningful = [
        action
        for action in permitted_actions
        if action.kind != ActionKind.CANCEL
        and (
            action.kind != ActionKind.CONFIRM
            or action.goal_relevance > 0
            or bool(expected.intersection(action.advances_goal_ids))
        )
    ]
    if not incomplete or meaningful:
        return []
    return [
        _signal(
            run_id,
            FailureKind.SOFT_LOCK,
            Severity.CRITICAL,
            "目标未完成，但运行时没有 TestCase 允许的推进或探索动作。",
            detected_at,
            step_indices,
            evidence_ids,
            position,
            producer_version=producer_version,
            details={"reason": "no_meaningful_permitted_actions"},
        )
    ]


def _telemetry_failures(
    run_id: str,
    observation: Observation,
    controls: TestControls,
    expected_goal_ids: Sequence[str],
    detected_at: datetime,
    step_indices: List[int],
    evidence_ids: Sequence[str],
    position: str,
    producer_version: str,
) -> List[FailureSignal]:
    expected = set(expected_goal_ids)
    blocked = [
        goal.goal_id
        for goal in observation.goals
        if goal.goal_id in expected and goal.state == GoalState.BLOCKED
    ]
    signals: List[FailureSignal] = []
    if blocked:
        signals.append(
            _signal(
                run_id,
                FailureKind.UNREACHABLE_GOAL,
                Severity.CRITICAL,
                "运行时明确报告 TestCase 目标不可达。",
                detected_at,
                step_indices,
                evidence_ids,
                position,
                producer_version=producer_version,
                details={"blocked_goal_ids": ",".join(sorted(blocked))},
            )
        )
    if observation.game_state.get("quest_state_mismatch") is True:
        signals.append(
            _signal(
                run_id,
                FailureKind.QUEST_STATE_MISMATCH,
                Severity.ERROR,
                "任务状态与目标进度不一致。",
                detected_at,
                step_indices,
                evidence_ids,
                position,
                producer_version=producer_version,
            )
        )
    signals.extend(
        _runtime_error_signals(
            run_id,
            observation,
            detected_at,
            step_indices,
            evidence_ids,
            position,
            producer_version,
        )
    )
    exceeded = _performance_values(observation, controls)
    if exceeded:
        signals.append(
            _signal(
                run_id,
                FailureKind.PERFORMANCE_REGRESSION,
                Severity.WARNING,
                "运行时超过 TestCase 声明的性能阈值。",
                detected_at,
                step_indices,
                evidence_ids,
                position,
                producer_version=producer_version,
                details=exceeded,
            )
        )
    return signals


def _runtime_error_signals(
    run_id: str,
    observation: Observation,
    detected_at: datetime,
    step_indices: List[int],
    evidence_ids: Sequence[str],
    position: str,
    producer_version: str,
) -> List[FailureSignal]:
    return [
        _signal(
            run_id,
            FailureKind.RUNTIME_ERROR,
            Severity.CRITICAL,
            f"运行时报告结构化错误：{error.code}",
            detected_at,
            step_indices,
            evidence_ids,
            position,
            producer_version=producer_version,
            suffix=str(error_index),
            target_sceneops_id=error.source_sceneops_id,
            details={
                "error_id": error.error_id,
                "code": error.code,
                "message": error.message,
            },
        )
        for error_index, error in enumerate(observation.runtime_errors)
    ]


def _performance_values(
    observation: Observation, controls: TestControls
) -> dict[str, float]:
    exceeded = {}
    if (
        controls.max_frame_time_ms is not None
        and observation.frame_time_ms > controls.max_frame_time_ms
    ):
        exceeded["frame_time_ms"] = observation.frame_time_ms
    if (
        controls.max_memory_mb is not None
        and observation.memory_mb is not None
        and observation.memory_mb > controls.max_memory_mb
    ):
        exceeded["memory_mb"] = observation.memory_mb
    return exceeded


def _signal(
    run_id: str,
    kind: FailureKind,
    severity: Severity,
    message: str,
    detected_at: datetime,
    step_indices: List[int],
    evidence_ids: Sequence[str],
    position: str,
    producer_version: str,
    suffix: str | None = None,
    target_sceneops_id: str | None = None,
    details: dict | None = None,
) -> FailureSignal:
    identifier_suffix = f":{suffix}" if suffix else ""
    return FailureSignal(
        signal_id=f"{run_id}:signal:{kind.value}:{position}{identifier_suffix}",
        kind=kind,
        severity=severity,
        message=message,
        detected_at=detected_at,
        step_indices=step_indices,
        target_sceneops_id=target_sceneops_id,
        evidence_artifact_ids=list(evidence_ids),
        details=details or {},
        producer_id="ai-playtest.failure-detector",
        producer_version=producer_version,
    )
