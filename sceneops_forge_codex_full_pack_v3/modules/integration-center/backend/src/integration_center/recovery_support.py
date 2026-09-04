"""Stateless recovery invariants shared by the coordinator."""

from dataclasses import replace
from typing import Optional, Tuple

from observability import CorrelationContext, ExecutionMode

from .recovery_ports import (
    MAX_RECONCILIATION_COUNT,
    ReconciliationState,
    RecoveryIntent,
    RecoveryIntentState,
    RecoveryJob,
)
from .schemas import RecoveryAction, RecoveryResult, SideEffectState


class RecoveryError(RuntimeError):
    code = "RECOVERY_ERROR"


class JobNotFound(RecoveryError):
    code = "JOB_NOT_FOUND"


class InvalidRecoveryState(RecoveryError):
    code = "INVALID_RECOVERY_STATE"


class UnsafeRecovery(RecoveryError):
    code = "UNSAFE_RECOVERY"


class IdempotencyConflict(RecoveryError):
    code = "IDEMPOTENCY_CONFLICT"


class RecoveryDispatchFailed(RecoveryError):
    code = "RECOVERY_DISPATCH_UNKNOWN"


def with_context(job: RecoveryJob, context: CorrelationContext) -> RecoveryJob:
    expected = job.context
    if context.project_id != expected.project_id:
        raise JobNotFound("job was not found")
    if (
        context.run_id != expected.run_id
        or context.job_id != job.job_id
        or context.correlation_id != expected.correlation_id
    ):
        raise InvalidRecoveryState("recovery context does not match the recorded operation")
    return job


def require_new_attempt(job: RecoveryJob, attempt_id: str) -> None:
    if attempt_id == job.attempt_id or attempt_id in job.prior_attempt_ids:
        raise InvalidRecoveryState("retry and resume require a new attempt_id")


def require_live(job: RecoveryJob) -> None:
    if job.mode != ExecutionMode.LIVE:
        raise UnsafeRecovery("controller dispatch requires a live job record")


def merged_steps(job: RecoveryJob, step_ids: Tuple[str, ...]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(job.completed_step_ids + step_ids))


def find_intent(job: RecoveryJob, idempotency_key: str) -> Optional[RecoveryIntent]:
    return next(
        (intent for intent in job.recovery_intents if intent.idempotency_key == idempotency_key),
        None,
    )


def append_intent(
    job: RecoveryJob,
    action: RecoveryAction,
    idempotency_key: str,
    attempt_id: str,
    context: CorrelationContext,
) -> RecoveryJob:
    existing = find_intent(job, idempotency_key)
    if existing is not None:
        if (
            existing.action != action
            or existing.attempt_id != attempt_id
            or existing.context != context
        ):
            raise IdempotencyConflict("idempotency key is already bound to another recovery intent")
        return job
    if len(job.recovery_intents) >= 256:
        raise InvalidRecoveryState("recovery intent history limit reached")
    intent = RecoveryIntent(
        action=action,
        idempotency_key=idempotency_key,
        attempt_id=attempt_id,
        context=context,
        state=RecoveryIntentState.PENDING,
    )
    return replace(job, recovery_intents=job.recovery_intents + (intent,))


def set_intent_state(
    job: RecoveryJob,
    idempotency_key: str,
    state: RecoveryIntentState,
    reconciliation: Optional[ReconciliationState] = None,
) -> RecoveryJob:
    found = False
    intents = []
    for intent in job.recovery_intents:
        if intent.idempotency_key == idempotency_key:
            last_reconciliation = intent.last_reconciliation
            reconciliation_count = intent.reconciliation_count
            if (
                state == RecoveryIntentState.RECONCILED
                and reconciliation is not None
                and not (
                    intent.state == RecoveryIntentState.RECONCILED
                    and intent.reconciliation == reconciliation
                )
            ):
                last_reconciliation = reconciliation
                reconciliation_count = min(
                    reconciliation_count + 1,
                    MAX_RECONCILIATION_COUNT,
                )
            intents.append(
                replace(
                    intent,
                    state=state,
                    reconciliation=reconciliation,
                    last_reconciliation=last_reconciliation,
                    reconciliation_count=reconciliation_count,
                )
            )
            found = True
        else:
            intents.append(intent)
    if not found:
        raise InvalidRecoveryState("recovery intent was not persisted")
    return replace(job, recovery_intents=tuple(intents))


def has_unresolved_intent(job: RecoveryJob, except_key: Optional[str] = None) -> bool:
    return any(
        intent.idempotency_key != except_key
        and intent.state
        in (
            RecoveryIntentState.PENDING,
            RecoveryIntentState.ACKNOWLEDGED,
            RecoveryIntentState.UNKNOWN,
        )
        for intent in job.recovery_intents
    )


def build_result(
    job: RecoveryJob,
    context: CorrelationContext,
    action: RecoveryAction,
    idempotency_key: str,
    reconciliation: str,
    message: str,
) -> RecoveryResult:
    return RecoveryResult(
        job_id=job.job_id,
        integration_id=job.integration_id,
        operation_id=job.operation_id,
        attempt_id=job.attempt_id,
        action=action,
        state=job.state,
        completed_step_ids=list(job.completed_step_ids),
        idempotency_key=idempotency_key,
        context=context,
        reconciliation=reconciliation,
        message=message,
        mode=job.mode,
    )


def dispatch_unknown(job: RecoveryJob, idempotency_key: str) -> RecoveryJob:
    return replace(
        set_intent_state(job, idempotency_key, RecoveryIntentState.UNKNOWN),
        side_effect_state=SideEffectState.UNKNOWN,
    )
