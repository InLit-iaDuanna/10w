from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from .base import ExecutionMode, FrozenModel, StableId, VersionReference, require_utc
from .git_models import GitFileChange, LfsPointer


class DiffState(str, Enum):
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"


class ConflictCode(str, Enum):
    GIT_OFFLINE = "git_offline"
    DIRTY_WORKTREE = "dirty_worktree"
    MERGE_CONFLICT = "merge_conflict"
    STALE_BASE = "stale_base"
    LOCKED_BINARY_ASSET = "locked_binary_asset"
    DELETED_TARGET = "deleted_target"
    INCOMPATIBLE_SCHEMA = "incompatible_schema"


class ReviewConflict(FrozenModel):
    code: ConflictCode
    message: str = Field(min_length=1, max_length=1000)
    blocking: bool
    target_id: Optional[str] = None
    path: Optional[str] = None


class SemanticEntity(FrozenModel):
    entity_id: StableId
    entity_kind: str = Field(min_length=1, max_length=120)
    schema_id: str = Field(min_length=1, max_length=200)
    schema_version: int = Field(ge=1)
    artifact_id: StableId
    producer_module: str = Field(min_length=1, max_length=120)
    values: dict[str, Any]
    mode: ExecutionMode


class SemanticChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class SemanticChange(FrozenModel):
    entity_id: StableId
    entity_kind: str
    path: str
    kind: SemanticChangeKind
    before: Any = None
    after: Any = None


class CameraPose(FrozenModel):
    coordinate_space: str = Field(default="world", pattern=r"^world$")
    axis_convention: str = Field(default="right-handed-y-up", pattern=r"^right-handed-y-up$")
    position_m: tuple[float, float, float]
    rotation_xyzw: tuple[float, float, float, float]
    projection: str = Field(pattern=r"^(perspective|orthographic)$")
    vertical_fov_degrees: Optional[float] = Field(default=None, gt=0, lt=180)


class VisualCapture(FrozenModel):
    artifact_id: StableId
    camera_id: StableId
    pose: CameraPose
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    channels: int = Field(default=1, ge=1, le=4)
    color_space: str = Field(min_length=1, max_length=80)
    capture_recipe_version: str = Field(min_length=1, max_length=80)
    renderer_version: str = Field(min_length=1, max_length=160)
    pixels: tuple[int, ...]
    mode: ExecutionMode

    @model_validator(mode="after")
    def validate_pixels(self) -> "VisualCapture":
        expected = self.width * self.height * self.channels
        if len(self.pixels) != expected:
            raise ValueError(f"pixels contains {len(self.pixels)} samples; expected {expected}")
        if any(value < 0 or value > 255 for value in self.pixels):
            raise ValueError("pixel samples must be in the inclusive range 0..255")
        return self


class BehaviorAssertion(FrozenModel):
    assertion_id: StableId
    passed: bool
    observed: Any = None
    expected: Any = None


class BehaviorStep(FrozenModel):
    step_id: StableId
    action_id: StableId
    outcome: str = Field(min_length=1, max_length=500)
    goal_progress: float = Field(ge=0, le=1)
    target_sceneops_id: Optional[StableId] = None


class BehaviorSnapshot(FrozenModel):
    run_id: StableId
    test_case_id: StableId
    build_id: StableId
    protocol_version: str = Field(min_length=1, max_length=80)
    config_id: StableId
    start_state_id: StableId
    seed: int
    objective_succeeded: bool
    assertions: tuple[BehaviorAssertion, ...]
    steps: tuple[BehaviorStep, ...]
    mode: ExecutionMode


class BehaviorChange(FrozenModel):
    key: StableId
    category: str = Field(pattern=r"^(objective|assertion|step)$")
    before: Any = None
    after: Any = None


class DiffLayerState(FrozenModel):
    state: DiffState
    failure_reason: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    mode: ExecutionMode

    @model_validator(mode="after")
    def validate_failure_reason(self) -> "DiffLayerState":
        if self.state == DiffState.FAILED and self.failure_reason is None:
            raise ValueError("failed diff layers require a failure_reason")
        if self.state != DiffState.FAILED and self.failure_reason is not None:
            raise ValueError("only failed diff layers may include failure_reason")
        return self


class FileDiffLayer(DiffLayerState):
    changes: tuple[GitFileChange, ...]
    lfs_pointers: tuple[LfsPointer, ...]


class SemanticDiffLayer(DiffLayerState):
    changes: tuple[SemanticChange, ...]


class VisualDiffLayer(DiffLayerState):
    base_artifact_id: Optional[StableId] = None
    target_artifact_id: Optional[StableId] = None
    camera_id: Optional[StableId] = None
    changed_samples: int = Field(default=0, ge=0)
    sample_count: int = Field(default=0, ge=0)
    mean_absolute_error: Optional[float] = Field(default=None, ge=0, le=255)
    maximum_absolute_error: Optional[int] = Field(default=None, ge=0, le=255)


class BehaviorDiffLayer(DiffLayerState):
    changes: tuple[BehaviorChange, ...]
    before_run_id: Optional[StableId] = None
    after_run_id: Optional[StableId] = None


class FourLayerDiff(FrozenModel):
    diff_bundle_id: StableId
    base_version: VersionReference
    target_version: VersionReference
    file: FileDiffLayer
    semantic: SemanticDiffLayer
    visual: VisualDiffLayer
    behavior: BehaviorDiffLayer
    conflicts: tuple[ReviewConflict, ...]
    sealed_at: datetime
    mode: ExecutionMode

    _utc = field_validator("sealed_at")(require_utc)

    @property
    def has_blocking_conflicts(self) -> bool:
        return any(conflict.blocking for conflict in self.conflicts)
