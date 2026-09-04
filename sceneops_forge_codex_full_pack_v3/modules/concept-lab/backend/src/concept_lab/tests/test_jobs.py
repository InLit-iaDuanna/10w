from __future__ import annotations

import pytest

from concept_lab.errors import InvalidTransitionError
from concept_lab.generation_schemas import GenerationRequest, GenerationRun
from concept_lab.jobs import transition_generation_run
from concept_lab.schemas import GenerationState


def test_generation_job_state_machine_rejects_terminal_transition(fixed_now):
    request = GenerationRequest(
        concept_id="cpt_1",
        concept_version=1,
        title="test",
        requested_views=["front"],
        prompt="test prompt",
        seed=1,
        workflow_version="test@1",
        execution_mode="mock",
        adapter_id="fixture",
    )
    run = GenerationRun(
        run_id="run_1",
        request=request,
        state="queued",
        execution_mode="mock",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    running = transition_generation_run(run, GenerationState.RUNNING, fixed_now)
    succeeded = transition_generation_run(
        running, GenerationState.SUCCEEDED, fixed_now, result_variant_id="var_1"
    )
    assert succeeded.result_variant_id == "var_1"
    with pytest.raises(InvalidTransitionError):
        transition_generation_run(succeeded, GenerationState.RUNNING, fixed_now)
