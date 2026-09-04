from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from asset_library import ExecutionMode, GateStatus, PublicationBlockedError, QualityGate
from sceneops_blender import BlenderAdapterError

from .adapter import BlenderAdapterPort
from .errors import PipelineExecutionError
from .schemas import (
    PipelineRequest,
    PipelineRun,
    PipelineState,
    ProcessingLog,
    ProcessingStep,
    ProcessingStepKind,
    StepState,
)


def create_run(request: PipelineRequest, now: datetime) -> PipelineRun:
    mode = ExecutionMode.PLANNED if request.dry_run else request.requested_mode
    return PipelineRun(
        pipeline_run_id=request.pipeline_run_id,
        idempotency_key=request.idempotency_key,
        project_id=request.spec.project_id,
        asset_id=request.spec.asset_id,
        asset_version_id=request.asset_version_id,
        requested_mode=request.requested_mode,
        execution_mode=mode,
        state=PipelineState.QUEUED,
        change_set_id=request.change_set.change_set_id,
        creator=request.creator,
        steps=[
            ProcessingStep(
                step_id="%s:%s" % (request.pipeline_run_id, kind.value),
                kind=kind,
                execution_mode=mode,
            )
            for kind in ProcessingStepKind
        ],
        started_at=now,
        retry_of_run_id=request.retry_of_run_id,
    )


def adapter_mode(adapter: BlenderAdapterPort) -> ExecutionMode:
    value = getattr(adapter.mode, "value", adapter.mode)
    return ExecutionMode(value)


def step_for(run: PipelineRun, kind: ProcessingStepKind) -> ProcessingStep:
    return next(step for step in run.steps if step.kind == kind)


def skip_step(step: ProcessingStep, reason: str) -> None:
    step.state = StepState.SKIPPED
    step.skip_reason = reason
    step.progress = 1


def mark_unrun(run: PipelineRun, reason: str) -> None:
    for step in run.steps:
        if step.state == StepState.QUEUED:
            step.state = StepState.SKIPPED
            step.skip_reason = "Pipeline stopped: %s" % reason


def record_progress(
    step: ProcessingStep,
    command_index: int,
    command_count: int,
    progress: float,
    message: str,
    clock: Callable[[], datetime],
) -> None:
    step.progress = min(1, max(0, (command_index + progress) / command_count))
    append_log(step, "info", "ADAPTER_PROGRESS", message, clock)


def append_log(
    step: ProcessingStep,
    level: str,
    code: str,
    message: str,
    clock: Callable[[], datetime],
) -> None:
    step.logs.append(
        ProcessingLog(
            timestamp=clock(),
            level=level,
            code=code,
            message=message,
            step_id=step.step_id,
            attempt=step.attempts,
        )
    )


def quality_gates(result: Dict[str, object]) -> List[QualityGate]:
    return [
        QualityGate(
            gate_id=raw["gate_id"],
            label=raw["gate_id"].replace("_", " ").title(),
            status=GateStatus(raw["status"]),
            blocking=raw["blocking"],
            message=raw.get("message", "Blender validation result."),
            measurements=raw.get("measurements", {}),
        )
        for raw in result.get("gates", [])
    ]


def merge_gates(current: List[QualityGate], new: List[QualityGate]) -> List[QualityGate]:
    merged = {item.gate_id: item for item in current}
    merged.update({item.gate_id: item for item in new})
    return [merged[key] for key in sorted(merged)]


def gate_blockers(request: PipelineRequest, gates: List[QualityGate]) -> List[str]:
    by_id = {gate.gate_id: gate for gate in gates}
    blockers = [
        "required gate not reported: %s" % gate_id
        for gate_id in request.spec.required_gate_ids
        if gate_id not in by_id
    ]
    blockers.extend(
        "blocking gate %s is %s" % (gate.gate_id, gate.status.value)
        for gate in gates
        if gate.blocking and gate.status != GateStatus.PASSED
    )
    return blockers


def asset_requirement_blockers(
    request: PipelineRequest, metrics: Dict[str, object]
) -> List[str]:
    blockers: List[str] = []
    if request.spec.requires_uv and metrics.get("has_uv") is not True:
        blockers.append("AssetSpec requires UV data")
    if request.spec.requires_rig and metrics.get("is_rigged") is not True:
        blockers.append("AssetSpec requires a rig")
    lod_count = metrics.get("lod_count")
    if request.spec.requires_lods and (
        not isinstance(lod_count, int) or isinstance(lod_count, bool) or lod_count < 1
    ):
        blockers.append("AssetSpec requires at least one LOD")
    collider_kind = metrics.get("collider_kind")
    if request.spec.requires_collider and (
        not isinstance(collider_kind, str) or not collider_kind
    ):
        blockers.append("AssetSpec requires a collider")
    return blockers


def map_error(error: Exception) -> PipelineExecutionError:
    if isinstance(error, PipelineExecutionError):
        return error
    if isinstance(error, BlenderAdapterError):
        state = (
            PipelineState.TIMED_OUT
            if error.code in {"BLENDER_TIMEOUT", "PIPELINE_TIMEOUT"}
            else PipelineState.CANCELLED
            if error.code == "BLENDER_CANCELLED"
            else PipelineState.FAILED
        )
        return PipelineExecutionError(error.code, str(error), state, error.retryable)
    if isinstance(error, PublicationBlockedError):
        return PipelineExecutionError("ASSET_PUBLICATION_BLOCKED", str(error), PipelineState.FAILED)
    return PipelineExecutionError("PIPELINE_INVALID_RESULT", str(error), PipelineState.FAILED)


def emit_event(
    sink: Callable[[Dict[str, object]], None],
    run: PipelineRun,
    event_type: str,
    step: Optional[ProcessingStep],
    now: datetime,
) -> None:
    event = {
        "event_id": "evt_" + uuid4().hex,
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": now.isoformat().replace("+00:00", "Z"),
        "project_id": run.project_id,
        "correlation_id": run.pipeline_run_id,
        "causation_id": run.change_set_id,
        "actor": {"type": "user", "id": run.creator},
        "mode": run.execution_mode.value,
        "payload": {
            "pipeline_run_id": run.pipeline_run_id,
            "asset_id": run.asset_id,
            "asset_version_id": run.asset_version_id,
            "artifact_ids": [
                item.artifact_id for item in run.published_version.outputs
            ]
            if run.published_version
            else [],
            "state": run.state.value,
            "step_id": step.step_id if step else None,
            "step_state": step.state.value if step else None,
            "progress": step.progress if step else None,
        },
    }
    try:
        sink(event)
    except Exception:
        target = step or (run.steps[0] if run.steps else None)
        if target is not None:
            target.logs.append(
                ProcessingLog(
                    timestamp=now,
                    level="warning",
                    code="EVENT_DELIVERY_FAILED",
                    message="Event delivery failed; the domain result remains authoritative.",
                    step_id=target.step_id,
                    attempt=target.attempts,
                )
            )
