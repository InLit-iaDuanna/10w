from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, Optional

from asset_library import (
    AssetLibraryService,
    ExecutionMode,
    PublicationBlockedError,
)
from sceneops_blender import (
    BlenderAdapterError,
    BlenderOperation,
)

from .adapter import BlenderAdapterPort
from .authorization import AssetApprovalAuthority, ProjectRootRegistry
from .errors import PipelineConflictError, PipelineExecutionError, PipelineNotFoundError
from .finalization import FinalizedCandidateStore
from .publication import build_and_publish_version
from .run_ledger import RequestLedgerPort
from .rollback import attempt_rollback
from .run_support import (
    adapter_mode,
    asset_requirement_blockers,
    create_run,
    emit_event,
    gate_blockers,
    map_error,
    mark_unrun,
    merge_gates,
    quality_gates,
    skip_step,
    step_for,
)
from .run_validation import (
    catalog_input_errors,
    retry_matches_run,
    rollback_matches_run,
)
from .schemas import (
    ChangeSetState,
    PipelineRequest,
    PipelineRun,
    PipelineState,
    ProcessingStep,
    ProcessingStepKind,
    StepState,
)
from .step_execution import execute_step
from .workflow import build_workflow_plan


Clock = Callable[[], datetime]
EventSink = Callable[[Dict[str, object]], None]


class AssetPipelineService:
    def __init__(
        self,
        catalog: AssetLibraryService,
        approval_authority: AssetApprovalAuthority,
        project_roots: ProjectRootRegistry,
        candidate_store: FinalizedCandidateStore,
        request_ledger: RequestLedgerPort,
        *,
        clock: Clock = lambda: datetime.now(timezone.utc),
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._catalog = catalog
        self._approval_authority = approval_authority
        self._project_roots = project_roots
        self._candidate_store = candidate_store
        self._clock = clock
        self._sleeper = sleeper
        self._runs: Dict[str, PipelineRun] = {}
        self._runs_lock = Lock()
        self._ledger = request_ledger

    def run(
        self,
        request: PipelineRequest,
        adapter: BlenderAdapterPort,
        on_event: EventSink = lambda _event: None,
    ) -> PipelineRun:
        replay = self._ledger.reserve(request)
        if replay is not None:
            return replay
        try:
            return self._run_reserved(request, adapter, on_event)
        except BaseException:
            self._ledger.abort(request)
            raise

    def _run_reserved(
        self,
        request: PipelineRequest,
        adapter: BlenderAdapterPort,
        on_event: EventSink,
    ) -> PipelineRun:
        run = create_run(request, self._clock())
        token = self._ledger.token_for(request.pipeline_run_id)
        with self._runs_lock:
            self._runs[run.pipeline_run_id] = run
        catalog_errors = catalog_input_errors(self._catalog, request)
        if catalog_errors:
            return self._blocked(
                request,
                run,
                "ASSET_INPUT_MISMATCH",
                "; ".join(catalog_errors),
            )
        if request.dry_run:
            return self._preview(request, run, adapter, PipelineState.PLANNED)
        if request.change_set.state != ChangeSetState.APPROVED:
            return self._preview(request, run, adapter, PipelineState.WAITING_APPROVAL)

        approval_errors = self._approval_authority.verify_change_set(
            request.change_set,
            request.spec.asset_id,
            request.asset_version_id,
        )
        if approval_errors:
            return self._blocked(
                request,
                run,
                "CHANGESET_APPROVAL_UNVERIFIED",
                "; ".join(approval_errors),
            )
        try:
            project_root = self._project_roots.resolve(request.spec.project_id)
        except (LookupError, OSError, ValueError) as error:
            return self._blocked(request, run, "PROJECT_ROOT_UNAVAILABLE", str(error))
        if Path(adapter.project_root).resolve() != project_root:
            return self._blocked(
                request,
                run,
                "PROJECT_ROOT_MISMATCH",
                "Selected Blender adapter is not bound to the registered project root.",
            )

        plans = build_workflow_plan(request, preview=False)
        workflow_errors = self._approval_authority.verify_workflow(
            request.change_set,
            request.pipeline_run_id,
            (command for plan in plans for command in plan.commands),
        )
        if workflow_errors:
            return self._blocked(
                request,
                run,
                "CHANGESET_SCOPE_UNVERIFIED",
                "; ".join(workflow_errors),
            )

        selected_mode = adapter_mode(adapter)
        if selected_mode != request.requested_mode:
            return self._blocked(
                request,
                run,
                "EXECUTION_MODE_MISMATCH",
                "Requested %s but the selected adapter is %s."
                % (request.requested_mode.value, selected_mode.value),
            )
        health = adapter.health_check(min(5, request.timeout_seconds))
        if not health.healthy:
            return self._blocked(request, run, health.code, health.message)

        run.execution_mode = selected_mode
        run.state = PipelineState.RUNNING
        deadline = time.monotonic() + request.timeout_seconds
        export_data: Dict[str, object] = {}
        metrics: Dict[str, object] = {}
        snapshot_path: Optional[str] = None
        try:
            emit_event(on_event, run, "asset.pipeline.started", None, self._clock())
            for plan in plans:
                step = step_for(run, plan.kind)
                if plan.skip_reason:
                    skip_step(step, plan.skip_reason)
                    emit_event(on_event, run, "asset.pipeline.progressed", step, self._clock())
                    continue
                if plan.kind == ProcessingStepKind.PUBLISH:
                    self._run_publication_step(
                        step,
                        request,
                        run,
                        export_data,
                        metrics,
                        health.version or "unknown",
                        project_root,
                    )
                else:
                    result = execute_step(
                        step,
                        plan,
                        request,
                        adapter,
                        token.is_cancelled,
                        deadline,
                        on_event,
                        run,
                        self._clock,
                        self._sleeper,
                    )
                    if plan.kind == ProcessingStepKind.SNAPSHOT:
                        snapshot_result = result[BlenderOperation.SAVE_SNAPSHOT.value]
                        snapshot_path = snapshot_result["snapshot_path"]
                        run.rollback_snapshot_path = snapshot_path
                        run.working_copy_path = snapshot_result["working_copy_path"]
                    if plan.kind in {ProcessingStepKind.PREFLIGHT, ProcessingStepKind.VALIDATE}:
                        checked = result[BlenderOperation.CHECK_GEOMETRY.value]
                        metrics = checked.get("metrics", {})
                        run.quality_gates = merge_gates(
                            run.quality_gates, quality_gates(checked)
                        )
                        blockers = gate_blockers(request, run.quality_gates)
                        if plan.kind == ProcessingStepKind.VALIDATE:
                            blockers.extend(
                                asset_requirement_blockers(request, metrics)
                            )
                        if blockers:
                            raise PipelineExecutionError(
                                "QUALITY_GATE_FAILED",
                                "; ".join(blockers),
                                PipelineState.FAILED,
                            )
                    if plan.kind == ProcessingStepKind.EXPORT:
                        export_data = result[BlenderOperation.EXPORT_ASSET.value]
                emit_event(on_event, run, "asset.pipeline.progressed", step, self._clock())
        except (PipelineExecutionError, BlenderAdapterError, PublicationBlockedError, ValueError) as error:
            execution_error = map_error(error)
            mark_unrun(run, execution_error.code)
            if snapshot_path:
                rolled_back = attempt_rollback(
                    request, adapter, snapshot_path, run, self._clock
                )
                run.state = PipelineState.ROLLED_BACK if rolled_back else execution_error.state
            else:
                run.state = execution_error.state
            run.error_code = execution_error.code
            run.error_message = str(execution_error)
            run.finished_at = self._clock()
            emit_event(on_event, run, "asset.pipeline.failed", None, self._clock())
            return self._remember(request, run)

        run.state = PipelineState.SUCCEEDED
        run.finished_at = self._clock()
        emit_event(on_event, run, "asset.pipeline.completed", None, self._clock())
        return self._remember(request, run)

    def cancel(self, pipeline_run_id: str) -> None:
        try:
            self._ledger.cancel(pipeline_run_id)
        except KeyError as error:
            raise PipelineNotFoundError(pipeline_run_id) from error

    def retry(
        self,
        previous_run_id: str,
        request: PipelineRequest,
        adapter: BlenderAdapterPort,
        on_event: EventSink = lambda _event: None,
    ) -> PipelineRun:
        previous = self.get_run(previous_run_id)
        allowed = {
            PipelineState.FAILED,
            PipelineState.CANCELLED,
            PipelineState.TIMED_OUT,
            PipelineState.ROLLED_BACK,
            PipelineState.BLOCKED,
        }
        if previous.state not in allowed:
            raise PipelineConflictError("only failed, cancelled, timed-out, rolled-back, or blocked runs retry")
        if request.retry_of_run_id != previous_run_id or request.pipeline_run_id == previous_run_id:
            raise PipelineConflictError("retry requires a new run ID and matching retry_of_run_id")
        if not retry_matches_run(previous, request):
            raise PipelineConflictError("retry must preserve project, asset, version, and ChangeSet")
        return self.run(request, adapter, on_event)

    def rollback(
        self,
        pipeline_run_id: str,
        request: PipelineRequest,
        adapter: BlenderAdapterPort,
    ) -> PipelineRun:
        run = self.get_run(pipeline_run_id)
        if not rollback_matches_run(run, request):
            raise PipelineConflictError("rollback request does not match the target run")
        if run.published_version is not None:
            raise PipelineConflictError("published versions require a new compensating version")
        if not run.rollback_snapshot_path:
            raise PipelineConflictError("run has no rollback snapshot")
        if request.change_set.state != ChangeSetState.APPROVED:
            raise PipelineConflictError("rollback requires the approved ChangeSet")
        approval_errors = self._approval_authority.verify_change_set(
            request.change_set,
            request.spec.asset_id,
            request.asset_version_id,
        )
        if approval_errors:
            raise PipelineConflictError("rollback approval was not verified")
        project_root = self._project_roots.resolve(request.spec.project_id)
        if Path(adapter.project_root).resolve() != project_root:
            raise PipelineConflictError("rollback adapter project root does not match")
        if not attempt_rollback(
            request, adapter, run.rollback_snapshot_path, run, self._clock
        ):
            raise PipelineExecutionError("ROLLBACK_FAILED", "Blender rollback failed", PipelineState.FAILED)
        run.state = PipelineState.ROLLED_BACK
        run.finished_at = self._clock()
        with self._runs_lock:
            self._runs[pipeline_run_id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    def get_run(self, pipeline_run_id: str) -> PipelineRun:
        with self._runs_lock:
            run = self._runs.get(pipeline_run_id)
        if run is None:
            raise PipelineNotFoundError(pipeline_run_id)
        return run.model_copy(deep=True)

    def _preview(
        self,
        request: PipelineRequest,
        run: PipelineRun,
        adapter: BlenderAdapterPort,
        final_state: PipelineState,
    ) -> PipelineRun:
        run.state = PipelineState.PLANNING
        run.execution_mode = ExecutionMode.PLANNED
        try:
            for plan in build_workflow_plan(request, preview=True):
                step = step_for(run, plan.kind)
                if plan.skip_reason:
                    skip_step(step, plan.skip_reason)
                else:
                    previews = [adapter.dry_run(command).model_dump(mode="json") for command in plan.commands]
                    step.state = StepState.PLANNED
                    step.execution_mode = ExecutionMode.PLANNED
                    step.result = {"previews": previews}
                    step.progress = 0
        except (BlenderAdapterError, ValueError) as error:
            return self._blocked(request, run, getattr(error, "code", "PREVIEW_INVALID"), str(error))
        run.state = final_state
        run.finished_at = self._clock()
        return self._remember(request, run)

    def _run_publication_step(
        self,
        step: ProcessingStep,
        request: PipelineRequest,
        run: PipelineRun,
        export_data: Dict[str, object],
        metrics: Dict[str, object],
        tool_version: str,
        project_root: Path,
    ) -> None:
        step.state = StepState.RUNNING
        step.started_at = self._clock()
        step.attempts = 1
        candidate, published = build_and_publish_version(
            request,
            self._catalog,
            export_data,
            metrics,
            run.quality_gates,
            run.execution_mode,
            tool_version,
            self._clock(),
            project_root,
            self._candidate_store,
        )
        run.candidate_version = candidate
        run.published_version = published
        step.state = StepState.SUCCEEDED
        step.progress = 1
        step.finished_at = self._clock()
        step.result = {"asset_version_id": published.asset_version_id}

    def _blocked(
        self, request: PipelineRequest, run: PipelineRun, code: str, message: str
    ) -> PipelineRun:
        run.state = PipelineState.BLOCKED
        run.execution_mode = ExecutionMode.BLOCKED
        run.error_code = code
        run.error_message = message
        run.finished_at = self._clock()
        mark_unrun(run, code)
        return self._remember(request, run)

    def _remember(self, request: PipelineRequest, run: PipelineRun) -> PipelineRun:
        stored = self._ledger.complete(request, run)
        with self._runs_lock:
            self._runs[run.pipeline_run_id] = stored
        return stored.model_copy(deep=True)
