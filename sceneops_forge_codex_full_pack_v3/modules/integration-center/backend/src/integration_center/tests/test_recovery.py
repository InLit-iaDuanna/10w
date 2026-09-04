import unittest
from dataclasses import replace
from datetime import datetime, timezone

from observability import CorrelationContext, ExecutionMode

from integration_center import (
    IdempotencyConflict,
    InMemoryRecoveryLedger,
    InMemoryRecoveryRepository,
    InvalidRecoveryState,
    JobNotFound,
    JobState,
    ReconciliationResult,
    ReconciliationState,
    RecoveryCoordinator,
    RecoveryDispatchFailed,
    RecoveryIntentState,
    RecoveryJob,
    RetrySafety,
    SideEffectState,
    UnsafeRecovery,
    EventActor,
    build_recovery_requested_event,
)


RECOVERY_CONTEXT = CorrelationContext(
    project_id="prj_recovery",
    run_id="run_recovery",
    job_id="job_recovery",
    correlation_id="corr_recovery",
    causation_id="cmd_recovery",
)


class RecordingController:
    def __init__(self, reconciliation=None) -> None:
        self.calls = []
        self.contexts = []
        self.reconciliation = reconciliation or ReconciliationResult(ReconciliationState.NOT_FOUND)

    def request_cancel(self, job, context, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("cancel", job.job_id, idempotency_key))

    def reconcile_operation(self, job, context):
        self.contexts.append(context)
        self.calls.append(("reconcile_operation", job.job_id, job.operation_id))
        return self.reconciliation

    def retry(self, job, context, attempt_id, skip_step_ids, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("retry", attempt_id, skip_step_ids, idempotency_key))

    def resume(self, job, context, attempt_id, resume_token, skip_step_ids, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("resume", attempt_id, resume_token, skip_step_ids, idempotency_key))


class FailingDispatchController(RecordingController):
    def retry(self, job, context, attempt_id, skip_step_ids, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("retry", attempt_id, skip_step_ids, idempotency_key))
        raise RuntimeError("fixture dispatch failure")


class FailOnceDispatchController(RecordingController):
    def __init__(self, reconciliation=None) -> None:
        super().__init__(reconciliation)
        self.failed = False

    def retry(self, job, context, attempt_id, skip_step_ids, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("retry", attempt_id, skip_step_ids, idempotency_key))
        if not self.failed:
            self.failed = True
            raise RuntimeError("fixture first dispatch failure")


class FailingCancelController(RecordingController):
    def request_cancel(self, job, context, idempotency_key):
        self.contexts.append(context)
        self.calls.append(("cancel", job.job_id, idempotency_key))
        raise RuntimeError("fixture cancel failure")


def job(
    state=JobState.FAILED,
    safety=RetrySafety.IDEMPOTENT,
    side_effect=SideEffectState.NONE,
    resume_token="resume_mock_01",
) -> RecoveryJob:
    return RecoveryJob(
        job_id="job_recovery",
        integration_id="unity",
        operation_id="op_recovery",
        attempt_id="attempt_1",
        state=state,
        retry_safety=safety,
        side_effect_state=side_effect,
        completed_step_ids=("scan",),
        resume_token=resume_token,
        mode=ExecutionMode.LIVE,
        context=RECOVERY_CONTEXT,
    )


def coordinator(record: RecoveryJob, controller: RecordingController):
    repository = InMemoryRecoveryRepository()
    repository.put(record)
    return RecoveryCoordinator(repository, controller, InMemoryRecoveryLedger()), repository


class RecoveryCoordinatorTests(unittest.TestCase):
    def test_timeout_marks_unknown_side_effect_for_reconciliation(self) -> None:
        target, repository = coordinator(job(state=JobState.RUNNING, side_effect=SideEffectState.STARTED), RecordingController())
        result = target.record_timeout("job_recovery", "timeout_key", RECOVERY_CONTEXT)

        self.assertEqual(JobState.TIMED_OUT, result.state)
        self.assertEqual("pending", result.reconciliation)
        self.assertEqual(SideEffectState.UNKNOWN, repository.get("job_recovery").side_effect_state)

    def test_cancel_is_requested_not_claimed_complete_and_is_idempotent(self) -> None:
        controller = RecordingController()
        target, _ = coordinator(job(state=JobState.RUNNING), controller)
        first = target.cancel("job_recovery", "cancel_key", RECOVERY_CONTEXT)
        duplicate = target.cancel("job_recovery", "cancel_key", RECOVERY_CONTEXT)

        self.assertEqual(JobState.CANCEL_REQUESTED, first.state)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(1, len(controller.calls))

    def test_retry_preserves_completed_steps_and_deduplicates_request(self) -> None:
        controller = RecordingController()
        target, _ = coordinator(job(), controller)
        first = target.retry("job_recovery", "attempt_2", "retry_key", RECOVERY_CONTEXT)
        duplicate = target.retry("job_recovery", "attempt_2", "retry_key", RECOVERY_CONTEXT)

        self.assertEqual(JobState.RUNNING, first.state)
        self.assertEqual(("retry", "attempt_2", ("scan",), "retry_key"), controller.calls[0])
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(1, len(controller.calls))

        event = build_recovery_requested_event(
            "evt_recovery",
            datetime(2026, 9, 4, tzinfo=timezone.utc),
            EventActor(type="user", id="usr_test"),
            first,
        )
        self.assertEqual("job.recovery.requested", event.event_type)
        self.assertEqual("corr_recovery", event.correlation_id)
        self.assertEqual("job_recovery", event.payload.job_id)

    def test_reconciliation_prevents_duplicate_completed_side_effect(self) -> None:
        controller = RecordingController(
            ReconciliationResult(ReconciliationState.COMPLETED, completed_step_ids=("publish",))
        )
        target, repository = coordinator(job(side_effect=SideEffectState.UNKNOWN), controller)
        result = target.retry("job_recovery", "attempt_2", "retry_reconcile_key", RECOVERY_CONTEXT)

        self.assertEqual(JobState.SUCCEEDED, result.state)
        self.assertEqual(["scan", "publish"], result.completed_step_ids)
        self.assertEqual(
            [("reconcile_operation", "job_recovery", "op_recovery")],
            controller.calls,
        )
        intent = repository.get("job_recovery").recovery_intents[-1]
        self.assertEqual(RecoveryIntentState.RECONCILED, intent.state)
        self.assertEqual(ReconciliationState.COMPLETED, intent.reconciliation)

    def test_non_idempotent_retry_is_blocked(self) -> None:
        target, _ = coordinator(job(safety=RetrySafety.NON_IDEMPOTENT), RecordingController())
        with self.assertRaises(UnsafeRecovery):
            target.retry("job_recovery", "attempt_2", "unsafe_retry_key", RECOVERY_CONTEXT)

    def test_dispatch_failure_persists_unknown_state_before_external_call(self) -> None:
        controller = FailingDispatchController()
        target, repository = coordinator(job(), controller)
        with self.assertRaises(RecoveryDispatchFailed):
            target.retry("job_recovery", "attempt_2", "dispatch_key", RECOVERY_CONTEXT)
        persisted = repository.get("job_recovery")
        self.assertEqual(JobState.FAILED, persisted.state)
        self.assertEqual(SideEffectState.UNKNOWN, persisted.side_effect_state)
        self.assertEqual("attempt_2", persisted.attempt_id)
        self.assertIn("attempt_1", persisted.prior_attempt_ids)
        self.assertEqual(RecoveryIntentState.UNKNOWN, persisted.recovery_intents[-1].state)
        self.assertEqual("dispatch_key", persisted.recovery_intents[-1].idempotency_key)

    def test_new_key_reconciles_old_unknown_intent_by_operation_id(self) -> None:
        controller = FailOnceDispatchController()
        target, repository = coordinator(job(), controller)
        with self.assertRaises(RecoveryDispatchFailed):
            target.retry("job_recovery", "attempt_2", "dispatch_key_one", RECOVERY_CONTEXT)

        result = target.retry(
            "job_recovery",
            "attempt_3",
            "dispatch_key_two",
            RECOVERY_CONTEXT,
        )

        persisted = repository.get("job_recovery")
        first_intent, second_intent = persisted.recovery_intents
        self.assertEqual(RecoveryIntentState.RECONCILED, first_intent.state)
        self.assertEqual(ReconciliationState.NOT_FOUND, first_intent.reconciliation)
        self.assertEqual(RecoveryIntentState.ACKNOWLEDGED, second_intent.state)
        self.assertEqual("attempt_3", result.attempt_id)
        self.assertEqual(
            ("reconcile_operation", "job_recovery", "op_recovery"),
            controller.calls[1],
        )

    def test_new_key_reconciles_old_acknowledged_intent(self) -> None:
        controller = RecordingController()
        target, repository = coordinator(job(), controller)
        target.retry("job_recovery", "attempt_2", "accepted_key", RECOVERY_CONTEXT)
        accepted = repository.get("job_recovery")
        repository.put(
            replace(
                accepted,
                state=JobState.FAILED,
                side_effect_state=SideEffectState.NONE,
            )
        )
        controller.reconciliation = ReconciliationResult(
            ReconciliationState.CONFIRMED_FAILED
        )

        target.retry("job_recovery", "attempt_3", "next_key", RECOVERY_CONTEXT)

        first_intent, second_intent = repository.get("job_recovery").recovery_intents
        self.assertEqual(RecoveryIntentState.RECONCILED, first_intent.state)
        self.assertEqual(ReconciliationState.CONFIRMED_FAILED, first_intent.reconciliation)
        self.assertEqual(
            ReconciliationState.CONFIRMED_FAILED,
            first_intent.last_reconciliation,
        )
        self.assertEqual(1, first_intent.reconciliation_count)
        self.assertEqual(RecoveryIntentState.ACKNOWLEDGED, second_intent.state)

    def test_same_key_redispatch_retains_latest_reconciliation(self) -> None:
        controller = FailOnceDispatchController()
        target, repository = coordinator(job(), controller)
        with self.assertRaises(RecoveryDispatchFailed):
            target.retry("job_recovery", "attempt_2", "same_key", RECOVERY_CONTEXT)

        target.retry("job_recovery", "attempt_2", "same_key", RECOVERY_CONTEXT)

        intent = repository.get("job_recovery").recovery_intents[-1]
        self.assertEqual(RecoveryIntentState.ACKNOWLEDGED, intent.state)
        self.assertIsNone(intent.reconciliation)
        self.assertEqual(ReconciliationState.NOT_FOUND, intent.last_reconciliation)
        self.assertEqual(1, intent.reconciliation_count)

    def test_cancel_failure_does_not_claim_cancel_requested(self) -> None:
        controller = FailingCancelController()
        target, repository = coordinator(job(state=JobState.RUNNING), controller)
        with self.assertRaises(RecoveryDispatchFailed):
            target.cancel("job_recovery", "cancel_dispatch_key", RECOVERY_CONTEXT)
        persisted = repository.get("job_recovery")
        self.assertEqual(JobState.RUNNING, persisted.state)
        self.assertEqual(SideEffectState.UNKNOWN, persisted.side_effect_state)
        self.assertEqual(RecoveryIntentState.UNKNOWN, persisted.recovery_intents[-1].state)

        reconciled = target.cancel("job_recovery", "cancel_dispatch_key", RECOVERY_CONTEXT)
        self.assertEqual("not_found", reconciled.reconciliation)
        self.assertEqual(
            [
                ("cancel", "job_recovery", "cancel_dispatch_key"),
                ("reconcile_operation", "job_recovery", "op_recovery"),
            ],
            controller.calls,
        )

    def test_resume_requires_checkpoint_reconciles_and_skips_completed_steps(self) -> None:
        controller = RecordingController(
            ReconciliationResult(ReconciliationState.NOT_FOUND, completed_step_ids=("export",))
        )
        target, _ = coordinator(
            job(state=JobState.TIMED_OUT, safety=RetrySafety.NON_IDEMPOTENT, side_effect=SideEffectState.UNKNOWN),
            controller,
        )
        result = target.resume("job_recovery", "attempt_2", "resume_key", RECOVERY_CONTEXT)

        self.assertEqual(JobState.RUNNING, result.state)
        self.assertEqual(
            ("resume", "attempt_2", "resume_mock_01", ("scan", "export"), "resume_key"),
            controller.calls[1],
        )

    def test_indeterminate_reconciliation_blocks_execution(self) -> None:
        controller = RecordingController(ReconciliationResult(ReconciliationState.INDETERMINATE))
        target, _ = coordinator(job(side_effect=SideEffectState.UNKNOWN), controller)
        with self.assertRaises(UnsafeRecovery):
            target.retry("job_recovery", "attempt_2", "indeterminate_key", RECOVERY_CONTEXT)
        self.assertEqual(
            [("reconcile_operation", "job_recovery", "op_recovery")],
            controller.calls,
        )

    def test_idempotency_key_cannot_be_reused_for_another_action(self) -> None:
        target, _ = coordinator(job(state=JobState.RUNNING), RecordingController())
        target.cancel("job_recovery", "shared_key", RECOVERY_CONTEXT)
        with self.assertRaises(IdempotencyConflict):
            target.record_timeout("job_recovery", "shared_key", RECOVERY_CONTEXT)

    def test_recovery_rejects_a_mismatched_correlation_chain(self) -> None:
        target, _ = coordinator(job(state=JobState.RUNNING), RecordingController())
        wrong = RECOVERY_CONTEXT.model_copy(update={"correlation_id": "corr_other"})
        with self.assertRaises(InvalidRecoveryState) as raised:
            target.cancel("job_recovery", "wrong_context_key", wrong)
        self.assertEqual("INVALID_RECOVERY_STATE", raised.exception.code)

    def test_cross_project_job_lookup_is_indistinguishable_from_missing(self) -> None:
        target, _ = coordinator(job(state=JobState.RUNNING), RecordingController())
        wrong_project = RECOVERY_CONTEXT.model_copy(update={"project_id": "prj_other"})
        with self.assertRaises(JobNotFound) as raised:
            target.cancel("job_recovery", "wrong_project_key", wrong_project)
        self.assertEqual("JOB_NOT_FOUND", raised.exception.code)

    def test_recovery_uses_new_causation_without_rewriting_original_context(self) -> None:
        controller = RecordingController()
        target, repository = coordinator(job(state=JobState.RUNNING), controller)
        action_context = RECOVERY_CONTEXT.model_copy(update={"causation_id": "cmd_recovery_action"})

        result = target.cancel("job_recovery", "causation_key", action_context)

        self.assertEqual("cmd_recovery_action", result.context.causation_id)
        self.assertEqual("cmd_recovery_action", controller.contexts[-1].causation_id)
        self.assertEqual("cmd_recovery", repository.get("job_recovery").context.causation_id)
        intent = repository.get("job_recovery").recovery_intents[-1]
        self.assertEqual("cmd_recovery_action", intent.context.causation_id)
        self.assertEqual(RecoveryIntentState.ACKNOWLEDGED, intent.state)

    def test_retry_rejects_current_and_historical_attempt_ids(self) -> None:
        record = replace(job(), prior_attempt_ids=("attempt_0",))
        target, _ = coordinator(record, RecordingController())
        for attempt_id in ("attempt_0", "attempt_1"):
            with self.subTest(attempt_id=attempt_id):
                with self.assertRaises(InvalidRecoveryState):
                    target.retry("job_recovery", attempt_id, "reuse_" + attempt_id, RECOVERY_CONTEXT)

    def test_non_live_job_cannot_reach_controller(self) -> None:
        controller = RecordingController()
        target, _ = coordinator(replace(job(), mode=ExecutionMode.MOCK), controller)
        with self.assertRaises(UnsafeRecovery):
            target.retry("job_recovery", "attempt_2", "mock_dispatch", RECOVERY_CONTEXT)
        self.assertEqual([], controller.calls)

    def test_idempotency_is_bound_to_job_and_project(self) -> None:
        repository = InMemoryRecoveryRepository()
        first = job()
        second_context = CorrelationContext(
            project_id="prj_second",
            run_id="run_second",
            job_id="job_second",
            correlation_id="corr_second",
            causation_id="cmd_second",
        )
        second = replace(first, job_id="job_second", context=second_context)
        repository.put(first)
        repository.put(second)
        controller = RecordingController()
        target = RecoveryCoordinator(repository, controller, InMemoryRecoveryLedger())

        first_result = target.retry("job_recovery", "attempt_2", "shared_job_key", RECOVERY_CONTEXT)
        second_result = target.retry("job_second", "attempt_2", "shared_job_key", second_context)

        self.assertEqual("job_recovery", first_result.job_id)
        self.assertEqual("job_second", second_result.job_id)
        self.assertEqual(2, len(controller.calls))


if __name__ == "__main__":
    unittest.main()
