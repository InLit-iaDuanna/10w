"""Shared value objects owned by the character-animation module."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Reject unknown fields so adapter and API boundaries stay inspectable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ApprovalState(str, Enum):
    DRAFT = "draft"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class CheckStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    BLOCKED = "blocked"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CoordinateSystem(StrictModel):
    space: Literal["character_local", "rig_local", "unity_local"]
    handedness: Literal["left", "right"]
    up_axis: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
    forward_axis: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
    meters_per_unit: float

    @model_validator(mode="after")
    def axes_must_be_distinct(self) -> "CoordinateSystem":
        if self.up_axis.lstrip("-") == self.forward_axis.lstrip("-"):
            raise ValueError("up_axis and forward_axis must use different dimensions")
        return self


class ApprovalRecord(StrictModel):
    state: ApprovalState = ApprovalState.DRAFT
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    comment: Optional[str] = None

    @field_validator("reviewed_at")
    @classmethod
    def normalize_review_time(cls, value: Optional[datetime]) -> Optional[datetime]:
        return normalize_utc(value)

    @model_validator(mode="after")
    def terminal_decisions_have_a_reviewer(self) -> "ApprovalRecord":
        if self.state in {ApprovalState.APPROVED, ApprovalState.REJECTED}:
            if not self.reviewed_by or not self.reviewed_at or not self.comment:
                raise ValueError("approved and rejected records require reviewer, time, and comment")
        return self


Sha256Checksum = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Provenance(StrictModel):
    artifact_id: str = Field(min_length=3)
    artifact_type: str = Field(min_length=3)
    source_project_id: str = Field(min_length=3)
    source_version: str = Field(min_length=1)
    source_commit: Optional[str] = None
    related_sceneops_ids: List[str] = Field(default_factory=list)
    producing_module: Literal["character-animation"] = "character-animation"
    tool: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    recipe_version: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    execution_mode: ExecutionMode
    created_at: datetime
    checksum_sha256: Sha256Checksum
    approval_state: ApprovalState
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    workflow_reference: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    parameters: Dict[str, object] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = normalize_utc(value)
        if normalized is None:
            raise ValueError("created_at is required")
        return normalized


class FeatureLink(StrictModel):
    feature_spec_id: str = Field(min_length=3)
    task_ids: List[str] = Field(min_length=1)


class VersionReference(StrictModel):
    entity_id: str = Field(min_length=3)
    version_number: int = Field(ge=1)


Vector3 = Tuple[float, float, float]


def normalize_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset")
    return value.astimezone(timezone.utc)
