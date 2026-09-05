"""Maintained tests. Not executed as part of this implementation task."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from sceneops_harness import (
    Authority, CapabilityDefinition, CapabilityRegistry, CapabilityResult,
    ChangeSet, ExecutionMode, HarnessError, HarnessRuntime, PipelineDefinition,
    PipelineStage, PipelineStep, RetryPolicy, StepEvaluation,
)


class InspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class InspectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inspected: str


class HarnessRuntimeTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "workspace.sqlite3"
        self.authority = Authority(project_id="project_fixture", actor_id="user_fixture",
            permissions=["workspace:read", "harness:approve"], allowed_capabilities=["fixture.inspect"])
        self.calls = []

    def definition(self, steps=None):
        fixture = Path(__file__).parents[1] / "fixtures" / "mock-inspection-pipeline.json"
        definition = PipelineDefinition.model_validate(json.loads(fixture.read_text()))
        if steps is not None:
            definition.stages = [PipelineStage(id="stage", title="Test", steps=steps)]
        return definition

    def runtime(self, handler=None, **capability_fields):
        async def inspect(invocation, cancellation):
            cancellation.raise_if_cancelled()
            self.calls.append(invocation)
            return CapabilityResult(execution_mode="mock", outputs={"inspected": invocation.inputs["name"]},
                                    tokens=0, cost_usd=0)
        registry = CapabilityRegistry()
        definition = CapabilityDefinition(id="fixture.inspect", provider_module_id="fixture",
            title="Fixture inspector", execution_mode=ExecutionMode.MOCK,
            required_permissions=["workspace:read"], estimated_cost_usd=0,
            **{"metered": False, **capability_fields})
        registry.register(definition, handler or inspect, input_model=InspectionInput, output_model=InspectionOutput)
        return HarnessRuntime(self.database, registry)

    async def test_fixture_runs_once_and_survives_new_runtime(self):
        runtime = self.runtime()
        definition = self.definition()
        run = runtime.submit(definition, self.authority, "request-success")
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(completed.execution_mode, ExecutionMode.MOCK)
        self.assertIsNotNone(completed.step_runs[0].checkpoint_at)
        duplicate = runtime.submit(definition, self.authority, "request-success")
        self.assertEqual(duplicate.id, completed.id)
        restored = HarnessRuntime(self.database, runtime.registry).get(run.project_id, run.id)
        self.assertEqual(restored.state, "completed")
        self.assertEqual(len(self.calls), 1)
        events = runtime.events(run.project_id, run.id)
        self.assertIn("harness.step.succeeded", [event.event_type for event in events])
        self.assertEqual(runtime.events(run.project_id, run.id, after=events[-1].sequence), [])

    async def test_handler_failure_persists_then_explicit_retry(self):
        async def flaky(invocation, cancellation):
            self.calls.append(invocation)
            if invocation.attempt == 1:
                raise HarnessError("FIXTURE_FAILURE", "A deterministic failure")
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "recovered"}, tokens=0, cost_usd=0)
        runtime = self.runtime(flaky, retry_policy=RetryPolicy(max_attempts=2, retryable_codes=["FIXTURE_FAILURE"]))
        run = runtime.submit(self.definition(), self.authority, "request-retry")
        failed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(failed.state, "failed")
        self.assertEqual(failed.step_runs[0].attempts[0].error_code, "FIXTURE_FAILURE")
        runtime.retry(run.project_id, run.id, self.authority)
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(len(completed.step_runs[0].attempts), 2)

    async def test_project_isolation_and_denied_capability(self):
        runtime = self.runtime()
        denied = self.authority.model_copy(update={"allowed_capabilities": []})
        report = runtime.validate(self.definition(), denied)
        self.assertFalse(report.valid)
        self.assertIn("CAPABILITY_DENIED", [issue.code for issue in report.issues])
        run = runtime.submit(self.definition(), self.authority, "request-project")
        with self.assertRaises(HarnessError):
            runtime.get("different-project", run.id)
        with self.assertRaises(HarnessError):
            runtime.events("different-project", run.id)
        self.assertEqual(runtime.list("different-project"), [])
        self.assertEqual(self.calls, [])

    async def test_approval_is_a_real_pause(self):
        runtime = self.runtime()
        definition = self.definition([
            PipelineStep(id="approval", title="Approve", kind="approval"),
            PipelineStep(id="inspect", title="Inspect", capability_id="fixture.inspect",
                         inputs={"name": "approved"}, depends_on=["approval"]),
        ])
        run = runtime.submit(definition, self.authority, "request-approval")
        waiting = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(waiting.state, "awaiting_approval")
        self.assertEqual(self.calls, [])
        runtime.approve(run.project_id, run.id, "approval", self.authority)
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(len(self.calls), 1)

    async def test_only_approval_does_not_claim_production_complete(self):
        runtime = self.runtime()
        run = runtime.submit(self.definition([PipelineStep(id="approval", title="Approve", kind="approval")]),
                             self.authority, "request-only-approval")
        await runtime.start(run.project_id, run.id, self.authority)
        runtime.approve(run.project_id, run.id, "approval", self.authority)
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "blocked")
        self.assertEqual(self.calls, [])

    async def test_cancel_cleans_handler_and_preserves_cancelled_attempt(self):
        entered, cleaned = asyncio.Event(), asyncio.Event()
        async def cancellable(invocation, cancellation):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        runtime = self.runtime(cancellable, metered=True)
        run = runtime.submit(self.definition(), self.authority, "request-cancel")
        task = asyncio.create_task(runtime.start(run.project_id, run.id, self.authority))
        await asyncio.wait_for(entered.wait(), timeout=2)
        runtime.cancel(run.project_id, run.id, self.authority)
        cancelled = await asyncio.wait_for(task, timeout=2)
        self.assertTrue(cleaned.is_set())
        self.assertEqual(cancelled.state, "cancelled")
        self.assertEqual(cancelled.step_runs[0].attempts[0].state, "cancelled")
        self.assertFalse(cancelled.budget_accounting_complete)

    async def test_unknown_metrics_remain_unknown(self):
        async def unmetered(invocation, cancellation):
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "unknown usage"})
        runtime = self.runtime(unmetered)
        run = runtime.submit(self.definition(), self.authority, "request-usage")
        completed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(completed.state, "completed")
        self.assertFalse(completed.budget_accounting_complete)
        self.assertIsNone(completed.step_runs[0].result.tokens)
        self.assertIsNone(completed.step_runs[0].result.cost_usd)

    async def test_unavailable_and_unsupported_do_not_execute(self):
        runtime = self.runtime()
        runtime.registry.register(CapabilityDefinition(id="blender.planned", provider_module_id="blender",
                                                       title="Planned Blender", availability_reason="Not connected"))
        definition = self.definition([PipelineStep(id="future", title="Future", kind="fan_out",
                                                   capability_id="blender.planned")])
        report = runtime.validate(definition, self.authority)
        codes = {issue.code for issue in report.issues}
        self.assertIn("UNSUPPORTED_STEP_KIND", codes)
        self.assertIn("CAPABILITY_UNAVAILABLE", codes)
        run = runtime.submit(definition, self.authority, "request-planned")
        self.assertEqual(run.state, "blocked")
        with self.assertRaises(HarnessError):
            await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(self.calls, [])

    async def test_cycle_and_request_id_conflict(self):
        runtime = self.runtime()
        definition = self.definition()
        definition.stages[0].steps[0].depends_on = ["inspect_source"]
        self.assertIn("DEPENDENCY_CYCLE", [issue.code for issue in runtime.validate(definition, self.authority).issues])
        runtime.submit(self.definition(), self.authority, "request-conflict")
        with self.assertRaises(HarnessError):
            runtime.submit(definition, self.authority, "request-conflict")

    async def test_dead_worker_is_blocked_without_replay(self):
        runtime = self.runtime()
        run = runtime.submit(self.definition(), self.authority, "request-interrupted")
        def crashed(current):
            current.owner_pid = 12345
            current.state = "running"
            current.step_runs[0].state = "running"
        runtime.repository.update(run.project_id, run.id, crashed, "fixture.worker_crashed")
        with patch("sceneops_harness.repository.os.kill", side_effect=ProcessLookupError):
            recovered = runtime.recover_interrupted(run.project_id)
        self.assertEqual(recovered, [run.id])
        restored = runtime.get(run.project_id, run.id)
        self.assertEqual(restored.state, "blocked")
        self.assertEqual(restored.step_runs[0].state, "blocked")
        self.assertIsNone(restored.owner_pid)
        self.assertEqual(self.calls, [])

    async def test_explicit_compensation_handler_and_approval(self):
        effects = []
        async def forward(invocation, cancellation):
            effects.append("fixture remote reservation")
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "reservation"},
                                    rollback_ref="fixture-reservation", tokens=0, cost_usd=0)
        async def compensate(invocation, result, cancellation):
            self.assertEqual(result.rollback_ref, "fixture-reservation")
            effects.remove("fixture remote reservation")
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "released"},
                                    evidence_refs=["fixture-compensation-record"], tokens=0, cost_usd=0)
        registry = CapabilityRegistry()
        registry.register(CapabilityDefinition(id="fixture.inspect", provider_module_id="fixture",
            title="Mock reservation", cross_system=True, supports_rollback=True, execution_mode="mock"),
            forward, input_model=InspectionInput, output_model=InspectionOutput, rollback_handler=compensate)
        runtime = HarnessRuntime(self.database, registry)
        run = runtime.submit(self.definition(), self.authority, "request-compensation")
        await runtime.start(run.project_id, run.id, self.authority)
        runtime.approve(run.project_id, run.id, "inspect_source", self.authority)
        await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(len(effects), 1)
        with self.assertRaises(HarnessError):
            await runtime.rollback(run.project_id, run.id, self.authority)
        runtime.approve(run.project_id, run.id, "inspect_source", self.authority, action="rollback")
        rolled_back = await runtime.rollback(run.project_id, run.id, self.authority)
        self.assertEqual(rolled_back.state, "rolled_back")
        self.assertEqual(effects, [])
        self.assertIsNotNone(rolled_back.step_runs[0].rollback_result)

    async def test_result_mode_cannot_be_upgraded_from_mock_to_live(self):
        async def mislabelled(invocation, cancellation):
            return CapabilityResult(execution_mode="live", outputs={"inspected": "fixture"}, tokens=0, cost_usd=0)
        runtime = self.runtime(mislabelled)
        run = runtime.submit(self.definition(), self.authority, "request-mode")
        failed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(failed.state, "failed")
        self.assertEqual(failed.step_runs[0].attempts[0].error_code, "RESULT_MODE_MISMATCH")
        self.assertEqual(failed.execution_mode, ExecutionMode.MOCK)

    async def test_observer_abort_without_acceptance_criteria_stops_run(self):
        async def observed(invocation, cancellation):
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "fixture"}, tokens=0, cost_usd=0,
                evaluation=StepEvaluation(step_run_id=invocation.step_run_id, next_disposition="abort"))
        runtime = self.runtime(observed)
        run = runtime.submit(self.definition(), self.authority, "request-observer")
        stopped = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(stopped.state, "failed")
        self.assertEqual(stopped.step_runs[0].attempts[0].error_code, "EVALUATION_INTERRUPTED")

    async def test_approval_cannot_silently_discard_output_requirements(self):
        runtime = self.runtime()
        definition = self.definition([PipelineStep(id="approve", title="Approve", kind="approval",
            output_schema={"type": "object"}, evidence_requirements=["external-proof"])])
        self.assertIn("INVALID_APPROVAL_STEP", [issue.code for issue in runtime.validate(definition, self.authority).issues])

    async def test_metered_failure_does_not_allow_a_second_paid_call(self):
        async def paid_failure(invocation, cancellation):
            self.calls.append(invocation)
            self.assertFalse(runtime.get(invocation.project_id, invocation.run_id).budget_accounting_complete)
            raise HarnessError("PROVIDER_FAILED", "Provider failed after accepting request")
        runtime = self.runtime(paid_failure, metered=True, retry_policy=RetryPolicy(max_attempts=2))
        run = runtime.submit(self.definition(), self.authority, "request-paid-failure")
        failed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertFalse(failed.budget_accounting_complete)
        runtime.retry(run.project_id, run.id, self.authority)
        blocked = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(blocked.state, "blocked")
        self.assertIn("USAGE_UNKNOWN", blocked.reason)
        self.assertEqual(len(self.calls), 1)

    async def test_compensation_consumes_approval_before_effect_and_blocks_replay(self):
        async def forward(invocation, cancellation):
            return CapabilityResult(execution_mode="mock", outputs={"inspected": "reservation"},
                                    rollback_ref="fixture-reservation", tokens=0, cost_usd=0)
        async def uncertain(invocation, result, cancellation):
            persisted = runtime.get(invocation.project_id, invocation.run_id).step_runs[0]
            self.assertEqual(persisted.rollback_state, "running")
            self.assertIsNone(persisted.rollback_approved_by)
            self.assertEqual(persisted.rollback_attempts[-1].state, "running")
            raise HarnessError("LOST_RECEIPT", "Compensation may have finished; receipt unavailable")
        registry = CapabilityRegistry()
        registry.register(CapabilityDefinition(id="fixture.inspect", provider_module_id="fixture", title="Mock reservation",
            cross_system=True, supports_rollback=True, execution_mode="mock", metered=False), forward,
            input_model=InspectionInput, output_model=InspectionOutput, rollback_handler=uncertain)
        runtime = HarnessRuntime(self.database, registry)
        run = runtime.submit(self.definition(), self.authority, "request-uncertain-compensation")
        await runtime.start(run.project_id, run.id, self.authority)
        runtime.approve(run.project_id, run.id, "inspect_source", self.authority)
        await runtime.start(run.project_id, run.id, self.authority)
        runtime.approve(run.project_id, run.id, "inspect_source", self.authority, action="rollback")
        blocked = await runtime.rollback(run.project_id, run.id, self.authority)
        self.assertEqual(blocked.state, "blocked")
        self.assertEqual(blocked.step_runs[0].rollback_state, "uncertain")
        self.assertIsNone(blocked.step_runs[0].rollback_approved_by)
        with self.assertRaises(HarnessError):
            await runtime.rollback(run.project_id, run.id, self.authority)
        with self.assertRaises(HarnessError) as error:
            runtime.approve(run.project_id, run.id, "inspect_source", self.authority, action="rollback")
        self.assertEqual(error.exception.code, "ROLLBACK_INSPECTION_REQUIRED")
        approved = runtime.approve(run.project_id, run.id, "inspect_source", self.authority,
                                   action="rollback", inspection_confirmed=True)
        self.assertEqual(approved.step_runs[0].rollback_state, "not_started")

    async def test_multi_approver_changeset_cannot_use_single_rollback_approval(self):
        runtime = self.runtime(cross_system=True)
        fixture = Path(__file__).parents[2] / "core-contracts" / "fixtures" / "valid-changeset.json"
        values = json.loads(fixture.read_text())
        values["approval_requirements"][0]["minimum_decisions"] = 2
        definition = self.definition()
        definition.stages[0].steps[0].change_set = ChangeSet.model_validate(values)
        authority = self.authority.model_copy(update={"permissions": self.authority.permissions + ["scene:approve"]})
        run = runtime.submit(definition, authority, "request-multiple-approvers")
        await runtime.start(run.project_id, run.id, authority)
        runtime.approve(run.project_id, run.id, "inspect_source", authority)
        runtime.approve(run.project_id, run.id, "inspect_source", authority.model_copy(update={"actor_id": "second-user"}))
        await runtime.start(run.project_id, run.id, authority)
        with self.assertRaises(HarnessError) as error:
            runtime.approve(run.project_id, run.id, "inspect_source", authority, action="rollback")
        self.assertEqual(error.exception.code, "MULTI_APPROVER_ROLLBACK_UNSUPPORTED")

    async def test_metered_timeout_and_restart_preserve_unknown_usage(self):
        async def timeout(invocation, cancellation):
            await asyncio.Event().wait()
        runtime = self.runtime(timeout, metered=True, timeout_seconds=0.01)
        run = runtime.submit(self.definition(), self.authority, "request-paid-timeout")
        failed = await runtime.start(run.project_id, run.id, self.authority)
        self.assertEqual(failed.step_runs[0].attempts[0].error_code, "TIMEOUT")
        self.assertFalse(failed.budget_accounting_complete)
        def interrupted(current):
            current.state, current.owner_pid = "running", 12345
            current.budget_accounting_complete = True
            current.step_runs[0].state = "running"
            current.step_runs[0].attempts[-1].state = "running"
        runtime.repository.update(run.project_id, run.id, interrupted, "fixture.worker_crashed")
        with patch("sceneops_harness.repository.os.kill", side_effect=ProcessLookupError):
            runtime.recover_interrupted(run.project_id)
        recovered = runtime.get(run.project_id, run.id)
        self.assertEqual(recovered.state, "blocked")
        self.assertFalse(recovered.budget_accounting_complete)
