from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Dict

from sceneops_blender import BlenderAdapterError, BlenderCommand

from .adapter import BlenderAdapterPort
from .errors import PipelineExecutionError
from .run_support import append_log, emit_event, record_progress
from .schemas import (
    PipelineRequest,
    PipelineRun,
    PipelineState,
    ProcessingLog,
    ProcessingStep,
    StepState,
)
from .workflow import StepPlan


def execute_step(
    step: ProcessingStep,
    plan: StepPlan,
    request: PipelineRequest,
    adapter: BlenderAdapterPort,
    is_cancelled: Callable[[], bool],
    deadline: float,
    on_event: Callable[[Dict[str, object]], None],
    run: PipelineRun,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
) -> Dict[str, object]:
    step.state = StepState.RUNNING
    step.started_at = clock()
    results: Dict[str, object] = {}
    for command_index, command in enumerate(plan.commands):
        result = _execute_command(
            command,
            command_index,
            len(plan.commands),
            step,
            request,
            adapter,
            is_cancelled,
            deadline,
            clock,
            sleeper,
        )
        results[command.operation.value] = result.data
        for adapter_log in result.logs:
            step.logs.append(
                ProcessingLog(
                    timestamp=datetime.fromisoformat(adapter_log.timestamp.replace("Z", "+00:00")),
                    level=adapter_log.level,
                    code=adapter_log.code,
                    message=adapter_log.message,
                    step_id=step.step_id,
                    attempt=step.attempts,
                )
            )
        emit_event(on_event, run, "asset.pipeline.progressed", step, clock())
    step.state = StepState.SUCCEEDED
    step.progress = 1
    step.finished_at = clock()
    step.result = results
    return results


def _execute_command(
    command: BlenderCommand,
    command_index: int,
    command_count: int,
    step: ProcessingStep,
    request: PipelineRequest,
    adapter: BlenderAdapterPort,
    is_cancelled: Callable[[], bool],
    deadline: float,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
):
    for attempt in range(1, request.retry_policy.max_attempts + 1):
        _check_cancel_and_deadline(step, is_cancelled, deadline)
        remaining = deadline - time.monotonic()
        step.attempts += 1
        try:
            return adapter.execute(
                command,
                timeout_seconds=remaining,
                is_cancelled=is_cancelled,
                on_progress=lambda progress, message: record_progress(
                    step, command_index, command_count, progress, message, clock
                ),
            )
        except BlenderAdapterError as error:
            retry = error.retryable and attempt < request.retry_policy.max_attempts
            append_log(
                step,
                "warning" if retry else "error",
                error.code,
                "%s%s" % (str(error), "; retrying" if retry else ""),
                clock,
            )
            if not retry:
                step.state = _failure_step_state(error.code)
                raise
            if request.retry_policy.backoff_seconds:
                sleeper(min(request.retry_policy.backoff_seconds, max(0, remaining)))
    raise AssertionError("retry loop exhausted without a result")


def _check_cancel_and_deadline(
    step: ProcessingStep, is_cancelled: Callable[[], bool], deadline: float
) -> None:
    if is_cancelled():
        step.state = StepState.CANCELLED
        raise PipelineExecutionError(
            "PIPELINE_CANCELLED", "pipeline was cancelled", PipelineState.CANCELLED
        )
    if deadline - time.monotonic() <= 0:
        step.state = StepState.TIMED_OUT
        raise PipelineExecutionError(
            "PIPELINE_TIMEOUT", "pipeline deadline elapsed", PipelineState.TIMED_OUT, True
        )


def _failure_step_state(code: str) -> StepState:
    if code in {"BLENDER_TIMEOUT", "PIPELINE_TIMEOUT"}:
        return StepState.TIMED_OUT
    if code == "BLENDER_CANCELLED":
        return StepState.CANCELLED
    return StepState.FAILED
