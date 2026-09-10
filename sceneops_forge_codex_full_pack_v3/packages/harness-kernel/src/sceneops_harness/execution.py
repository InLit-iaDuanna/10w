"""One bounded invocation at a time, checkpointed before and after external work."""
import asyncio
from time import monotonic

from sceneops_core_contracts import ExecutionMode

from .contracts import Authority, PipelineStep, utc_now
from .registry import CancellationToken, CapabilityBinding, CapabilityRegistry, HarnessError
from .repository import RunRepository
from .run_contracts import AttemptRecord, CapabilityInvocation, CapabilityResult, PipelineRun, StepRun
from .validation import condition_matches


def duration_exhausted(limit: float | None, elapsed: float) -> bool:
    return limit is not None and elapsed >= limit


def remaining_duration(limit: float | None, elapsed: float) -> float | None:
    return None if limit is None else max(0, limit - elapsed)


def shortest_duration(*limits: float | None) -> float | None:
    bounded = [limit for limit in limits if limit is not None]
    return min(bounded) if bounded else None


async def await_handler(awaitable, cancellation: CancellationToken, timeout: float | None):
    task = asyncio.create_task(awaitable)
    started = monotonic()
    try:
        while not task.done():
            cancellation.raise_if_cancelled()
            if duration_exhausted(timeout, monotonic() - started):
                raise TimeoutError("Capability deadline exceeded")
            await asyncio.wait({task}, timeout=0.1 if timeout is None else min(0.1, timeout))
        return await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def validate_result(result: CapabilityResult, binding: CapabilityBinding, step: PipelineStep,
                    step_run: StepRun) -> None:
    if result.execution_mode != binding.definition.execution_mode:
        raise HarnessError("RESULT_MODE_MISMATCH", "Handler result differs from registered execution mode")
    binding.output_model.model_validate(result.outputs)
    required = set(step.evidence_requirements) | set(binding.definition.evidence_produced)
    if not required.issubset(result.evidence_types) or (required and not result.evidence_refs):
        raise HarnessError("MISSING_EVIDENCE", "Handler did not return required evidence types and references")
    for condition in binding.definition.postconditions:
        if not condition_matches(condition, step.inputs, result.outputs):
            raise HarnessError("POSTCONDITION_FAILED", f"Condition failed: {condition.field}")
    if result.evaluation is not None:
        if result.evaluation.step_run_id != step_run.id:
            raise HarnessError("EVALUATION_MISMATCH", "Evaluation belongs to a different step run")
        if result.evaluation.next_disposition != "continue":
            raise HarnessError("EVALUATION_INTERRUPTED", result.evaluation.next_disposition)
    if step.acceptance_criteria:
        evaluation = result.evaluation
        if evaluation is None or evaluation.step_run_id != step_run.id:
            raise HarnessError("EVALUATION_REQUIRED", "Acceptance criteria require an evaluation for this step run")
        results = {entry.criterion_id: entry for entry in evaluation.acceptance_results}
        if any(criterion.id not in results or not results[criterion.id].passed for criterion in step.acceptance_criteria):
            raise HarnessError("ACCEPTANCE_FAILED", "Not all acceptance criteria passed")
    if step.kind == "agent":
        agent = result.agent_result
        if agent is None or agent.task_id != step.agent_task.id or agent.agent_role != step.agent_task.agent_role:
            raise HarnessError("AGENT_RESULT_MISMATCH", "Agent result must match its assigned task and role")
        if agent.routing_decision != step.model_routing or agent.execution_mode != result.execution_mode:
            raise HarnessError("AGENT_ROUTING_MISMATCH", "Agent must report the selected routing and execution mode")
        if not set(agent.proposed_capabilities).issubset(step.agent_task.allowed_capabilities):
            raise HarnessError("AGENT_CAPABILITY_DENIED", "Agent proposed a capability outside its allowlist")


class ExecutionEngine:
    def __init__(self, repository: RunRepository, registry: CapabilityRegistry):
        self.repository, self.registry = repository, registry

    def token(self, run: PipelineRun) -> CancellationToken:
        return CancellationToken(lambda: self.repository.get(run.project_id, run.id).cancel_requested)

    async def execute(self, run: PipelineRun, step: PipelineStep, authority: Authority) -> PipelineRun:
        entry = next(item for item in run.step_runs if item.step_id == step.id)
        binding = self.registry.binding(step.capability_id)
        budget = run.definition.budget
        if len(entry.attempts) >= min(budget.max_attempts_per_step, binding.definition.retry_policy.max_attempts):
            raise HarnessError("ATTEMPTS_EXHAUSTED", "Explicit retry budget exhausted; human review required")
        if duration_exhausted(budget.max_duration_seconds, run.duration_seconds):
            raise HarnessError("TIME_BUDGET_EXCEEDED", "Run execution-time budget exhausted")
        estimated_cost = binding.definition.estimated_cost_usd
        if not run.budget_accounting_complete and binding.definition.metered and budget.usage_policy == "require_reported":
            raise HarnessError("USAGE_UNKNOWN", "Prior usage is unknown; cannot reserve another metered call")
        if binding.definition.metered and run.metered_calls_used >= budget.max_metered_calls:
            raise HarnessError("CALL_BUDGET_EXCEEDED", "Metered call budget exhausted")
        if run.cost_usd + (estimated_cost or 0) > budget.max_cost_usd or run.tokens_used + binding.definition.estimated_tokens > budget.max_tokens:
            raise HarnessError("BUDGET_EXCEEDED", "Remaining budget cannot cover the declared estimate")
        inputs = binding.input_model.model_validate(step.inputs).model_dump(mode="json")
        step_budget = step.agent_task.budget if step.agent_task else budget
        step_calls_used = sum(1 for attempt in entry.attempts if attempt.invocation.metered)
        if binding.definition.metered and step_calls_used >= step_budget.max_metered_calls:
            raise HarnessError("CALL_BUDGET_EXCEEDED", "Agent task metered call budget exhausted")
        invocation = CapabilityInvocation(project_id=run.project_id, run_id=run.id, step_id=step.id,
            step_run_id=entry.id, attempt=len(entry.attempts) + 1, capability_id=step.capability_id, inputs=inputs,
            execution_mode=binding.definition.execution_mode, metered=binding.definition.metered, dry_run=step.dry_run,
            change_set_id=step.change_set.change_set_id if step.change_set else None,
            change_set=step.change_set,
            snapshot_ref=step.snapshot_ref, agent_task=step.agent_task, model_routing=step.model_routing,
            authority=authority, budget=budget.model_copy(update={
                "max_tokens": min(step_budget.max_tokens, max(0, budget.max_tokens - run.tokens_used)),
                "max_cost_usd": min(step_budget.max_cost_usd, max(0, budget.max_cost_usd - run.cost_usd)),
                "max_duration_seconds": shortest_duration(
                    step_budget.max_duration_seconds,
                    remaining_duration(budget.max_duration_seconds, run.duration_seconds),
                ),
                "max_metered_calls": max(0, min(step_budget.max_metered_calls - step_calls_used,
                                               budget.max_metered_calls - run.metered_calls_used)),
            }), dependency_outputs={item.step_id: item.result.outputs for item in run.step_runs
                                    if item.step_id in step.depends_on and item.result is not None})
        entry.state, entry.reason = "running", None
        entry.execution_mode = invocation.execution_mode
        run.execution_mode = (ExecutionMode.MOCK if invocation.execution_mode == ExecutionMode.MOCK
                              or run.execution_mode == ExecutionMode.MOCK else ExecutionMode.LIVE)
        entry.attempts.append(AttemptRecord(invocation=invocation, started_at=utc_now()))
        prior_accounting_complete = run.budget_accounting_complete
        if binding.definition.metered:
            # An in-flight provider call can incur charges even without returning usage.
            run.budget_accounting_complete = False
            run.metered_calls_used += 1
        run = self.repository.save_owned(run, "harness.step.started", step.id)
        entry = next(item for item in run.step_runs if item.step_id == step.id)
        started = monotonic()
        try:
            with self.repository.resources(invocation, binding.definition.required_integrations):
                result = await await_handler(binding.handler(invocation, self.token(run)), self.token(run),
                    shortest_duration(binding.definition.timeout_seconds, invocation.budget.max_duration_seconds))
            result = CapabilityResult.model_validate(result)
            # Preserve real outputs even when a later schema/evidence/acceptance check fails.
            entry.result = result
            entry.attempts[-1].result = result
            run.tokens_used += result.tokens or 0
            run.cost_usd += result.cost_usd or 0
            run.budget_accounting_complete = prior_accounting_complete and result.tokens is not None and result.cost_usd is not None
            validate_result(result, binding, step, entry)
            if run.tokens_used > budget.max_tokens or run.cost_usd > budget.max_cost_usd or (result.tokens or 0) > invocation.budget.max_tokens or (result.cost_usd or 0) > invocation.budget.max_cost_usd:
                raise HarnessError("BUDGET_OVERRUN", "Reported usage exceeds budget; no further work will execute")
            entry.state = "succeeded"
            entry.checkpoint_at = utc_now() if step.checkpoint else None
        except asyncio.CancelledError:
            entry.state, entry.reason = "cancelled", "Cancellation requested; inspect any completed external effects"
            entry.attempts[-1].error_code = "CANCELLED"
            run.cancel_requested = True
        except Exception as exc:
            entry.state, entry.reason = "failed", str(exc)
            entry.attempts[-1].error_code = getattr(exc, "code", "TIMEOUT" if isinstance(exc, TimeoutError) else "CAPABILITY_FAILED")
        finally:
            run.duration_seconds += monotonic() - started
            entry.attempts[-1].state = entry.state
            entry.attempts[-1].error = entry.reason
            entry.attempts[-1].ended_at = utc_now()
        return self.repository.save_owned(run, f"harness.step.{entry.state}", step.id)
