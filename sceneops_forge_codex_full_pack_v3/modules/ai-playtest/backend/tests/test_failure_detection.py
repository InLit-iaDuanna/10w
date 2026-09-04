from __future__ import annotations

import unittest

from test_support import load_test_case, run_fixture

from ai_playtest.detectors import FailureDetector
from ai_playtest.schemas import (
    ActionKind,
    ActionOutcome,
    ActionResult,
    AvailableAction,
    FailureKind,
    GoalState,
    RuntimeErrorRecord,
)


class FailureDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.detector.base"
        )
        cls.detector = FailureDetector()
        cls.controls = load_test_case().controls
        cls.expected_goal_ids = [goal.goal_id for goal in load_test_case().goals]

    def _kinds(self, current, history=()):
        return {
            signal.kind
            for signal in self.detector.evaluate(
                current,
                history,
                self.controls,
                self.expected_goal_ids,
            )
        }

    def test_timeout_is_detected_from_typed_action_outcome(self):
        step = self.base_run.steps[0].model_copy(
            update={
                "result": ActionResult(
                    outcome=ActionOutcome.TIMED_OUT,
                    detail="fixture timeout",
                    error_code="ACTION_TIMEOUT",
                    duration_ms=self.controls.action_timeout_ms,
                )
            }
        )
        self.assertIn(FailureKind.TIMEOUT, self._kinds(step))

    def test_stall_uses_configured_window_pose_epsilon_and_goal_progress(self):
        base = self.base_run.steps[0]
        stationary = base.post_observation
        updates = {
            "observation": stationary,
            "post_observation": stationary,
            "progress": stationary.goals,
        }
        first = base.model_copy(update={**updates, "step_index": 0})
        second = base.model_copy(update={**updates, "step_index": 1})
        third = base.model_copy(update={**updates, "step_index": 2})
        self.assertIn(FailureKind.STALL, self._kinds(third, [first, second]))

    def test_stall_window_does_not_ignore_first_action_progress(self):
        base = self.base_run.steps[0]
        stationary = base.model_copy(
            update={
                "observation": base.post_observation,
                "post_observation": base.post_observation,
                "progress": base.post_observation.goals,
            }
        )
        second = stationary.model_copy(update={"step_index": 1})
        third = stationary.model_copy(update={"step_index": 2})
        self.assertNotIn(FailureKind.STALL, self._kinds(third, [base, second]))

    def test_camera_or_game_state_change_prevents_false_stall(self):
        base = self.base_run.steps[0]
        stationary = base.post_observation
        unchanged = {
            "observation": stationary,
            "post_observation": stationary,
            "progress": stationary.goals,
        }
        first = base.model_copy(update={**unchanged, "step_index": 0})
        second = base.model_copy(update={**unchanged, "step_index": 1})
        rotated_pose = stationary.camera.pose.model_copy(
            update={
                "rotation_euler_deg": stationary.camera.pose.rotation_euler_deg.model_copy(
                    update={"y": 45}
                )
            }
        )
        rotated_camera = stationary.camera.model_copy(update={"pose": rotated_pose})
        changed_observation = stationary.model_copy(
            update={
                "camera": rotated_camera,
                "game_state": {**stationary.game_state, "door_hint_seen": True},
            }
        )
        third = base.model_copy(
            update={
                "step_index": 2,
                "observation": stationary,
                "post_observation": changed_observation,
                "progress": stationary.goals,
            }
        )
        self.assertNotIn(FailureKind.STALL, self._kinds(third, [first, second]))

    def test_soft_lock_requires_incomplete_goal_and_no_meaningful_action(self):
        base = self.base_run.steps[0]
        cancel = AvailableAction(
            action_id="action.only-cancel",
            kind=ActionKind.CANCEL,
            label="取消",
        )
        observation = base.post_observation.model_copy(
            update={"available_actions": [cancel]}
        )
        step = base.model_copy(update={"post_observation": observation})
        self.assertIn(FailureKind.SOFT_LOCK, self._kinds(step))

    def test_blocked_goal_is_unreachable(self):
        base = self.base_run.steps[0]
        progress = [
            base.progress[0].model_copy(
                update={"state": GoalState.BLOCKED, "detail": "no route"}
            )
        ]
        post_observation = base.post_observation.model_copy(
            update={"goals": progress}
        )
        step = base.model_copy(
            update={"post_observation": post_observation, "progress": progress}
        )
        self.assertIn(FailureKind.UNREACHABLE_GOAL, self._kinds(step))

    def test_unrelated_blocked_goal_does_not_fail_completed_test_case(self):
        base = self.base_run.steps[0]
        expected = base.progress[0].model_copy(
            update={"state": GoalState.COMPLETED, "value": 1}
        )
        unrelated = base.progress[0].model_copy(
            update={"goal_id": "goal.unrelated", "state": GoalState.BLOCKED}
        )
        progress = [expected, unrelated]
        post_observation = base.post_observation.model_copy(
            update={"goals": progress}
        )
        step = base.model_copy(
            update={"post_observation": post_observation, "progress": progress}
        )
        signals = self.detector.evaluate(
            step,
            (),
            self.controls,
            [expected.goal_id],
        )
        self.assertNotIn(
            FailureKind.UNREACHABLE_GOAL,
            {signal.kind for signal in signals},
        )

    def test_repeated_failed_interaction_is_detected(self):
        first = self.base_run.steps[3]
        second = self.base_run.steps[4]
        self.assertIn(
            FailureKind.REPEATED_FAILED_INTERACTION, self._kinds(second, [first])
        )

    def test_success_or_other_action_breaks_repeated_interaction_sequence(self):
        first = self.base_run.steps[3]
        separator = self.base_run.steps[2]
        current = self.base_run.steps[4]
        self.assertNotIn(
            FailureKind.REPEATED_FAILED_INTERACTION,
            self._kinds(current, [first, separator]),
        )

    def test_navigation_and_collider_codes_are_structured(self):
        base = self.base_run.steps[3]
        navigation = base.model_copy(
            update={
                "result": base.result.model_copy(
                    update={"error_code": "NAVMESH_PATH_BLOCKED"}
                )
            }
        )
        self.assertIn(FailureKind.NAVIGATION_ERROR, self._kinds(navigation))
        self.assertIn(FailureKind.COLLIDER_ERROR, self._kinds(base))

    def test_missing_feedback_is_detected_only_when_declared(self):
        base = self.base_run.steps[0]
        action = base.selected_action.model_copy(update={"feedback_expected": True})
        result = ActionResult(
            outcome=ActionOutcome.SUCCEEDED,
            detail="succeeded silently",
            duration_ms=10,
        )
        step = base.model_copy(update={"selected_action": action, "result": result})
        self.assertIn(FailureKind.MISSING_FEEDBACK, self._kinds(step))

    def test_quest_mismatch_runtime_error_and_configured_performance(self):
        base = self.base_run.steps[0]
        observation = base.post_observation.model_copy(
            update={
                "game_state": {"quest_state_mismatch": True},
                "runtime_errors": [
                    RuntimeErrorRecord(
                        error_id="runtime.door.null-reference",
                        code="NULL_REFERENCE",
                        message="NullReferenceException at Door.Update",
                    )
                ],
                "frame_time_ms": self.controls.max_frame_time_ms + 1,
            }
        )
        step = base.model_copy(update={"post_observation": observation})
        signals = self.detector.evaluate(step, (), self.controls)
        kinds = {signal.kind for signal in signals}
        self.assertIn(FailureKind.QUEST_STATE_MISMATCH, kinds)
        self.assertIn(FailureKind.RUNTIME_ERROR, kinds)
        self.assertIn(FailureKind.PERFORMANCE_REGRESSION, kinds)
        global_kinds = {
            FailureKind.QUEST_STATE_MISMATCH,
            FailureKind.RUNTIME_ERROR,
            FailureKind.PERFORMANCE_REGRESSION,
        }
        self.assertTrue(
            all(
                signal.target_sceneops_id is None
                for signal in signals
                if signal.kind in global_kinds
            )
        )


if __name__ == "__main__":
    unittest.main()
