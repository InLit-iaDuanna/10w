from __future__ import annotations

from math import sqrt
from typing import Callable, List, Sequence

from .goal_scope import progress_projection
from .observation_detection import detect_observation_failures
from .schemas import (
    ActionKind,
    ActionOutcome,
    AvailableAction,
    FailureKind,
    FailureSignal,
    PlaytestStep,
    Severity,
    TestControls,
)


class FailureDetector:
    version = "1.1.0"

    def evaluate(
        self,
        current: PlaytestStep,
        history: Sequence[PlaytestStep],
        controls: TestControls,
        expected_goal_ids: Sequence[str] = (),
        permitted_actions: Sequence[AvailableAction] | None = None,
    ) -> List[FailureSignal]:
        checks: List[Callable[[], List[FailureSignal]]] = [
            lambda: self._timeout(current),
            lambda: self._stall(current, history, controls, expected_goal_ids),
            lambda: self._repeated_interaction(current, history, controls),
            lambda: self._error_code_signals(current),
            lambda: self._missing_feedback(current),
        ]
        signals = [signal for check in checks for signal in check()]
        actions = (
            list(permitted_actions)
            if permitted_actions is not None
            else current.post_observation.available_actions
        )
        evidence_ids = [
            artifact.artifact_id for artifact in current.evidence.artifacts
        ]
        signals.extend(
            detect_observation_failures(
                current.run_id,
                current.post_observation,
                controls,
                expected_goal_ids,
                actions,
                current.completed_at,
                [current.step_index],
                evidence_ids,
                str(current.step_index),
                self.version,
            )
        )
        return signals

    def _timeout(self, step: PlaytestStep) -> List[FailureSignal]:
        if step.result.outcome != ActionOutcome.TIMED_OUT:
            return []
        return [
            self._signal(
                step,
                FailureKind.TIMEOUT,
                "动作超过 TestCase 声明的执行时限。",
                Severity.ERROR,
                details={"duration_ms": step.result.duration_ms},
                target_sceneops_id=step.target_sceneops_id,
            )
        ]

    def _signal(
        self,
        step: PlaytestStep,
        kind: FailureKind,
        message: str,
        severity: Severity = Severity.ERROR,
        indices: List[int] | None = None,
        details: dict | None = None,
        target_sceneops_id: str | None = None,
    ) -> FailureSignal:
        return FailureSignal(
            signal_id=f"{step.run_id}:signal:{kind.value}:{step.step_index}",
            kind=kind,
            severity=severity,
            message=message,
            detected_at=step.completed_at,
            step_indices=indices or [step.step_index],
            target_sceneops_id=target_sceneops_id,
            evidence_artifact_ids=[
                artifact.artifact_id for artifact in step.evidence.artifacts
            ],
            details=details or {},
            producer_id="ai-playtest.failure-detector",
            producer_version=self.version,
        )

    def _stall(
        self,
        current: PlaytestStep,
        history: Sequence[PlaytestStep],
        controls: TestControls,
        expected_goal_ids: Sequence[str],
    ) -> List[FailureSignal]:
        window = list(history) + [current]
        window = window[-controls.stall_steps :]
        if len(window) < controls.stall_steps:
            return []
        stationary = all(
            self._distance(
                step.observation.pose.position,
                step.post_observation.pose.position,
            )
            <= controls.pose_epsilon_m
            for step in window
        )
        no_progress = all(
            progress_projection(step.observation.goals, expected_goal_ids)
            == progress_projection(step.progress, expected_goal_ids)
            for step in window
        )
        unchanged_runtime_state = all(
            step.observation.camera.pose == step.post_observation.camera.pose
            and step.observation.camera.field_of_view_deg
            == step.post_observation.camera.field_of_view_deg
            and step.observation.game_state == step.post_observation.game_state
            and step.observation.available_actions
            == step.post_observation.available_actions
            for step in window
        )
        if not stationary or not no_progress or not unchanged_runtime_state:
            return []
        indices = [step.step_index for step in window]
        return [
            self._signal(
                current,
                FailureKind.STALL,
                "角色位置、相机、游戏状态、可用动作与目标进度在配置窗口内均未变化。",
                indices=indices,
            )
        ]

    def _repeated_interaction(
        self,
        current: PlaytestStep,
        history: Sequence[PlaytestStep],
        controls: TestControls,
    ) -> List[FailureSignal]:
        if (
            current.selected_action.kind != ActionKind.INTERACT
            or current.result.outcome != ActionOutcome.FAILED
        ):
            return []
        matching = []
        for step in reversed(list(history) + [current]):
            is_same_failed_interaction = (
                step.selected_action.kind == ActionKind.INTERACT
                and step.selected_action.action_id == current.selected_action.action_id
                and step.target_sceneops_id == current.target_sceneops_id
                and step.result.outcome == ActionOutcome.FAILED
            )
            if not is_same_failed_interaction:
                break
            matching.append(step)
        matching.reverse()
        if len(matching) < controls.repeated_failure_threshold:
            return []
        return [
            self._signal(
                current,
                FailureKind.REPEATED_FAILED_INTERACTION,
                "同一目标的交互连续失败。",
                indices=[step.step_index for step in matching],
                details={
                    "attempts": len(matching),
                    "action_id": current.selected_action.action_id,
                },
                target_sceneops_id=current.target_sceneops_id,
            )
        ]

    def _error_code_signals(self, step: PlaytestStep) -> List[FailureSignal]:
        code = step.result.error_code or ""
        mapping = {
            FailureKind.NAVIGATION_ERROR: ("NAVIGATION_", "NAVMESH_"),
            FailureKind.COLLIDER_ERROR: ("COLLIDER_", "COLLISION_"),
        }
        signals = []
        for kind, prefixes in mapping.items():
            if code.startswith(prefixes):
                signals.append(
                    self._signal(
                        step,
                        kind,
                        f"运行时动作失败：{code}",
                        details={
                            "code": code,
                            "action_id": step.selected_action.action_id,
                        },
                        target_sceneops_id=step.target_sceneops_id,
                    )
                )
        return signals

    def _missing_feedback(self, step: PlaytestStep) -> List[FailureSignal]:
        action = step.selected_action
        if (
            action.feedback_expected
            and step.result.outcome == ActionOutcome.SUCCEEDED
            and not step.result.feedback
        ):
            return [
                self._signal(
                    step,
                    FailureKind.MISSING_FEEDBACK,
                    "动作成功但没有提供测试配置期望的玩家反馈。",
                    Severity.WARNING,
                    details={"action_id": step.selected_action.action_id},
                    target_sceneops_id=step.target_sceneops_id,
                )
            ]
        return []

    @staticmethod
    def _distance(a: object, b: object) -> float:
        return sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
