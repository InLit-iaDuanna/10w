from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Sequence

from .ports import ActionRejectedError, ReplayUnavailableError
from .schemas import ActionKind, AgentMode, AvailableAction, GoalState, Observation, TestCase


class NoPermittedActionError(ActionRejectedError):
    code = "NO_PERMITTED_ACTION"


class DeterministicActionPolicy:
    """Selects only runtime-advertised actions inside TestCase controls."""

    version = "1.1.0"

    def __init__(self, test_case: TestCase, replay_action_ids: Sequence[str] = ()):
        self.test_case = test_case
        self.replay_action_ids = list(replay_action_ids)
        self._random = random.Random(test_case.seed)
        self._counts: Counter[str] = Counter()

    def select(self, observation: Observation, step_index: int) -> AvailableAction:
        permitted = self.permitted_actions(observation)
        if not permitted:
            raise NoPermittedActionError("runtime exposes no action allowed by TestCase")
        if step_index < len(self.replay_action_ids):
            selected = self._select_replay(permitted, step_index)
        else:
            selected = self._select_mode(permitted, observation, step_index)
        self._counts[selected.action_id] += 1
        return selected

    def permitted_actions(self, observation: Observation) -> List[AvailableAction]:
        return [
            action
            for action in observation.available_actions
            if self._is_permitted(action)
        ]

    def _is_permitted(self, action: AvailableAction) -> bool:
        controls = self.test_case.controls
        if action.kind not in controls.allowed_action_kinds:
            return False
        if action.destructive and not controls.allow_destructive:
            return False
        if self.test_case.agent_mode == AgentMode.DESTRUCTIVE and not action.destructive:
            return False
        if action.kind == ActionKind.REGISTERED:
            return action.registered_action_id in controls.registered_action_ids
        return True

    def _select_replay(
        self, actions: Sequence[AvailableAction], step_index: int
    ) -> AvailableAction:
        expected = self.replay_action_ids[step_index]
        for action in actions:
            if action.action_id == expected:
                return action
        raise ReplayUnavailableError(
            f"replay action {expected} is unavailable at step {step_index}"
        )

    def _select_mode(
        self,
        actions: Sequence[AvailableAction],
        observation: Observation,
        step_index: int,
    ) -> AvailableAction:
        mode = self.test_case.agent_mode
        if mode == AgentMode.PERSONA:
            mode = AgentMode(self.test_case.persona.base_mode)
        selectors = {
            AgentMode.SMOKE: self._select_smoke,
            AgentMode.GOAL_DRIVEN: self._select_goal_driven,
            AgentMode.EXPLORER: self._select_explorer,
            AgentMode.DESTRUCTIVE: self._select_destructive,
        }
        return selectors[mode](actions, observation, step_index)

    def _select_smoke(
        self, actions: Sequence[AvailableAction], _: Observation, step_index: int
    ) -> AvailableAction:
        order = [
            ActionKind.LOOK,
            ActionKind.MOVE,
            ActionKind.INTERACT,
            ActionKind.USE_ITEM,
            ActionKind.CONFIRM,
            ActionKind.CANCEL,
            ActionKind.REGISTERED,
        ]
        desired = order[step_index % len(order)]
        candidates = [action for action in actions if action.kind == desired]
        return sorted(candidates or actions, key=lambda action: action.action_id)[0]

    def _select_goal_driven(
        self, actions: Sequence[AvailableAction], observation: Observation, _: int
    ) -> AvailableAction:
        expected_goals = {goal.goal_id for goal in self.test_case.goals}
        active_goals = {
            goal.goal_id for goal in observation.goals if goal.state != GoalState.COMPLETED
        }.intersection(expected_goals)
        return sorted(
            actions,
            key=lambda action: (
                -int(bool(active_goals.intersection(action.advances_goal_ids))),
                -action.goal_relevance,
                action.action_id,
            ),
        )[0]

    def _select_explorer(
        self, actions: Sequence[AvailableAction], _: Observation, __: int
    ) -> AvailableAction:
        minimum = min(self._counts[action.action_id] for action in actions)
        candidates = sorted(
            [action for action in actions if self._counts[action.action_id] == minimum],
            key=lambda action: action.action_id,
        )
        return candidates[self._random.randrange(len(candidates))]

    def _select_destructive(
        self, actions: Sequence[AvailableAction], _: Observation, __: int
    ) -> AvailableAction:
        candidates = sorted(
            [action for action in actions if action.destructive],
            key=lambda action: action.action_id,
        )
        if not candidates:
            raise NoPermittedActionError(
                "destructive mode has no runtime-advertised destructive action"
            )
        return candidates[0]

    @property
    def action_counts(self) -> Dict[str, int]:
        return dict(self._counts)
