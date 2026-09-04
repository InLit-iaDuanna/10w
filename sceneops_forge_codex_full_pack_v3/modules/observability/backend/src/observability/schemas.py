"""Public, vendor-neutral observability contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


STABLE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"
FieldValue = Union[str, int, float, bool, None]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, str_strip_whitespace=True)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class LogLevel(str, Enum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProgressState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must use UTC")
    return value.astimezone(timezone.utc)


class CorrelationContext(ContractModel):
    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    run_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    job_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    correlation_id: str = Field(pattern=STABLE_ID_PATTERN)
    causation_id: str = Field(pattern=STABLE_ID_PATTERN)


class ArtifactLink(ContractModel):
    artifact_id: str = Field(pattern=STABLE_ID_PATTERN)
    label: str = Field(min_length=1, max_length=160)
    media_type: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$", max_length=120)


class StructuredLogEvent(ContractModel):
    event_id: str = Field(pattern=STABLE_ID_PATTERN)
    event_type: str = Field(default="observability.log.recorded", pattern=r"^observability\.log\.recorded$")
    event_version: int = Field(default=1, ge=1, le=1)
    emitted_at: datetime
    level: LogLevel
    source_module: str = Field(pattern=STABLE_ID_PATTERN)
    source_tool: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    worker_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    message: str = Field(min_length=1, max_length=4000)
    context: CorrelationContext
    fields: Dict[str, FieldValue] = Field(default_factory=dict, max_length=32)
    artifact_links: List[ArtifactLink] = Field(default_factory=list, max_length=32)
    mode: ExecutionMode
    sequence: Optional[int] = Field(default=None, ge=1)

    _validate_emitted_at = field_validator("emitted_at")(_require_utc)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: Dict[str, FieldValue]) -> Dict[str, FieldValue]:
        _validate_field_values(value)
        return value


class ProgressEvent(ContractModel):
    event_id: str = Field(pattern=STABLE_ID_PATTERN)
    event_type: str = Field(default="job.progress.reported", pattern=r"^job\.progress\.reported$")
    event_version: int = Field(default=1, ge=1, le=1)
    occurred_at: datetime
    source_module: str = Field(pattern=STABLE_ID_PATTERN)
    state: ProgressState
    progress: float = Field(ge=0.0, le=1.0)
    message: str = Field(min_length=1, max_length=1000)
    context: CorrelationContext
    fields: Dict[str, FieldValue] = Field(default_factory=dict, max_length=32)
    mode: ExecutionMode
    sequence: Optional[int] = Field(default=None, ge=1)

    _validate_occurred_at = field_validator("occurred_at")(_require_utc)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: Dict[str, FieldValue]) -> Dict[str, FieldValue]:
        _validate_field_values(value)
        return value


GatewayEvent = Union[StructuredLogEvent, ProgressEvent]


class EventBatch(ContractModel):
    events: List[GatewayEvent]
    next_cursor: str = Field(min_length=1)
    reset_required: bool = False


class LogQuery(ContractModel):
    text: Optional[str] = Field(default=None, max_length=200)
    minimum_level: Optional[LogLevel] = None
    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    run_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    job_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    correlation_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    source_module: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    source_tool: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)
    field_equals: Dict[str, FieldValue] = Field(default_factory=dict, max_length=16)
    limit: int = Field(default=200, ge=1, le=2000)

    @field_validator("field_equals")
    @classmethod
    def validate_field_equals(cls, value: Dict[str, FieldValue]) -> Dict[str, FieldValue]:
        _validate_field_values(value)
        return value


class LogPage(ContractModel):
    items: List[StructuredLogEvent]
    total: int = Field(ge=0)


def _validate_field_values(value: Dict[str, FieldValue]) -> None:
    for key, item in value.items():
        if not key or len(key) > 64 or not key.replace("_", "").isalnum():
            raise ValueError("structured field names must be short alphanumeric identifiers")
        if isinstance(item, str) and len(item) > 1000:
            raise ValueError("structured string fields may not exceed 1000 characters")
