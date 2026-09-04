from __future__ import annotations

from typing import List, Sequence, Tuple

from .schemas import GoalProgress, GoalState, TestCase


def expected_goal_ids(test_case: TestCase) -> List[str]:
    return [goal.goal_id for goal in test_case.goals]


def goals_completed(
    progress: Sequence[GoalProgress], expected_ids: Sequence[str]
) -> bool:
    states = {goal.goal_id: goal.state for goal in progress}
    return bool(expected_ids) and all(
        states.get(goal_id) == GoalState.COMPLETED for goal_id in expected_ids
    )


def progress_projection(
    progress: Sequence[GoalProgress], expected_ids: Sequence[str]
) -> List[Tuple[str, str | None, float | None]]:
    by_id = {goal.goal_id: goal for goal in progress}
    identifiers = list(expected_ids) or sorted(by_id)
    return [
        (goal_id, by_id[goal_id].state.value, by_id[goal_id].value)
        if goal_id in by_id
        else (goal_id, None, None)
        for goal_id in identifiers
    ]
