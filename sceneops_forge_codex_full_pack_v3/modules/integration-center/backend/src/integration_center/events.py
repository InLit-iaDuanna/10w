"""Builders for versioned integration and recovery event contracts."""

from datetime import datetime
from typing import Optional

from observability import ExecutionMode
from pydantic import Field, field_validator

from .contract_validation import STABLE_ID_PATTERN
from .schemas import (
    ContractModel,
    HealthSummaryState,
    IntegrationHealthSnapshot,
    RecoveryAction,
    RecoveryResult,
    _require_utc,
)


class EventActor(ContractModel):
    type: str = Field(pattern=r"^(user|agent|system|worker)$")
    id: str = Field(pattern=STABLE_ID_PATTERN)


class IntegrationHealthChangedPayload(ContractModel):
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    run_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    job_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    previous_state: Optional[HealthSummaryState] = None
    current: IntegrationHealthSnapshot


class IntegrationHealthChangedEvent(ContractModel):
    event_id: str = Field(pattern=STABLE_ID_PATTERN)
    event_type: str = Field(default="integration.health.changed", pattern=r"^integration\.health\.changed$")
    event_version: int = Field(default=1, ge=1, le=1)
    occurred_at: datetime
    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    correlation_id: str = Field(pattern=STABLE_ID_PATTERN)
    causation_id: str = Field(pattern=STABLE_ID_PATTERN)
    actor: EventActor
    mode: ExecutionMode
    payload: IntegrationHealthChangedPayload

    _validate_occurred_at = field_validator("occurred_at")(_require_utc)


class JobRecoveryRequestedPayload(ContractModel):
    job_id: str = Field(pattern=STABLE_ID_PATTERN)
    run_id: str = Field(pattern=STABLE_ID_PATTERN)
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    operation_id: str = Field(pattern=STABLE_ID_PATTERN)
    attempt_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    action: RecoveryAction


class JobRecoveryRequestedEvent(ContractModel):
    event_id: str = Field(pattern=STABLE_ID_PATTERN)
    event_type: str = Field(default="job.recovery.requested", pattern=r"^job\.recovery\.requested$")
    event_version: int = Field(default=1, ge=1, le=1)
    occurred_at: datetime
    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    correlation_id: str = Field(pattern=STABLE_ID_PATTERN)
    causation_id: str = Field(pattern=STABLE_ID_PATTERN)
    actor: EventActor
    mode: ExecutionMode
    payload: JobRecoveryRequestedPayload

    _validate_occurred_at = field_validator("occurred_at")(_require_utc)


def build_health_changed_event(
    event_id: str,
    occurred_at: datetime,
    actor: EventActor,
    current: IntegrationHealthSnapshot,
    project_id: str,
    correlation_id: str,
    causation_id: str,
    previous: Optional[IntegrationHealthSnapshot] = None,
    run_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> IntegrationHealthChangedEvent:
    if previous is not None and previous.integration_id != current.integration_id:
        raise ValueError("previous and current integration IDs must match")
    return IntegrationHealthChangedEvent(
        event_id=event_id,
        occurred_at=occurred_at,
        project_id=project_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        actor=actor,
        mode=current.evidence.mode,
        payload=IntegrationHealthChangedPayload(
            integration_id=current.integration_id,
            run_id=run_id,
            job_id=job_id,
            previous_state=previous.summary_state if previous else None,
            current=current,
        ),
    )


def build_recovery_requested_event(
    event_id: str,
    occurred_at: datetime,
    actor: EventActor,
    result: RecoveryResult,
) -> JobRecoveryRequestedEvent:
    context = result.context
    if context.run_id is None or context.job_id is None:
        raise ValueError("recovery events require run_id and job_id")
    return JobRecoveryRequestedEvent(
        event_id=event_id,
        occurred_at=occurred_at,
        project_id=context.project_id,
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        actor=actor,
        mode=result.mode,
        payload=JobRecoveryRequestedPayload(
            job_id=context.job_id,
            run_id=context.run_id,
            integration_id=result.integration_id,
            operation_id=result.operation_id,
            attempt_id=result.attempt_id,
            action=result.action,
        ),
    )
