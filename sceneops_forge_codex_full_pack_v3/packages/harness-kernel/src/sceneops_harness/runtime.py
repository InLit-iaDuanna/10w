"""Public durable runtime. Scheduling requires fresh authority supplied by the caller."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sceneops_core_contracts import ExecutionMode

from .contracts import Authority, PipelineDefinition, utc_now
from .execution import ExecutionEngine
from .registry import CapabilityRegistry, HarnessError
from .repository import RunRepository
from .run_contracts import PipelineRun, StepRun
from .validation import requires_approval, validate_pipeline, validate_step


class HarnessRuntime:
    def __init__(self, database_path: str | Path, registry: CapabilityRegistry):
        self.registry = registry
        self.repository = RunRepository(database_path)
        self.executor = ExecutionEngine(self.repository, registry)

    def validate(self, definition: PipelineDefinition, authority: Authority):
        return validate_pipeline(definition, authority, self.registry)

    def submit(self, definition: PipelineDefinition, authority: Authority, request_id: str) -> PipelineRun:
        self._authorize(definition.project_id, authority)
        if not request_id.strip():
            raise HarnessError("REQUEST_ID_REQUIRED", "Submission requires a stable request ID")
        report = self.validate(definition, authority)
        run = PipelineRun(project_id=definition.project_id, request_id=request_id, definition=definition,
            submitted_by=authority.actor_id, state="queued" if report.valid else "blocked",
            reason=None if report.valid else "; ".join(f"{item.code}: {item.message}" for item in report.issues),
            step_runs=[StepRun(step_id=step.id, stage_id=stage.id) for stage in definition.stages for step in stage.steps])
        return self.repository.create(run)

    def get(self, project_id: str, run_id: str) -> PipelineRun:
        return self.repository.get(project_id, run_id)

    def list(self, project_id: str, limit: int = 50) -> list[PipelineRun]:
        return self.repository.list(project_id, limit)

    def events(self, project_id: str, run_id: str, after: int = 0, limit: int = 200):
        return self.repository.events(project_id, run_id, after, limit)

    def recover_interrupted(self, project_id: str) -> list[str]:
        return self.repository.recover_interrupted(project_id)

    @staticmethod
    def _authorize(project_id: str, authority: Authority):
        if authority.project_id != project_id or not authority.actor_id.strip():
            raise HarnessError("PROJECT_DENIED", "Current authority does not match this project")

    async def start(self, project_id: str, run_id: str, authority: Authority) -> PipelineRun:
        self._authorize(project_id, authority)
        def claim(run: PipelineRun):
            if run.owner_pid is not None or run.state not in ("queued", "awaiting_approval"):
                raise HarnessError("INVALID_RUN_STATE", f"Cannot start run in {run.state}; explicitly retry blocked/failed work")
            run.state, run.owner_pid = "running", os.getpid()
            run.started_at = run.started_at or utc_now()
            run.reason, run.ended_at = None, None
        run = self.repository.update(project_id, run_id, claim, "harness.run.started")
        try:
            report = self.validate(run.definition, authority)
            if not report.valid:
                run.state = "blocked"
                run.reason = "; ".join(f"{item.code}: {item.message}" for item in report.issues)
            else:
                run = await self._schedule(run, authority, report.execution_order)
        except asyncio.CancelledError:
            run = self.get(project_id, run_id)
            run = self._cancel_remaining(run)
        except Exception as exc:
            run = self.get(project_id, run_id)
            run.state, run.reason = "blocked", f"{getattr(exc, 'code', 'RUNTIME_FAILED')}: {exc}"
        finally:
            # The owner publishes final state and releases its claim atomically.
            run.owner_pid = None
            if run.state in ("completed", "cancelled", "failed", "rolled_back"):
                run.ended_at = utc_now()
            run = self.repository.save_owned(run, f"harness.run.{run.state}")
        return run

    async def _schedule(self, run: PipelineRun, authority: Authority, order: list[str]) -> PipelineRun:
        steps = {step.id: step for stage in run.definition.stages for step in stage.steps}
        for step_id in order:
            if self.get(run.project_id, run.id).cancel_requested:
                return self._cancel_remaining(run)
            entry = next(item for item in run.step_runs if item.step_id == step_id)
            if entry.state == "succeeded":
                continue
            step = steps[step_id]
            issues = validate_step(step, run.definition, authority, self.registry)
            if issues:
                entry.state, entry.reason = "blocked", "; ".join(item.message for item in issues)
                run.state, run.reason = "blocked", entry.reason
                return run
            if requires_approval(step, self.registry) and not self._approved(step, entry):
                entry.state, entry.reason = "waiting_approval", "Awaiting explicit human approval"
                run.state, run.reason = "awaiting_approval", entry.reason
                return run
            if step.kind == "approval":
                entry.state, entry.reason = "succeeded", "Explicit human approval recorded"
                run = self.repository.save_owned(run, "harness.step.approved", step_id)
                continue
            run = await self.executor.execute(run, step, authority)
            entry = next(item for item in run.step_runs if item.step_id == step_id)
            if entry.state != "succeeded":
                run.state = "cancelled" if run.cancel_requested else ("blocked" if step.failure_strategy == "ask_human" else "failed")
                run.reason = entry.reason
                return self._cancel_remaining(run) if run.cancel_requested else run
        if self.get(run.project_id, run.id).cancel_requested:
            return self._cancel_remaining(run)
        executed = [item for item in run.step_runs if item.result is not None]
        if not executed:
            run.state, run.reason = "blocked", "No capability work executed; approvals alone do not complete production"
        else:
            run.state, run.reason = "completed", None
            modes = {item.result.execution_mode for item in executed}
            run.execution_mode = ExecutionMode.MOCK if ExecutionMode.MOCK in modes else ExecutionMode.LIVE
        return run

    @staticmethod
    def _cancel_remaining(run):
        run.state, run.cancel_requested = "cancelled", True
        run.reason = "Run cancelled; completed results are preserved"
        for entry in run.step_runs:
            if entry.state in ("pending", "ready", "waiting_approval"):
                entry.state, entry.reason = "cancelled", "Cancelled before execution"
        return run

    @staticmethod
    def _approved(step, entry) -> bool:
        minimum = max((item.minimum_decisions for item in step.change_set.approval_requirements), default=1) if step.change_set else 1
        return len(set(entry.approved_by)) >= minimum

    def approve(self, project_id: str, run_id: str, step_id: str, authority: Authority,
                *, decision: str = "approved", action: str = "execute", inspection_confirmed: bool = False) -> PipelineRun:
        self._authorize(project_id, authority)
        if authority.actor_type != "user" or "harness:approve" not in authority.permissions:
            raise HarnessError("APPROVAL_DENIED", "Approval requires an authorized human actor")
        if decision not in ("approved", "rejected") or action not in ("execute", "rollback"):
            raise HarnessError("INVALID_APPROVAL", "Unsupported approval decision or action")
        def apply(run):
            if run.owner_pid is not None:
                raise HarnessError("RUN_BUSY", "Cannot change approvals while a worker owns the run")
            step = next((item for stage in run.definition.stages for item in stage.steps if item.id == step_id), None)
            entry = next((item for item in run.step_runs if item.step_id == step_id), None)
            if step is None or entry is None:
                raise HarnessError("STEP_NOT_FOUND", step_id)
            if action == "execute" and entry.state != "waiting_approval":
                raise HarnessError("INVALID_STEP_STATE", "Only waiting approval steps can be approved")
            if action == "rollback" and entry.result is None:
                raise HarnessError("ROLLBACK_UNAVAILABLE", "No executed result to compensate")
            if action == "rollback" and step.change_set and any(item.minimum_decisions > 1 for item in step.change_set.approval_requirements):
                raise HarnessError("MULTI_APPROVER_ROLLBACK_UNSUPPORTED", "This ChangeSet requires multiple rollback approvers; current compensation flow cannot satisfy it")
            if action == "rollback" and decision == "approved" and entry.rollback_state in ("running", "uncertain") and not inspection_confirmed:
                raise HarnessError("ROLLBACK_INSPECTION_REQUIRED", "Inspect actual external compensation effects before approving another attempt")
            if step.change_set:
                for requirement in step.change_set.approval_requirements:
                    if requirement.permission not in authority.permissions or "user" not in requirement.allowed_actor_types:
                        raise HarnessError("APPROVAL_DENIED", "ChangeSet approval requirements are not met")
            if decision == "rejected":
                run.state, run.reason = "blocked", f"{action} rejected by {authority.actor_id}"
                if action == "execute":
                    entry.state, entry.reason, entry.approved_by = "blocked", run.reason, []
                else:
                    entry.rollback_approved_by = None
            elif action == "rollback":
                entry.rollback_approved_by = authority.actor_id
                if inspection_confirmed:
                    entry.rollback_state = "not_started"
            elif authority.actor_id not in entry.approved_by:
                entry.approved_by.append(authority.actor_id)
        return self.repository.update(project_id, run_id, apply, "harness.approval.recorded", step_id,
                                      {"actor_id": authority.actor_id, "decision": decision, "action": action,
                                       "inspection_confirmed": inspection_confirmed})

    def cancel(self, project_id: str, run_id: str, authority: Authority) -> PipelineRun:
        self._authorize(project_id, authority)
        def apply(run):
            if run.state in ("completed", "cancelled", "rolled_back"):
                raise HarnessError("INVALID_RUN_STATE", f"Cannot cancel {run.state} run")
            run.cancel_requested = True
            if run.owner_pid is None:
                self._cancel_remaining(run)
                run.ended_at = utc_now()
        return self.repository.update(project_id, run_id, apply, "harness.run.cancellation_requested")

    def retry(self, project_id: str, run_id: str, authority: Authority) -> PipelineRun:
        self._authorize(project_id, authority)
        def apply(run):
            if run.owner_pid is not None or run.state not in ("failed", "blocked", "cancelled"):
                raise HarnessError("INVALID_RUN_STATE", "Only failed, blocked or cancelled runs can be retried")
            if any(entry.rollback_attempts for entry in run.step_runs):
                raise HarnessError("RECOVERY_REQUIRES_INSPECTION", "A compensated or uncertain run cannot reuse forward checkpoints; inspect and submit a new plan")
            report = self.validate(run.definition, authority)
            if not report.valid:
                raise HarnessError("PIPELINE_INVALID", "; ".join(item.message for item in report.issues))
            for entry in run.step_runs:
                if entry.state == "succeeded":
                    continue
                step = next(step for stage in run.definition.stages for step in stage.steps if step.id == entry.step_id)
                cap = self.registry.get(step.capability_id or "")
                if cap and len(entry.attempts) >= min(cap.retry_policy.max_attempts, run.definition.budget.max_attempts_per_step):
                    raise HarnessError("ATTEMPTS_EXHAUSTED", f"{entry.step_id}: maximum attempts reached; human review required")
                if cap and entry.attempts:
                    policy = cap.retry_policy
                    last = entry.attempts[-1]
                    if policy.retryable_codes and last.error_code not in policy.retryable_codes:
                        raise HarnessError("RETRY_DENIED", f"{entry.step_id}: failure code is outside retry policy")
                    if (cap.mode in ("mutate", "build") or cap.cross_system) and not step.dry_run and not policy.side_effect_retry_safe:
                        raise HarnessError("RETRY_REQUIRES_INSPECTION", f"{entry.step_id}: adapter has not declared side-effect-safe retries")
                entry.state, entry.reason, entry.approved_by = "pending", None, []
            run.state, run.reason, run.cancel_requested, run.ended_at = "queued", None, False, None
        return self.repository.update(project_id, run_id, apply, "harness.run.retry_requested")

    async def rollback(self, project_id: str, run_id: str, authority: Authority) -> PipelineRun:
        from .rollback import rollback_run
        self._authorize(project_id, authority)
        return await rollback_run(self, project_id, run_id, authority)
