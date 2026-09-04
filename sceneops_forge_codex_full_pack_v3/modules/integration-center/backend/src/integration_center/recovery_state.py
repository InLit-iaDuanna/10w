"""Persistence, idempotency, and reconciliation operations for recovery."""

from dataclasses import replace
from typing import Optional

from observability import CorrelationContext

from .recovery_ports import (
    JobControlPort,
    ReconciliationResult,
    ReconciliationState,
    RecoveryIntent,
    RecoveryIntentState,
    RecoveryJob,
    RecoveryLedger,
    RecoveryLedgerEntry,
    RecoveryRepository,
)
from .recovery_support import (
    IdempotencyConflict,
    JobNotFound,
    RecoveryDispatchFailed,
    UnsafeRecovery,
    append_intent,
    build_result,
    dispatch_unknown,
    find_intent,
    has_unresolved_intent,
    merged_steps,
    set_intent_state,
)
from .schemas import JobState, RecoveryAction, RecoveryResult, SideEffectState


class RecoveryStateOperations:
    def __init__(
        self,
        repository: RecoveryRepository,
        controller: JobControlPort,
        ledger: RecoveryLedger,
    ) -> None:
        self._repository = repository
        self._controller = controller
        self._ledger = ledger

    def _prepare(
        self,
        job: RecoveryJob,
        action: RecoveryAction,
        idempotency_key: str,
        attempt_id: str,
        context: CorrelationContext,
    ) -> RecoveryJob:
        prepared = append_intent(job, action, idempotency_key, attempt_id, context)
        self._repository.put(prepared)
        return prepared

    @staticmethod
    def _intent(
        job: RecoveryJob,
        action: RecoveryAction,
        idempotency_key: str,
        attempt_id: str,
        context: CorrelationContext,
    ) -> Optional[RecoveryIntent]:
        existing = find_intent(job, idempotency_key)
        if existing is not None:
            append_intent(job, action, idempotency_key, attempt_id, context)
        return existing

    def _settled(
        self,
        intent: Optional[RecoveryIntent],
        job: RecoveryJob,
        context: CorrelationContext,
    ) -> Optional[RecoveryResult]:
        if intent is None:
            return None
        if (
            intent.state == RecoveryIntentState.RECONCILED
            and intent.action in (RecoveryAction.RETRY, RecoveryAction.RESUME)
            and intent.reconciliation
            in (
                ReconciliationState.NOT_FOUND,
                ReconciliationState.CONFIRMED_FAILED,
            )
        ):
            return None
        if intent.state not in (
            RecoveryIntentState.ACKNOWLEDGED,
            RecoveryIntentState.RECONCILED,
        ):
            return None
        reconciliation = (
            intent.reconciliation.value
            if intent.state == RecoveryIntentState.RECONCILED
            else "pending"
            if intent.action in (RecoveryAction.TIMEOUT, RecoveryAction.CANCEL)
            else "not_required"
        )
        result = build_result(
            job,
            context,
            intent.action,
            intent.idempotency_key,
            reconciliation,
            "恢复动作已经持久化；返回当前记录状态。",
        )
        return self._remember(result).model_copy(update={"duplicate": True})

    def _reconcile_if_needed(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        idempotency_key: str,
        existing_intent: bool,
    ) -> Optional[ReconciliationResult]:
        if (
            existing_intent
            or has_unresolved_intent(job, except_key=idempotency_key)
            or job.side_effect_state
            in (SideEffectState.STARTED, SideEffectState.UNKNOWN, SideEffectState.COMPLETED)
        ):
            return self._reconcile(job, context, idempotency_key)
        return None

    def _reconcile(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        idempotency_key: str,
    ) -> ReconciliationResult:
        try:
            return self._controller.reconcile_operation(job, context)
        except Exception as error:
            self._repository.put(dispatch_unknown(job, idempotency_key))
            raise RecoveryDispatchFailed("controller reconciliation failed safely") from error

    def _resolve_reconciliation(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        outcome: ReconciliationResult,
        action: RecoveryAction,
        idempotency_key: str,
    ) -> Optional[RecoveryResult]:
        completed_steps = merged_steps(job, outcome.completed_step_ids)
        if outcome.state == ReconciliationState.INDETERMINATE:
            self._repository.put(dispatch_unknown(job, idempotency_key))
            raise UnsafeRecovery("adapter could not determine the original operation state")
        if outcome.state == ReconciliationState.COMPLETED:
            updated = replace(
                set_intent_state(
                    job,
                    idempotency_key,
                    RecoveryIntentState.RECONCILED,
                    outcome.state,
                ),
                state=JobState.SUCCEEDED,
                side_effect_state=SideEffectState.COMPLETED,
                completed_step_ids=completed_steps,
            )
            message = "原操作已完成，未发起重复执行。"
        elif outcome.state == ReconciliationState.RUNNING:
            updated = replace(
                set_intent_state(
                    job,
                    idempotency_key,
                    RecoveryIntentState.RECONCILED,
                    outcome.state,
                ),
                state=JobState.RUNNING,
                side_effect_state=SideEffectState.STARTED,
                completed_step_ids=completed_steps,
            )
            message = "原操作仍在运行，未发起重复执行。"
        else:
            return None
        self._repository.put(updated)
        return build_result(
            updated, context, action, idempotency_key, outcome.state.value, message
        )

    def _resolve_cancel(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        outcome: ReconciliationResult,
        idempotency_key: str,
    ) -> Optional[RecoveryResult]:
        if outcome.state == ReconciliationState.RUNNING:
            return None
        if outcome.state == ReconciliationState.INDETERMINATE:
            self._repository.put(dispatch_unknown(job, idempotency_key))
            raise UnsafeRecovery("adapter could not determine the prior cancellation state")
        completed_steps = merged_steps(job, outcome.completed_step_ids)
        state = (
            JobState.SUCCEEDED
            if outcome.state == ReconciliationState.COMPLETED
            else JobState.FAILED
        )
        side_effect = (
            SideEffectState.COMPLETED
            if outcome.state == ReconciliationState.COMPLETED
            else SideEffectState.NONE
        )
        updated = replace(
            set_intent_state(
                job,
                idempotency_key,
                RecoveryIntentState.RECONCILED,
                outcome.state,
            ),
            state=state,
            side_effect_state=side_effect,
            completed_step_ids=completed_steps,
        )
        self._repository.put(updated)
        return build_result(
            updated,
            context,
            RecoveryAction.CANCEL,
            idempotency_key,
            outcome.state.value,
            "对账确认没有仍在运行的操作，未重复发送取消请求。",
        )

    def _record_prior_reconciliation(
        self,
        job: RecoveryJob,
        current_key: str,
        outcome: ReconciliationResult,
        include_current: bool,
    ) -> RecoveryJob:
        if outcome.state == ReconciliationState.INDETERMINATE:
            return job
        updated = job
        for intent in job.recovery_intents:
            if (
                (intent.idempotency_key != current_key or include_current)
                and (
                    intent.state
                    in (
                        RecoveryIntentState.PENDING,
                        RecoveryIntentState.ACKNOWLEDGED,
                        RecoveryIntentState.UNKNOWN,
                    )
                    or (
                        include_current
                        and intent.idempotency_key == current_key
                        and intent.state == RecoveryIntentState.RECONCILED
                    )
                )
            ):
                updated = set_intent_state(
                    updated,
                    intent.idempotency_key,
                    RecoveryIntentState.RECONCILED,
                    outcome.state,
                )
                self._repository.put(updated)
        return updated

    @staticmethod
    def _new_attempt(
        job: RecoveryJob,
        attempt_id: str,
        idempotency_key: str,
    ) -> RecoveryJob:
        prior_attempt_ids = job.prior_attempt_ids
        if job.attempt_id != attempt_id:
            prior_attempt_ids = tuple(dict.fromkeys(prior_attempt_ids + (job.attempt_id,)))
        updated = replace(
            job,
            attempt_id=attempt_id,
            side_effect_state=SideEffectState.UNKNOWN,
            prior_attempt_ids=prior_attempt_ids,
        )
        return set_intent_state(updated, idempotency_key, RecoveryIntentState.PENDING)

    def _require_job(self, job_id: str) -> RecoveryJob:
        job = self._repository.get(job_id)
        if job is None:
            raise JobNotFound("job was not found")
        return job

    def _duplicate(
        self,
        job: RecoveryJob,
        action: RecoveryAction,
        idempotency_key: str,
        context: CorrelationContext,
        attempt_id: str,
    ) -> Optional[RecoveryResult]:
        entry = self._ledger.get(job.integration_id, job.job_id, idempotency_key)
        if entry is None:
            return None
        recorded = entry.result
        if (
            entry.action != action
            or recorded.operation_id != job.operation_id
            or recorded.job_id != job.job_id
            or recorded.attempt_id != attempt_id
            or recorded.context != context
        ):
            raise IdempotencyConflict("idempotency key is already bound to another operation")
        return recorded.model_copy(update={"duplicate": True})

    def _remember(self, result: RecoveryResult) -> RecoveryResult:
        self._ledger.put(
            result.integration_id,
            result.job_id,
            result.idempotency_key,
            RecoveryLedgerEntry(action=result.action, result=result),
        )
        return result
