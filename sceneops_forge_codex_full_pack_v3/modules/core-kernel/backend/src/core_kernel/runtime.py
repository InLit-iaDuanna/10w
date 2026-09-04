"""Explicit state transitions for shared job-run records."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Set

from sceneops_core_contracts import RunRecord, RunState, StandardError


ALLOWED_RUN_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.QUEUED: {RunState.RUNNING, RunState.FAILED, RunState.CANCELLED},
    RunState.RUNNING: {
        RunState.WAITING_APPROVAL,
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.WAITING_APPROVAL: {
        RunState.RUNNING,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.SUCCEEDED: {RunState.ROLLED_BACK},
    RunState.FAILED: {RunState.ROLLED_BACK},
    RunState.CANCELLED: set(),
    RunState.ROLLED_BACK: set(),
}


class InvalidRunTransition(ValueError):
    def __init__(self, current: RunState, target: RunState):
        self.error = StandardError(
            code="INVALID_RUN_TRANSITION",
            message=f"Run cannot transition from {current.value} to {target.value}.",
            details={"from_state": current.value, "to_state": target.value},
            retryable=False,
        )
        super().__init__(self.error.message)


def transition_run(
    run: RunRecord,
    target: RunState,
    occurred_at: datetime,
    *,
    error: Optional[StandardError] = None,
) -> RunRecord:
    if target not in ALLOWED_RUN_TRANSITIONS[run.state]:
        raise InvalidRunTransition(run.state, target)
    terminal = {
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.ROLLED_BACK,
    }
    update = {
        "state": target,
        "error": error,
        "started_at": occurred_at if target == RunState.RUNNING and run.started_at is None else run.started_at,
        "finished_at": occurred_at if target in terminal else None,
    }
    return RunRecord.model_validate({**run.model_dump(), **update})
