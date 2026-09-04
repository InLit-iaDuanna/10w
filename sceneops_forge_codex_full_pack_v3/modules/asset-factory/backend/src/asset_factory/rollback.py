from __future__ import annotations

from datetime import datetime
from typing import Callable

from sceneops_blender import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    MutationAuthorization,
)

from .adapter import BlenderAdapterPort
from .run_support import append_log, step_for
from .schemas import PipelineRequest, PipelineRun, ProcessingStepKind


def attempt_rollback(
    request: PipelineRequest,
    adapter: BlenderAdapterPort,
    snapshot_path: str,
    run: PipelineRun,
    clock: Callable[[], datetime],
) -> bool:
    command = BlenderCommand(
        request_id="%s:rollback" % request.pipeline_run_id,
        project_id=request.spec.project_id,
        operation=BlenderOperation.ROLLBACK_SNAPSHOT,
        source_path=snapshot_path,
        output_paths=[run.working_copy_path or ""],
        parameters={"snapshot_id": snapshot_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]},
        authorization=MutationAuthorization(
            change_set_id=request.change_set.change_set_id,
            approval_id=request.change_set.approval_id or "",
        ),
    )
    try:
        adapter.execute(command, timeout_seconds=request.timeout_seconds)
    except BlenderAdapterError:
        return False
    append_log(
        step_for(run, ProcessingStepKind.SNAPSHOT),
        "warning",
        "ROLLBACK_COMPLETED",
        "Restored the approved rollback snapshot.",
        clock,
    )
    return True
