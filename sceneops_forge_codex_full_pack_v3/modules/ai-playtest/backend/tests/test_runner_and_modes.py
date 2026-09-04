from __future__ import annotations

import unittest
from copy import deepcopy

from pydantic import ValidationError

from test_support import load_json, load_test_case, make_adapter, run_fixture
from adapters import DeterministicPlaytestRunnerAdapter

from ai_playtest.policy import DeterministicActionPolicy, NoPermittedActionError
from ai_playtest.ports import BuildMismatchError, CancellationToken
from ai_playtest.runner import AIPlaytestRunner
from ai_playtest.schemas import (
    AgentMode,
    AvailableAction,
    BackpinStatus,
    BuildReference,
    ExecutionMode,
    FailureKind,
    RunRequest,
    RunStatus,
    TestCase,
)


class RunnerTests(unittest.TestCase):
    def test_hero_attempt_records_bounded_steps_evidence_and_real_source_id(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.hero.before"
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIsNotNone(run.failure)
        self.assertEqual(run.failure.code, "PLAYTEST_CRITICAL_FAILURE")
        self.assertEqual(run.execution_mode, ExecutionMode.MOCK)
        self.assertEqual(
            [step.selected_action.action_id for step in run.steps],
            [
                "action.key.move",
                "action.key.interact",
                "action.door.move",
                "action.door.interact",
                "action.door.interact",
            ],
        )
        self.assertLessEqual(len(run.steps), run.test_case.controls.max_steps)
        for index, step in enumerate(run.steps):
            self.assertEqual(step.step_index, index)
            self.assertEqual(step.build_id, run.build.build_id)
            self.assertEqual(step.scene_id, run.test_case.scene_id)
            self.assertTrue(step.evidence.artifacts)
            self.assertTrue(step.progress)
        collider = next(
            issue
            for issue in run.issues
            if issue.failure_signal.kind == FailureKind.COLLIDER_ERROR
        )
        self.assertEqual(collider.backpin.status, BackpinStatus.RESOLVED)
        self.assertEqual(
            collider.backpin.target_id, "component.home-door-interaction"
        )
        self.assertEqual(collider.backpin.owning_module, "logic-studio")
        self.assertIn("Mock", " ".join(run.limitation_labels))

    def test_deterministic_seed_and_replay_are_stable(self):
        first, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.replay.first"
        )
        second, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.replay.second"
        )
        first_actions = [step.selected_action.action_id for step in first.steps]
        second_actions = [step.selected_action.action_id for step in second.steps]
        self.assertEqual(first_actions, second_actions)
        self.assertTrue(
            {step.evidence.evidence_id for step in first.steps}.isdisjoint(
                {step.evidence.evidence_id for step in second.steps}
            )
        )
        self.assertTrue(
            {log.log_id for log in first.adapter_logs}.isdisjoint(
                {log.log_id for log in second.adapter_logs}
            )
        )

        adapter = make_adapter("find-my-way-home-before.runtime.json")
        replay = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.replay.explicit",
                test_case=load_test_case(),
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
                replay_action_ids=first_actions,
            )
        )
        self.assertEqual(
            [step.selected_action.action_id for step in replay.steps], first_actions
        )

    def test_telemetry_loss_is_recovered_and_remains_visible(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json",
            "run.telemetry.recovery",
            telemetry_loss_on_reads=[1],
            telemetry_recoverable=True,
        )
        signals = [signal.kind for step in run.steps for signal in step.failure_signals]
        self.assertIn(FailureKind.TELEMETRY_LOSS, signals)
        self.assertEqual(run.status, RunStatus.SUCCEEDED)

    def test_unrecoverable_telemetry_returns_structured_failure_and_keeps_steps(self):
        run, _, _, repository = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.telemetry.failed",
            telemetry_loss_on_reads=[2],
            telemetry_recoverable=False,
        )
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(run.failure.code, "TELEMETRY_LOSS")
        self.assertTrue(run.failure.retryable)
        self.assertEqual(repository.get_run(run.run_id).steps, run.steps)

    def test_build_mismatch_is_rejected(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        build = adapter.build.model_copy(update={"build_id": "build.wrong"})
        with self.assertRaises(BuildMismatchError):
            AIPlaytestRunner(adapter).run(
                RunRequest(
                    run_id="run.build.mismatch",
                    test_case=load_test_case(),
                    build=build,
                    execution_mode=ExecutionMode.MOCK,
                )
            )

    def test_cancelled_run_executes_no_action(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        token = CancellationToken()
        token.cancel()
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.cancelled",
                test_case=load_test_case(),
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            ),
            token,
        )
        self.assertEqual(run.status, RunStatus.CANCELLED)
        self.assertEqual(run.steps, [])

    def test_max_step_unreachable_signal_becomes_reproducible_issue(self):
        case = load_test_case()
        case = case.model_copy(
            update={
                "controls": case.controls.model_copy(update={"max_steps": 1})
            }
        )
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.max-step",
                test_case=case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        self.assertTrue(
            any(
                issue.failure_signal.kind == FailureKind.UNREACHABLE_GOAL
                for issue in run.issues
            )
        )
        self.assertEqual(run.measurements["goal_completion"], 0.25)
        self.assertEqual(run.measurements["failed_interactions"], 0)
        self.assertEqual(run.measurements["max_frame_time_ms"], 15.8)

    def test_action_timeout_is_recorded_as_issue(self):
        case = load_test_case()
        controls = case.controls.model_copy(
            update={"action_timeout_ms": 50, "max_steps": 1}
        )
        case = case.model_copy(update={"controls": controls})
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.action-timeout",
                test_case=case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        self.assertEqual(run.steps[0].result.outcome.value, "timed_out")
        self.assertTrue(
            any(
                issue.failure_signal.kind == FailureKind.TIMEOUT
                for issue in run.issues
            )
        )
        self.assertEqual(run.measurements["goal_completion"], 0)


class AgentModeTests(unittest.TestCase):
    def setUp(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        self.observation = adapter._observation()
        self.base = load_json("find-my-way-home-key-door.test-case.json")

    def _case(self, mode: str, **changes) -> TestCase:
        payload = deepcopy(self.base)
        payload["agent_mode"] = mode
        payload.update(changes)
        return TestCase.model_validate(payload)

    def test_smoke_is_deterministic(self):
        case = self._case("smoke")
        first = DeterministicActionPolicy(case).select(self.observation, 0)
        second = DeterministicActionPolicy(case).select(self.observation, 0)
        self.assertEqual(first.action_id, second.action_id)
        self.assertEqual(first.kind.value, "look")

    def test_complete_smoke_run_is_seed_stable(self):
        case = self._case("smoke")
        first, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.smoke.first",
            test_case=case,
        )
        second, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.smoke.second",
            test_case=case,
        )
        self.assertEqual(
            [step.selected_action.action_id for step in first.steps],
            [step.selected_action.action_id for step in second.steps],
        )

    def test_explorer_is_seeded_and_prefers_unvisited_actions(self):
        case = self._case("explorer")
        first_policy = DeterministicActionPolicy(case)
        second_policy = DeterministicActionPolicy(case)
        first = [first_policy.select(self.observation, index).action_id for index in range(4)]
        second = [second_policy.select(self.observation, index).action_id for index in range(4)]
        self.assertEqual(first, second)
        self.assertEqual(set(first[:2]), {"action.key.look", "action.key.move"})

    def test_destructive_mode_requires_containment_and_selects_only_destructive(self):
        with self.assertRaises(ValidationError):
            self._case("destructive")
        payload = deepcopy(self.base)
        payload["agent_mode"] = "destructive"
        payload["controls"]["allow_destructive"] = True
        payload["controls"]["destructive_sandbox_id"] = "sandbox.fixture"
        case = TestCase.model_validate(payload)
        action = AvailableAction(
            action_id="action.fixture.destroy",
            kind="interact",
            label="销毁测试箱",
            target_sceneops_id="sceneops.fixture-box",
            destructive=True,
        )
        observation = self.observation.model_copy(
            update={"available_actions": [action]}
        )
        self.assertTrue(DeterministicActionPolicy(case).select(observation, 0).destructive)

    def test_destructive_policy_rejects_non_destructive_runtime_actions(self):
        payload = deepcopy(self.base)
        payload["agent_mode"] = "destructive"
        payload["controls"]["allow_destructive"] = True
        payload["controls"]["destructive_sandbox_id"] = "sandbox.fixture"
        case = TestCase.model_validate(payload)
        with self.assertRaises(NoPermittedActionError):
            DeterministicActionPolicy(case).select(self.observation, 0)

    def test_goal_driven_policy_ignores_goals_outside_test_case(self):
        case = self._case("goal_driven")
        expected = self.observation.available_actions[0].model_copy(
            update={
                "action_id": "action.expected",
                "advances_goal_ids": ["goal.key-door"],
                "goal_relevance": 0.1,
            }
        )
        unrelated = self.observation.available_actions[0].model_copy(
            update={
                "action_id": "action.unrelated",
                "advances_goal_ids": ["goal.unrelated"],
                "goal_relevance": 1,
            }
        )
        unrelated_goal = self.observation.goals[0].model_copy(
            update={"goal_id": "goal.unrelated"}
        )
        observation = self.observation.model_copy(
            update={
                "goals": self.observation.goals + [unrelated_goal],
                "available_actions": [unrelated, expected],
            }
        )
        selected = DeterministicActionPolicy(case).select(observation, 0)
        self.assertEqual(selected.action_id, "action.expected")

    def test_registered_actions_require_the_test_case_allowlist(self):
        case = self._case("goal_driven")
        allowed = AvailableAction(
            action_id="action.runtime.hint",
            kind="registered",
            label="请求提示",
            registered_action_id="action.request-hint",
        )
        denied = allowed.model_copy(
            update={
                "action_id": "action.runtime.cheat",
                "registered_action_id": "action.enable-cheat",
            }
        )
        observation = self.observation.model_copy(
            update={"available_actions": [allowed, denied]}
        )
        self.assertEqual(
            DeterministicActionPolicy(case).permitted_actions(observation),
            [allowed],
        )

    def test_contained_destructive_fixture_runs_deterministically(self):
        fixture = load_json("find-my-way-home-before.runtime.json")
        fixture["adapter"]["supports_destructive_containment"] = True
        fixture["frames"][0]["actions"] = [
            {
                "action_id": "action.fixture.destroy",
                "kind": "interact",
                "label": "销毁隔离测试箱",
                "target_sceneops_id": "sceneops.fixture-box",
                "destructive": True,
                "advances_goal_ids": ["goal.key-door"],
                "goal_relevance": 1,
            }
        ]
        fixture["frames"][0]["results"] = {
            "action.fixture.destroy": {
                "outcome": "succeeded",
                "detail": "contained fixture reset",
                "feedback": ["sandbox_reset"],
                "duration_ms": 20,
            }
        }
        fixture["frames"][0]["next_frame"] = {"action.fixture.destroy": 1}
        fixture["frames"][1]["goals"] = [
            {
                "goal_id": "goal.key-door",
                "state": "completed",
                "value": 1,
                "detail": "隔离破坏测试完成",
            }
        ]
        payload = deepcopy(self.base)
        payload["agent_mode"] = "destructive"
        payload["controls"]["allow_destructive"] = True
        payload["controls"]["destructive_sandbox_id"] = "sandbox.fixture"
        case = TestCase.model_validate(payload)
        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        run = AIPlaytestRunner(adapter).run(
            RunRequest(
                run_id="run.destructive.fixture",
                test_case=case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        self.assertEqual(run.status, RunStatus.SUCCEEDED)
        self.assertEqual(run.steps[0].selected_action.action_id, "action.fixture.destroy")

    def test_persona_requires_and_preserves_heuristic_label(self):
        with self.assertRaises(ValidationError):
            self._case("persona")
        case = self._case(
            "persona",
            persona={
                "label": "谨慎探索启发式",
                "base_mode": "explorer",
                "description": "优先未尝试动作；不代表真实玩家群体。",
            },
        )
        self.assertEqual(case.agent_mode, AgentMode.PERSONA)
        self.assertIn("启发式", case.persona.label)
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.persona",
            test_case=case,
        )
        self.assertIn("Persona 是动作选择启发式", " ".join(run.limitation_labels))


if __name__ == "__main__":
    unittest.main()
