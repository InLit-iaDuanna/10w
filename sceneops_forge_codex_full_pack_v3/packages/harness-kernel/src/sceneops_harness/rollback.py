"""Explicit compensation, never replaying a forward handler as rollback."""
import os
from time import monotonic

from .contracts import utc_now
from .execution import await_handler
from .registry import HarnessError
from .run_contracts import CapabilityResult, RollbackAttempt
from .validation import validate_step


async def rollback_run(runtime, project_id, run_id, authority):
    def claim(run):
        if run.owner_pid is not None or run.state not in ("completed", "failed", "blocked", "cancelled"):
            raise HarnessError("INVALID_RUN_STATE", "Run must be stopped before rollback")
        if run.definition.rollback_strategy == "none":
            raise HarnessError("ROLLBACK_DISABLED", "Pipeline has disabled rollback")
        candidates = []
        for stage in run.definition.stages:
            for step in stage.steps:
                entry = next(item for item in run.step_runs if item.step_id == step.id)
                cap = runtime.registry.get(step.capability_id or "")
                if cap and (cap.mode in ("mutate", "build") or cap.cross_system) and not step.dry_run and entry.attempts:
                    if entry.state == "rolled_back":
                        continue
                    candidates.append((step, entry))
        if not candidates:
            raise HarnessError("ROLLBACK_UNAVAILABLE", "No executed side effects with rollback results")
        for step, entry in candidates:
            binding = runtime.registry.binding(step.capability_id)
            if len(entry.rollback_attempts) >= run.definition.budget.max_attempts_per_step:
                raise HarnessError("ATTEMPTS_EXHAUSTED", f"{step.id}: compensation attempt budget exhausted")
            if not binding.rollback_handler or not entry.result or not entry.result.rollback_ref:
                raise HarnessError("ROLLBACK_UNAVAILABLE", f"{step.id}: handler/result has no compensation reference")
            if not entry.rollback_approved_by:
                raise HarnessError("APPROVAL_REQUIRED", f"{step.id}: rollback requires separate approval")
            if entry.rollback_state in ("running", "uncertain"):
                raise HarnessError("ROLLBACK_INSPECTION_REQUIRED", f"{step.id}: prior compensation outcome must be inspected")
            if step.change_set and any(item.minimum_decisions > 1 for item in step.change_set.approval_requirements):
                raise HarnessError("MULTI_APPROVER_ROLLBACK_UNSUPPORTED", "Multi-approver ChangeSets cannot use single-approver compensation")
            issues = validate_step(step, run.definition, authority, runtime.registry)
            if issues:
                raise HarnessError("ROLLBACK_DENIED", "; ".join(item.message for item in issues))
        metered = sum(1 for step, _ in candidates if runtime.registry.get(step.capability_id).metered)
        if run.metered_calls_used + metered > run.definition.budget.max_metered_calls:
            raise HarnessError("CALL_BUDGET_EXCEEDED", "Insufficient remaining metered calls for compensation")
        if metered and not run.budget_accounting_complete and run.definition.budget.usage_policy == "require_reported":
            raise HarnessError("USAGE_UNKNOWN", "Prior usage is unknown; cannot reserve metered compensation")
        run.state, run.owner_pid = "recovering", os.getpid()
        run.reason, run.cancel_requested = None, False
    run = runtime.repository.update(project_id, run_id, claim, "harness.rollback.started")
    try:
        # Reverse actual invocation order, which can differ from declaration order in a DAG.
        entries = sorted([entry for entry in run.step_runs if entry.attempts],
                         key=lambda entry: entry.attempts[-1].started_at, reverse=True)
        for entry in entries:
            entry = next(item for item in run.step_runs if item.step_id == entry.step_id)
            binding = runtime.registry.binding(entry.attempts[-1].invocation.capability_id)
            cap = binding.definition
            if entry.state == "rolled_back" or not (cap.mode in ("mutate", "build") or cap.cross_system) or entry.attempts[-1].invocation.dry_run:
                continue
            budget = run.definition.budget
            if run.duration_seconds >= budget.max_duration_seconds:
                raise HarnessError("TIME_BUDGET_EXCEEDED", "Run execution-time budget exhausted before compensation")
            if cap.metered and run.metered_calls_used >= budget.max_metered_calls:
                raise HarnessError("CALL_BUDGET_EXCEEDED", "Metered compensation call budget exhausted")
            if cap.metered and not run.budget_accounting_complete and budget.usage_policy == "require_reported":
                raise HarnessError("USAGE_UNKNOWN", "Previous compensation usage is unknown")
            remaining = run.definition.budget.model_copy(update={
                "max_metered_calls": max(0, run.definition.budget.max_metered_calls - run.metered_calls_used),
                "max_tokens": max(0, run.definition.budget.max_tokens - run.tokens_used),
                "max_cost_usd": max(0, run.definition.budget.max_cost_usd - run.cost_usd),
                "max_duration_seconds": budget.max_duration_seconds - run.duration_seconds,
            })
            invocation = entry.attempts[-1].invocation.model_copy(update={"authority": authority, "budget": remaining})
            token = runtime.executor.token(run)
            entry.rollback_state = "running"
            entry.rollback_attempts.append(RollbackAttempt(approved_by=entry.rollback_approved_by))
            entry.rollback_approved_by = None
            prior_accounting_complete = run.budget_accounting_complete
            if cap.metered:
                run.budget_accounting_complete = False
                run.metered_calls_used += 1
            # Consume approval and record an uncertain-effect boundary BEFORE external work.
            run = runtime.repository.save_owned(run, "harness.step.rollback_started", entry.step_id)
            entry = next(item for item in run.step_runs if item.step_id == entry.step_id)
            started = monotonic()
            try:
                with runtime.repository.resources(invocation, cap.required_integrations):
                    result = await await_handler(binding.rollback_handler(invocation, entry.result, token), token,
                                                 min(cap.timeout_seconds, remaining.max_duration_seconds))
                result = CapabilityResult.model_validate(result)
                entry.rollback_result = result
                entry.rollback_attempts[-1].result = result
                run.cost_usd += result.cost_usd or 0
                run.tokens_used += result.tokens or 0
                run.budget_accounting_complete = prior_accounting_complete and result.cost_usd is not None and result.tokens is not None
                if result.execution_mode != cap.execution_mode or not result.evidence_refs:
                    raise HarnessError("ROLLBACK_EVIDENCE_REQUIRED", "Compensation must report current mode and evidence")
                entry.state, entry.reason, entry.rollback_state = "rolled_back", None, "succeeded"
                entry.rollback_attempts[-1].state = "succeeded"
            except BaseException as exc:
                entry.rollback_state = "uncertain"
                entry.rollback_attempts[-1].state = "uncertain"
                entry.rollback_attempts[-1].reason = str(exc) or type(exc).__name__
                raise
            finally:
                run.duration_seconds += monotonic() - started
                entry.rollback_attempts[-1].ended_at = utc_now()
            run = runtime.repository.save_owned(run, "harness.step.rolled_back", entry.step_id)
        run.state, run.reason, run.ended_at = "rolled_back", None, utc_now()
    except BaseException as exc:
        run.state, run.reason = "blocked", f"Rollback incomplete: {exc or type(exc).__name__}; inspect external effects"
    finally:
        run.owner_pid = None
        run = runtime.repository.save_owned(run, f"harness.run.{run.state}")
    return run
