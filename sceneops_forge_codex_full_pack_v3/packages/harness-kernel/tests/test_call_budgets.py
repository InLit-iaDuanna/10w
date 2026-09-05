"""Explicit bounded-call policy cases; maintained but not executed in this task."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from pydantic import BaseModel
from sceneops_harness import (
    Authority, CapabilityDefinition, CapabilityRegistry, CapabilityResult, HarnessError,
    HarnessRuntime, PipelineDefinition, PipelineStage, PipelineStep, RetryPolicy, RuntimeBudget,
)


class EmptyPayload(BaseModel):
    pass


class CallBudgetTests(IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.authority = Authority(project_id="budget-project", actor_id="budget-user",
                                   allowed_capabilities=["fixture.provider"])
        self.calls = []

    def runtime(self, fail=False):
        async def invoke(call, cancellation):
            self.calls.append(call)
            current = runtime.get(call.project_id, call.run_id)
            self.assertEqual(current.metered_calls_used, len(self.calls))
            if fail:
                raise HarnessError("LOST_RECEIPT", "Provider accepted request but did not return usage")
            return CapabilityResult(execution_mode="mock")
        registry = CapabilityRegistry()
        registry.register(CapabilityDefinition(id="fixture.provider", provider_module_id="fixture",
            title="Mock metered provider", metered=True, execution_mode="mock",
            retry_policy=RetryPolicy(max_attempts=3)), invoke,
            input_model=EmptyPayload, output_model=EmptyPayload)
        runtime = HarnessRuntime(self.directory / "workspace.sqlite3", registry)
        return runtime

    def definition(self, budget, count=2):
        return PipelineDefinition(project_id=self.authority.project_id, intent_id="budget-intent",
            execution_mode="mock", budget=budget, stages=[PipelineStage(id="agents", title="Agents",
                steps=[PipelineStep(id=f"agent-{index}", title="Mock provider", capability_id="fixture.provider",
                                    depends_on=[f"agent-{index-1}"] if index else []) for index in range(count)])])

    async def test_default_unknown_usage_stops_second_call(self):
        runtime = self.runtime()
        run = runtime.submit(self.definition(RuntimeBudget()), self.authority, "strict")
        stopped = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(stopped.state, "blocked")
        self.assertEqual(stopped.metered_calls_used, 1)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(stopped.budget_accounting_complete)

    async def test_explicit_bounded_calls_continues_without_claiming_known_cost(self):
        runtime = self.runtime()
        budget = RuntimeBudget(usage_policy="bounded_calls", max_metered_calls=2)
        run = runtime.submit(self.definition(budget), self.authority, "bounded")
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(completed.metered_calls_used, 2)
        self.assertEqual([call.budget.max_metered_calls for call in self.calls], [2, 1])
        self.assertFalse(completed.budget_accounting_complete)
        self.assertTrue(all(step.result.cost_usd is None for step in completed.step_runs))

    async def test_failed_attempts_consume_call_budget(self):
        runtime = self.runtime(fail=True)
        budget = RuntimeBudget(usage_policy="bounded_calls", max_metered_calls=1, max_attempts_per_step=3)
        run = runtime.submit(self.definition(budget, count=1), self.authority, "failed")
        failed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(failed.metered_calls_used, 1)
        runtime.retry(run.project_id, run.id, self.authority)
        blocked = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(blocked.state, "blocked")
        self.assertIn("CALL_BUDGET_EXCEEDED", blocked.reason)
        self.assertEqual(len(self.calls), 1)

    async def test_zero_calls_disables_metered_execution(self):
        runtime = self.runtime()
        report = runtime.validate(self.definition(RuntimeBudget(max_metered_calls=0), count=1), self.authority)
        self.assertFalse(report.valid)
        self.assertIn("CALL_BUDGET_EXCEEDED", [issue.code for issue in report.issues])
        self.assertEqual(self.calls, [])
