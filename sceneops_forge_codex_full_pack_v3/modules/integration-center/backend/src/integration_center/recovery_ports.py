"""Typed recovery records, adapter ports, and deterministic fixture stores."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Protocol, Tuple

from observability import CorrelationContext, ExecutionMode

from .contract_validation import STABLE_ID_PATTERN, require_unique_stable
from .schemas import JobState, RecoveryAction, RecoveryResult, RetrySafety, SideEffectState


class ReconciliationState(str, Enum):
    COMPLETED = "completed"
    RUNNING = "running"
    NOT_FOUND = "not_found"
    CONFIRMED_FAILED = "confirmed_failed"
    INDETERMINATE = "indeterminate"


class RecoveryIntentState(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


MAX_RECONCILIATION_COUNT = 2_147_483_647


@dataclass(frozen=True)
class ReconciliationResult:
    state: ReconciliationState
    completed_step_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_unique_stable(list(self.completed_step_ids))


@dataclass(frozen=True)
class RecoveryIntent:
    action: RecoveryAction
    idempotency_key: str
    attempt_id: str
    context: CorrelationContext
    state: RecoveryIntentState
    reconciliation: Optional[ReconciliationState] = None
    last_reconciliation: Optional[ReconciliationState] = None
    reconciliation_count: int = 0

    def __post_init__(self) -> None:
        for value in (self.idempotency_key, self.attempt_id):
            if re.fullmatch(STABLE_ID_PATTERN, value) is None:
                raise ValueError("recovery intents require stable identifiers")
        if self.state == RecoveryIntentState.RECONCILED and self.reconciliation is None:
            raise ValueError("reconciled intents require an operation reconciliation result")
        if self.state != RecoveryIntentState.RECONCILED and self.reconciliation is not None:
            raise ValueError("only reconciled intents may retain a reconciliation result")
        if self.last_reconciliation == ReconciliationState.INDETERMINATE:
            raise ValueError("recovery intents may retain only determinate results")
        if not 0 <= self.reconciliation_count <= MAX_RECONCILIATION_COUNT:
            raise ValueError("reconciliation_count is outside its bounded range")
        if (self.reconciliation_count == 0) != (self.last_reconciliation is None):
            raise ValueError("reconciliation_count and last_reconciliation must agree")
        if (
            self.reconciliation is not None
            and self.reconciliation != self.last_reconciliation
        ):
            raise ValueError("current reconciliation must match the latest recorded result")


@dataclass(frozen=True)
class RecoveryJob:
    job_id: str
    integration_id: str
    operation_id: str
    attempt_id: str
    state: JobState
    retry_safety: RetrySafety
    side_effect_state: SideEffectState
    completed_step_ids: Tuple[str, ...]
    resume_token: Optional[str]
    mode: ExecutionMode
    context: CorrelationContext
    prior_attempt_ids: Tuple[str, ...] = ()
    recovery_intents: Tuple[RecoveryIntent, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.job_id, self.integration_id, self.operation_id, self.attempt_id):
            if re.fullmatch(STABLE_ID_PATTERN, value) is None:
                raise ValueError("recovery records require stable identifiers")
        require_unique_stable(list(self.completed_step_ids))
        require_unique_stable(list(self.prior_attempt_ids))
        if self.attempt_id in self.prior_attempt_ids:
            raise ValueError("current attempt_id may not appear in prior_attempt_ids")
        if self.context.job_id != self.job_id:
            raise ValueError("recovery record context must identify its job")
        intent_keys = [intent.idempotency_key for intent in self.recovery_intents]
        if len(intent_keys) > 256:
            raise ValueError("recovery records may retain at most 256 active intents")
        if len(intent_keys) != len(set(intent_keys)):
            raise ValueError("recovery intent idempotency keys must be unique per job")
        for intent in self.recovery_intents:
            if (
                intent.context.project_id != self.context.project_id
                or intent.context.run_id != self.context.run_id
                or intent.context.job_id != self.job_id
                or intent.context.correlation_id != self.context.correlation_id
            ):
                raise ValueError("recovery intent context must match its recorded operation")


class JobControlPort(Protocol):
    """Allowlisted adapter operations; mutating calls deduplicate by idempotency key."""

    def request_cancel(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        idempotency_key: str,
    ) -> None:
        ...

    def reconcile_operation(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
    ) -> ReconciliationResult:
        """Query the immutable operation_id; never scope lookup by a recovery key."""
        ...

    def retry(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        attempt_id: str,
        skip_step_ids: Tuple[str, ...],
        idempotency_key: str,
    ) -> None:
        ...

    def resume(
        self,
        job: RecoveryJob,
        context: CorrelationContext,
        attempt_id: str,
        resume_token: str,
        skip_step_ids: Tuple[str, ...],
        idempotency_key: str,
    ) -> None:
        ...


class RecoveryRepository(Protocol):
    def get(self, job_id: str) -> Optional[RecoveryJob]:
        ...

    def put(self, job: RecoveryJob) -> None:
        ...


@dataclass(frozen=True)
class RecoveryLedgerEntry:
    action: RecoveryAction
    result: RecoveryResult


class RecoveryLedger(Protocol):
    def get(
        self,
        integration_id: str,
        job_id: str,
        idempotency_key: str,
    ) -> Optional[RecoveryLedgerEntry]:
        ...

    def put(
        self,
        integration_id: str,
        job_id: str,
        idempotency_key: str,
        entry: RecoveryLedgerEntry,
    ) -> None:
        ...


class InMemoryRecoveryRepository:
    """Deterministic fixture repository; production must inject durable storage."""

    def __init__(self) -> None:
        self._jobs: Dict[str, RecoveryJob] = {}

    def get(self, job_id: str) -> Optional[RecoveryJob]:
        return self._jobs.get(job_id)

    def put(self, job: RecoveryJob) -> None:
        self._jobs[job.job_id] = job


class InMemoryRecoveryLedger:
    """Deterministic fixture ledger; production must inject durable storage."""

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str, str], RecoveryLedgerEntry] = {}

    def get(
        self,
        integration_id: str,
        job_id: str,
        idempotency_key: str,
    ) -> Optional[RecoveryLedgerEntry]:
        return self._entries.get((integration_id, job_id, idempotency_key))

    def put(
        self,
        integration_id: str,
        job_id: str,
        idempotency_key: str,
        entry: RecoveryLedgerEntry,
    ) -> None:
        self._entries[(integration_id, job_id, idempotency_key)] = entry
