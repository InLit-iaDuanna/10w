"""Safe timeout, cancellation, retry, and resume coordination."""

import threading
from dataclasses import replace

from observability import CorrelationContext

from .recovery_ports import (
    JobControlPort,
    RecoveryIntentState,
    RecoveryJob,
    RecoveryLedger,
    RecoveryRepository,
)
from .recovery_state import RecoveryStateOperations
from .recovery_support import (
    InvalidRecoveryState,
    RecoveryDispatchFailed,
    UnsafeRecovery,
    append_intent,
    build_result,
    dispatch_unknown,
    has_unresolved_intent,
    merged_steps,
    require_live,
    require_new_attempt,
    set_intent_state,
    with_context,
)
from .schemas import (
    JobState,
    RecoveryAction,
    RecoveryResult,
    RetrySafety,
    SideEffectState,
)


class RecoveryCoordinator(RecoveryStateOperations):
    def __init__(
        self,
        repository: RecoveryRepository,
        controller: JobControlPort,
        ledger: RecoveryLedger,
    ) -> None:
        super().__init__(repository, controller, ledger)
        self._lock = threading.RLock()

    def record_timeout(
        self,
        job_id: str,
        idempotency_key: str,
        context: CorrelationContext,
    ) -> RecoveryResult:
        with self._lock:
            job = with_context(self._require_job(job_id), context)
            require_live(job)
            duplicate = self._duplicate(
                job, RecoveryAction.TIMEOUT, idempotency_key, context, job.attempt_id
            )
            if duplicate:
                return duplicate
            existing = self._intent(job, RecoveryAction.TIMEOUT, idempotency_key, job.attempt_id, context)
            settled = self._settled(existing, job, context)
            if settled:
                return settled
            if job.state not in (JobState.QUEUED, JobState.RUNNING, JobState.PAUSED):
                raise InvalidRecoveryState("only active jobs can time out")
            side_effect = (
                SideEffectState.UNKNOWN
                if job.side_effect_state == SideEffectState.STARTED
                else job.side_effect_state
            )
            updated = replace(job, state=JobState.TIMED_OUT, side_effect_state=side_effect)
            updated = append_intent(
                updated,
                RecoveryAction.TIMEOUT,
                idempotency_key,
                updated.attempt_id,
                context,
            )
            updated = set_intent_state(updated, idempotency_key, RecoveryIntentState.ACKNOWLEDGED)
            self._repository.put(updated)
            result = build_result(
                updated,
                context,
                RecoveryAction.TIMEOUT,
                idempotency_key,
                "pending",
                "任务已超时；执行状态需要对账。",
            )
            return self._remember(result)

    def cancel(
        self,
        job_id: str,
        idempotency_key: str,
        context: CorrelationContext,
    ) -> RecoveryResult:
        with self._lock:
            job = with_context(self._require_job(job_id), context)
            require_live(job)
            duplicate = self._duplicate(
                job, RecoveryAction.CANCEL, idempotency_key, context, job.attempt_id
            )
            if duplicate:
                return duplicate
            existing = self._intent(job, RecoveryAction.CANCEL, idempotency_key, job.attempt_id, context)
            settled = self._settled(existing, job, context)
            if settled:
                return settled
            if job.state in (JobState.CANCELLED, JobState.SUCCEEDED):
                raise InvalidRecoveryState("completed jobs cannot be cancelled")
            prepared = self._prepare(job, RecoveryAction.CANCEL, idempotency_key, job.attempt_id, context)
            needs_reconciliation = (
                existing is not None
                or prepared.side_effect_state == SideEffectState.UNKNOWN
                or has_unresolved_intent(prepared, except_key=idempotency_key)
            )
            if needs_reconciliation:
                outcome = self._reconcile(prepared, context, idempotency_key)
                prepared = self._record_prior_reconciliation(
                    prepared,
                    idempotency_key,
                    outcome,
                    include_current=existing is not None,
                )
                terminal = self._resolve_cancel(prepared, context, outcome, idempotency_key)
                if terminal is not None:
                    return self._remember(terminal)
                prepared = replace(
                    prepared,
                    state=JobState.RUNNING,
                    side_effect_state=SideEffectState.STARTED,
                    completed_step_ids=merged_steps(prepared, outcome.completed_step_ids),
                )
            uncertain = replace(prepared, side_effect_state=SideEffectState.UNKNOWN)
            uncertain = set_intent_state(uncertain, idempotency_key, RecoveryIntentState.PENDING)
            self._repository.put(uncertain)
            try:
                self._controller.request_cancel(uncertain, context, idempotency_key)
            except Exception as error:
                self._repository.put(dispatch_unknown(uncertain, idempotency_key))
                raise RecoveryDispatchFailed(
                    "controller dispatch outcome is unknown; reconcile before another action"
                ) from error
            updated = replace(uncertain, state=JobState.CANCEL_REQUESTED)
            updated = set_intent_state(updated, idempotency_key, RecoveryIntentState.ACKNOWLEDGED)
            self._repository.put(updated)
            result = build_result(
                updated,
                context,
                RecoveryAction.CANCEL,
                idempotency_key,
                "pending",
                "已请求取消；外部副作用尚未确认停止。",
            )
            return self._remember(result)

    def retry(
        self,
        job_id: str,
        attempt_id: str,
        idempotency_key: str,
        context: CorrelationContext,
    ) -> RecoveryResult:
        with self._lock:
            job = with_context(self._require_job(job_id), context)
            require_live(job)
            duplicate = self._duplicate(
                job, RecoveryAction.RETRY, idempotency_key, context, attempt_id
            )
            if duplicate:
                return duplicate
            existing = self._intent(job, RecoveryAction.RETRY, idempotency_key, attempt_id, context)
            settled = self._settled(existing, job, context)
            if settled:
                return settled
            if existing is None and job.state not in (JobState.FAILED, JobState.TIMED_OUT):
                raise InvalidRecoveryState("only failed or timed-out jobs can be retried")
            if job.retry_safety == RetrySafety.NON_IDEMPOTENT:
                raise UnsafeRecovery("non-idempotent work requires an explicit adapter recovery decision")
            if existing is None:
                require_new_attempt(job, attempt_id)
            prepared = self._prepare(job, RecoveryAction.RETRY, idempotency_key, attempt_id, context)
            outcome = self._reconcile_if_needed(prepared, context, idempotency_key, existing is not None)
            if outcome is not None:
                prepared = self._record_prior_reconciliation(
                    prepared,
                    idempotency_key,
                    outcome,
                    include_current=existing is not None,
                )
                terminal = self._resolve_reconciliation(
                    prepared, context, outcome, RecoveryAction.RETRY, idempotency_key
                )
                if terminal is not None:
                    return self._remember(terminal)
                prepared = replace(
                    prepared,
                    completed_step_ids=merged_steps(prepared, outcome.completed_step_ids),
                )
            uncertain = self._new_attempt(prepared, attempt_id, idempotency_key)
            self._repository.put(uncertain)
            dispatching = replace(uncertain, state=JobState.RUNNING)
            try:
                self._controller.retry(
                    dispatching,
                    context,
                    attempt_id,
                    dispatching.completed_step_ids,
                    idempotency_key,
                )
            except Exception as error:
                self._repository.put(dispatch_unknown(uncertain, idempotency_key))
                raise RecoveryDispatchFailed(
                    "controller dispatch outcome is unknown; retry requires reconciliation"
                ) from error
            updated = replace(dispatching, side_effect_state=SideEffectState.STARTED)
            updated = set_intent_state(updated, idempotency_key, RecoveryIntentState.ACKNOWLEDGED)
            self._repository.put(updated)
            result = build_result(
                updated,
                context,
                RecoveryAction.RETRY,
                idempotency_key,
                "reconciled" if outcome else "not_required",
                "已启动安全重试；已完成步骤不会重复执行。",
            )
            return self._remember(result)

    def resume(
        self,
        job_id: str,
        attempt_id: str,
        idempotency_key: str,
        context: CorrelationContext,
    ) -> RecoveryResult:
        with self._lock:
            job = with_context(self._require_job(job_id), context)
            require_live(job)
            duplicate = self._duplicate(
                job, RecoveryAction.RESUME, idempotency_key, context, attempt_id
            )
            if duplicate:
                return duplicate
            existing = self._intent(job, RecoveryAction.RESUME, idempotency_key, attempt_id, context)
            settled = self._settled(existing, job, context)
            if settled:
                return settled
            if existing is None and job.state not in (
                JobState.PAUSED,
                JobState.FAILED,
                JobState.TIMED_OUT,
            ):
                raise InvalidRecoveryState("job is not resumable from its current state")
            if not job.resume_token:
                raise UnsafeRecovery("resume requires an adapter-issued resume token")
            if existing is None:
                require_new_attempt(job, attempt_id)
            prepared = self._prepare(job, RecoveryAction.RESUME, idempotency_key, attempt_id, context)
            outcome = self._reconcile(prepared, context, idempotency_key)
            prepared = self._record_prior_reconciliation(
                prepared,
                idempotency_key,
                outcome,
                include_current=existing is not None,
            )
            terminal = self._resolve_reconciliation(
                prepared, context, outcome, RecoveryAction.RESUME, idempotency_key
            )
            if terminal is not None:
                return self._remember(terminal)
            prepared = replace(
                prepared,
                completed_step_ids=merged_steps(prepared, outcome.completed_step_ids),
            )
            uncertain = self._new_attempt(prepared, attempt_id, idempotency_key)
            self._repository.put(uncertain)
            dispatching = replace(uncertain, state=JobState.RUNNING)
            try:
                self._controller.resume(
                    dispatching,
                    context,
                    attempt_id,
                    job.resume_token,
                    dispatching.completed_step_ids,
                    idempotency_key,
                )
            except Exception as error:
                self._repository.put(dispatch_unknown(uncertain, idempotency_key))
                raise RecoveryDispatchFailed(
                    "controller dispatch outcome is unknown; resume requires reconciliation"
                ) from error
            updated = replace(dispatching, side_effect_state=SideEffectState.STARTED)
            updated = set_intent_state(updated, idempotency_key, RecoveryIntentState.ACKNOWLEDGED)
            self._repository.put(updated)
            result = build_result(
                updated,
                context,
                RecoveryAction.RESUME,
                idempotency_key,
                "reconciled",
                "已从适配器检查点恢复；已完成步骤不会重复执行。",
            )
            return self._remember(result)
