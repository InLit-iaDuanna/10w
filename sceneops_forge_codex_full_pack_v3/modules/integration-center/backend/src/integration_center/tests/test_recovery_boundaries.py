import unittest

from observability import CorrelationContext, ExecutionMode

from integration_center import (
    InMemoryRecoveryLedger,
    InMemoryRecoveryRepository,
    JobState,
    ReconciliationResult,
    ReconciliationState,
    RecoveryAction,
    RecoveryCoordinator,
    RecoveryIntent,
    RecoveryIntentState,
    RecoveryJob,
    RetrySafety,
    SideEffectState,
)
from integration_center.recovery_ports import MAX_RECONCILIATION_COUNT


CONTEXT = CorrelationContext(
    project_id="prj_recovery",
    run_id="run_recovery",
    job_id="job_recovery",
    correlation_id="corr_recovery",
    causation_id="cmd_recovery",
)


class RecordingController:
    def __init__(self) -> None:
        self.calls = []

    def reconcile_operation(self, job, context):
        self.calls.append(("reconcile_operation", job.job_id, job.operation_id))
        return ReconciliationResult(ReconciliationState.CONFIRMED_FAILED)

    def retry(self, job, context, attempt_id, skip_step_ids, idempotency_key):
        self.calls.append(("retry", attempt_id, skip_step_ids, idempotency_key))

    def request_cancel(self, job, context, idempotency_key):
        raise AssertionError("cancel is outside this fixture")

    def resume(self, job, context, attempt_id, resume_token, skip_step_ids, idempotency_key):
        raise AssertionError("resume is outside this fixture")


def recovery_job(intent: RecoveryIntent) -> RecoveryJob:
    return RecoveryJob(
        job_id="job_recovery",
        integration_id="unity",
        operation_id="op_recovery",
        attempt_id="attempt_2",
        state=JobState.FAILED,
        retry_safety=RetrySafety.IDEMPOTENT,
        side_effect_state=SideEffectState.UNKNOWN,
        completed_step_ids=("scan",),
        resume_token=None,
        mode=ExecutionMode.LIVE,
        context=CONTEXT,
        prior_attempt_ids=("attempt_1",),
        recovery_intents=(intent,),
    )


def coordinator(intent: RecoveryIntent):
    repository = InMemoryRecoveryRepository()
    repository.put(recovery_job(intent))
    controller = RecordingController()
    target = RecoveryCoordinator(repository, controller, InMemoryRecoveryLedger())
    return target, repository, controller


class RecoveryBoundaryTests(unittest.TestCase):
    def test_same_key_continues_after_reconciled_predispatch_crash_window(self) -> None:
        intent = RecoveryIntent(
            action=RecoveryAction.RETRY,
            idempotency_key="crash_window_key",
            attempt_id="attempt_2",
            context=CONTEXT,
            state=RecoveryIntentState.RECONCILED,
            reconciliation=ReconciliationState.NOT_FOUND,
            last_reconciliation=ReconciliationState.NOT_FOUND,
            reconciliation_count=1,
        )
        target, repository, controller = coordinator(intent)

        target.retry(
            "job_recovery",
            "attempt_2",
            "crash_window_key",
            CONTEXT,
        )

        persisted = repository.get("job_recovery").recovery_intents[-1]
        self.assertEqual(RecoveryIntentState.ACKNOWLEDGED, persisted.state)
        self.assertEqual(
            ReconciliationState.CONFIRMED_FAILED,
            persisted.last_reconciliation,
        )
        self.assertEqual(2, persisted.reconciliation_count)
        self.assertEqual(
            [
                ("reconcile_operation", "job_recovery", "op_recovery"),
                ("retry", "attempt_2", ("scan",), "crash_window_key"),
            ],
            controller.calls,
        )

    def test_reconciliation_count_saturates_without_growing_the_aggregate(self) -> None:
        intent = RecoveryIntent(
            action=RecoveryAction.RETRY,
            idempotency_key="bounded_key",
            attempt_id="attempt_2",
            context=CONTEXT,
            state=RecoveryIntentState.UNKNOWN,
            last_reconciliation=ReconciliationState.NOT_FOUND,
            reconciliation_count=MAX_RECONCILIATION_COUNT,
        )
        target, repository, _controller = coordinator(intent)

        target.retry("job_recovery", "attempt_2", "bounded_key", CONTEXT)

        persisted = repository.get("job_recovery").recovery_intents[-1]
        self.assertEqual(MAX_RECONCILIATION_COUNT, persisted.reconciliation_count)
        self.assertEqual(
            ReconciliationState.CONFIRMED_FAILED,
            persisted.last_reconciliation,
        )


if __name__ == "__main__":
    unittest.main()
