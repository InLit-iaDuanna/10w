from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import Field, field_validator, model_validator

from .models import ContractModel, ExecutionMode


class PlannerExecutionContext(ContractModel):
    actor_id: str = Field(min_length=1)
    ai_initiated: bool
    occurred_at: datetime
    execution_mode: ExecutionMode
    correlation_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    change_set_id: Optional[str] = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("occurred_at must use UTC")
        return value


class VerifiedRunTiming(ContractModel):
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    mode: ExecutionMode
    originating_live_run_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_verified_timing(self) -> "VerifiedRunTiming":
        for field_name in ("started_at", "completed_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
                raise ValueError(f"{field_name} must use UTC")
        if self.completed_at <= self.started_at:
            raise ValueError("completed_at must be after started_at")
        if self.mode not in {ExecutionMode.LIVE, ExecutionMode.CACHED}:
            raise ValueError("verified run timing must be live or cached")
        if self.mode == ExecutionMode.CACHED and not self.originating_live_run_id:
            raise ValueError("cached timing requires originating_live_run_id")
        return self


class VerifiedApproval(ContractModel):
    approval_ref_id: str = Field(min_length=1)
    scope: str = Field(pattern="^(plan|task)$")
    scope_id: str = Field(min_length=1)
    mode: ExecutionMode

    @model_validator(mode="after")
    def validate_verified_mode(self) -> "VerifiedApproval":
        if self.mode not in {ExecutionMode.LIVE, ExecutionMode.CACHED, ExecutionMode.MOCK}:
            raise ValueError("approval verification must be live, cached, or mock")
        return self
