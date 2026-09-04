from __future__ import annotations

from datetime import datetime
from typing import Dict, Set

from .errors import InvalidTransitionError
from .generation_schemas import GenerationRun
from .schemas import GenerationState


ALLOWED_GENERATION_TRANSITIONS: Dict[GenerationState, Set[GenerationState]] = {
    GenerationState.QUEUED: {
        GenerationState.RUNNING,
        GenerationState.BLOCKED,
        GenerationState.CANCELLED,
    },
    GenerationState.RUNNING: {
        GenerationState.SUCCEEDED,
        GenerationState.FAILED,
        GenerationState.CANCELLED,
    },
    GenerationState.SUCCEEDED: set(),
    GenerationState.FAILED: set(),
    GenerationState.BLOCKED: set(),
    GenerationState.CANCELLED: set(),
}


def transition_generation_run(
    run: GenerationRun,
    target: GenerationState,
    now: datetime,
    *,
    reason: str | None = None,
    result_variant_id: str | None = None,
) -> GenerationRun:
    if target not in ALLOWED_GENERATION_TRANSITIONS[run.state]:
        raise InvalidTransitionError(run.state.value, target.value)
    return run.model_copy(
        update={
            "state": target,
            "updated_at": now,
            "reason": reason,
            "result_variant_id": result_variant_id,
        }
    )


GENERATION_JOB_DEFINITION = {
    "id": "concept.variant.generate",
    "input": "GenerationRequest",
    "output": "GenerationOutcome",
    "states": [state.value for state in GenerationState],
    "cancellable": True,
    "retryable": True,
    "resumable": False,
}
