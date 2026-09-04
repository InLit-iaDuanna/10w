from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StableId = Annotated[str, Field(min_length=3, max_length=160, pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")]
CommitId = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{7,64}$")]


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VersionReference(FrozenModel):
    provider: str = Field(default="git", pattern=r"^git$")
    repository_id: StableId
    object_format: str = Field(default="sha1", pattern=r"^(sha1|sha256)$")
    commit_id: CommitId
    branch: Optional[str] = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_object_id_length(self) -> "VersionReference":
        expected = 40 if self.object_format == "sha1" else 64
        if len(self.commit_id) != expected:
            raise ValueError(
                f"{self.object_format} version references require a full {expected}-character object ID"
            )
        return self

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value.startswith("-") or ".." in value or value.endswith("/"):
            raise ValueError("branch is not a safe Git reference name")
        return value


class Actor(FrozenModel):
    actor_type: str = Field(default="user", pattern=r"^(user|agent|service)$")
    actor_id: StableId


class ActionContext(FrozenModel):
    actor: Actor
    correlation_id: StableId
    causation_id: StableId
    mode: ExecutionMode
    permissions: frozenset[str]


class Clock(Protocol):
    def now(self) -> datetime: ...


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class IdFactory(Protocol):
    def new(self, prefix: str) -> str: ...


class UuidIdFactory:
    def new(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return value
