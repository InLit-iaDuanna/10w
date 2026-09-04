"""Public integration health, worker, and recovery contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from observability import CorrelationContext, ExecutionMode, StructuredLogEvent
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from .contract_validation import STABLE_ID_PATTERN, VERSION_PATTERN, bounded_json, require_unique_stable


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, str_strip_whitespace=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include UTC")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must use UTC")
    return value.astimezone(timezone.utc)


class HealthSummaryState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    INCOMPATIBLE = "incompatible"
    BUSY = "busy"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class ConnectionState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class AuthorizationState(str, Enum):
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class CompatibilityState(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class AvailabilityState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ActivityState(str, Enum):
    IDLE = "idle"
    BUSY = "busy"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class WorkerLifecycle(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"
    UNKNOWN = "unknown"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"


class RetrySafety(str, Enum):
    IDEMPOTENT = "idempotent"
    COMPENSATED = "compensated"
    NON_IDEMPOTENT = "non_idempotent"


class SideEffectState(str, Enum):
    NONE = "none"
    STARTED = "started"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    TIMEOUT = "timeout"
    CANCEL = "cancel"
    RETRY = "retry"
    RESUME = "resume"


class ExecutionEvidence(ContractModel):
    mode: ExecutionMode
    observed_at: datetime
    source_run_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    reason: Optional[str] = Field(default=None, max_length=500)

    _validate_observed_at = field_validator("observed_at")(_require_utc)

    @model_validator(mode="after")
    def validate_mode_evidence(self):
        if self.mode == ExecutionMode.CACHED and not self.source_run_id:
            raise ValueError("cached evidence requires source_run_id")
        if self.mode in (ExecutionMode.PLANNED, ExecutionMode.BLOCKED) and not self.reason:
            raise ValueError("planned and blocked evidence require a reason")
        return self


class QueueSnapshot(ContractModel):
    depth: int = Field(ge=0)
    running: int = Field(ge=0)
    oldest_queued_at: Optional[datetime] = None

    @field_validator("oldest_queued_at")
    @classmethod
    def validate_oldest_queued_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else None


class JobPointer(ContractModel):
    job_id: str = Field(pattern=STABLE_ID_PATTERN)
    run_id: str = Field(pattern=STABLE_ID_PATTERN)
    correlation_id: str = Field(pattern=STABLE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=160)
    state: JobState
    progress: float = Field(ge=0.0, le=1.0)
    retry_safety: RetrySafety = RetrySafety.NON_IDEMPOTENT
    resume_available: bool = False
    completed_step_ids: List[str] = Field(default_factory=list, max_length=256)

    _validate_completed_steps = field_validator("completed_step_ids")(require_unique_stable)


class CapabilityReport(ContractModel):
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    tool_version: Optional[str] = Field(default=None, pattern=VERSION_PATTERN, max_length=120)
    adapter_version: str = Field(pattern=VERSION_PATTERN, max_length=120)
    observed_at: datetime
    capability_ids: List[str] = Field(max_length=128)
    allowlisted_command_ids: List[str] = Field(max_length=128)
    constraints: Dict[str, JsonValue] = Field(default_factory=dict, max_length=32)
    evidence: ExecutionEvidence

    _validate_observed_at = field_validator("observed_at")(_require_utc)
    _validate_unique_ids = field_validator("capability_ids", "allowlisted_command_ids")(require_unique_stable)

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value: Dict[str, JsonValue]) -> Dict[str, JsonValue]:
        if bounded_json(value) > 256:
            raise ValueError("capability constraints may not exceed 256 values")
        return value

    @model_validator(mode="after")
    def validate_evidence_time(self):
        if self.evidence.observed_at != self.observed_at:
            raise ValueError("capability report and evidence observation times must match")
        return self


class HealthProbe(ContractModel):
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    connection: ConnectionState
    authorization: AuthorizationState
    availability: AvailabilityState
    activity: ActivityState
    observed_at: datetime
    expires_at: datetime
    last_seen_at: Optional[datetime] = None
    tool_version: Optional[str] = Field(default=None, pattern=VERSION_PATTERN, max_length=120)
    adapter_version: str = Field(pattern=VERSION_PATTERN, max_length=120)
    current_job: Optional[JobPointer] = None
    queue: QueueSnapshot
    reason_code: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9_]{1,120}$")
    safe_reason: Optional[str] = Field(default=None, max_length=500)
    evidence: ExecutionEvidence

    _validate_observed_at = field_validator("observed_at")(_require_utc)
    _validate_expires_at = field_validator("expires_at")(_require_utc)

    @field_validator("last_seen_at")
    @classmethod
    def validate_last_seen_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_window(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be later than observed_at")
        if self.evidence.observed_at != self.observed_at:
            raise ValueError("probe and evidence observation times must match")
        return self


class CircuitSnapshot(ContractModel):
    state: CircuitState
    consecutive_failures: int = Field(ge=0)
    opened_at: Optional[datetime] = None
    retry_at: Optional[datetime] = None

    @field_validator("opened_at", "retry_at")
    @classmethod
    def validate_optional_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else None


class RecommendedAction(ContractModel):
    command_id: str = Field(pattern=STABLE_ID_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    available: bool
    unavailable_reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def explain_unavailable(self):
        if not self.available and not self.unavailable_reason:
            raise ValueError("unavailable actions require a reason")
        return self


class IntegrationHealthSnapshot(ContractModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    summary_state: HealthSummaryState
    connection: ConnectionState
    authorization: AuthorizationState
    compatibility: CompatibilityState
    availability: AvailabilityState
    activity: ActivityState
    observed_at: datetime
    expires_at: datetime
    last_seen_at: Optional[datetime] = None
    tool_version: Optional[str] = Field(default=None, pattern=VERSION_PATTERN, max_length=120)
    adapter_version: Optional[str] = Field(default=None, pattern=VERSION_PATTERN, max_length=120)
    capability_ids: List[str] = Field(default_factory=list, max_length=128)
    allowlisted_command_ids: List[str] = Field(default_factory=list, max_length=128)
    current_job: Optional[JobPointer] = None
    queue: QueueSnapshot
    circuit: CircuitSnapshot
    reason_code: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9_]{1,120}$")
    safe_reason: Optional[str] = Field(default=None, max_length=500)
    recommended_actions: List[RecommendedAction] = Field(max_length=32)
    is_current: bool
    live_actions_enabled: bool
    evidence: ExecutionEvidence

    _validate_observed_at = field_validator("observed_at")(_require_utc)
    _validate_unique_ids = field_validator("capability_ids", "allowlisted_command_ids")(require_unique_stable)
    _validate_expires_at = field_validator("expires_at")(_require_utc)

    @field_validator("last_seen_at")
    @classmethod
    def validate_last_seen_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_live_actions(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be later than observed_at")
        if self.evidence.observed_at != self.observed_at:
            raise ValueError("health snapshot and evidence observation times must match")
        if self.live_actions_enabled and (
            self.evidence.mode != ExecutionMode.LIVE
            or not self.is_current
            or self.summary_state not in (HealthSummaryState.CONNECTED, HealthSummaryState.BUSY)
        ):
            raise ValueError("live actions require current live connected or busy evidence")
        return self


class WorkerSnapshot(ContractModel):
    worker_id: str = Field(pattern=STABLE_ID_PATTERN)
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    lifecycle: WorkerLifecycle
    health_state: HealthSummaryState
    observed_at: datetime
    expires_at: datetime
    is_current: bool
    last_heartbeat_at: Optional[datetime] = None
    worker_version: str = Field(pattern=VERSION_PATTERN, max_length=120)
    capability_ids: List[str] = Field(max_length=128)
    current_job: Optional[JobPointer] = None
    queue: QueueSnapshot
    recommended_actions: List[RecommendedAction] = Field(max_length=32)
    evidence: ExecutionEvidence

    _validate_observed_at = field_validator("observed_at")(_require_utc)
    _validate_expires_at = field_validator("expires_at")(_require_utc)
    _validate_capabilities = field_validator("capability_ids")(require_unique_stable)

    @field_validator("last_heartbeat_at")
    @classmethod
    def validate_last_heartbeat_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_evidence_time(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("worker expiry must follow its observation time")
        if self.evidence.observed_at != self.observed_at:
            raise ValueError("worker snapshot and evidence observation times must match")
        live_control_ids = {"job.cancel", "job.retry", "job.resume"}
        if any(
            action.available and action.command_id in live_control_ids
            for action in self.recommended_actions
        ) and (self.evidence.mode != ExecutionMode.LIVE or not self.is_current):
            raise ValueError("worker control actions require current live evidence")
        return self


class IntegrationDetails(ContractModel):
    health: IntegrationHealthSnapshot
    recent_logs: List[StructuredLogEvent]


class CachedEvidence(ContractModel):
    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    source_run_id: str = Field(pattern=STABLE_ID_PATTERN)
    observed_at: datetime
    expires_at: datetime

    _validate_observed_at = field_validator("observed_at")(_require_utc)
    _validate_expires_at = field_validator("expires_at")(_require_utc)

    @model_validator(mode="after")
    def validate_window(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("cached evidence expiry must follow its observation time")
        return self


class JudgeFallback(ContractModel):
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    active: bool
    reason: str = Field(min_length=1, max_length=500)
    evidence_mode: ExecutionMode
    source_run_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    live_step_available: bool


class JudgeModeHealthSummary(ContractModel):
    mode: ExecutionMode
    headline: str
    live_step_available: bool
    integrations: List[IntegrationHealthSnapshot]
    fallbacks: List[JudgeFallback]


class RecoveryResult(ContractModel):
    job_id: str = Field(pattern=STABLE_ID_PATTERN)
    integration_id: str = Field(pattern=STABLE_ID_PATTERN)
    operation_id: str = Field(pattern=STABLE_ID_PATTERN)
    attempt_id: str = Field(pattern=STABLE_ID_PATTERN)
    action: RecoveryAction
    state: JobState
    completed_step_ids: List[str] = Field(max_length=256)
    idempotency_key: str = Field(pattern=STABLE_ID_PATTERN)
    context: CorrelationContext
    duplicate: bool = False
    reconciliation: str = Field(pattern=r"^[a-z_]{1,64}$")
    message: str = Field(min_length=1, max_length=500)
    mode: ExecutionMode

    _validate_completed_steps = field_validator("completed_step_ids")(require_unique_stable)


class RecoveryCommandRequest(ContractModel):
    context: CorrelationContext
    idempotency_key: str = Field(pattern=STABLE_ID_PATTERN)
    attempt_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)


class RestartGuidance(ContractModel):
    worker_id: str = Field(pattern=STABLE_ID_PATTERN)
    available: bool
    reason: str = Field(min_length=1, max_length=500)
    steps: List[str] = Field(min_length=1, max_length=16)
    command_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    requires_approval: bool = True
