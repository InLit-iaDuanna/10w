from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must use UTC")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]
StableId = Annotated[
    str,
    Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
RunId = Annotated[
    str,
    Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
JsonScalar = Union[str, int, float, bool, None]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class AgentMode(str, Enum):
    SMOKE = "smoke"
    GOAL_DRIVEN = "goal_driven"
    EXPLORER = "explorer"
    DESTRUCTIVE = "destructive"
    PERSONA = "persona"


class ActionKind(str, Enum):
    MOVE = "move"
    LOOK = "look"
    INTERACT = "interact"
    USE_ITEM = "use_item"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    REGISTERED = "registered"


class GoalState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ActionOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class FailureKind(str, Enum):
    TIMEOUT = "timeout"
    STALL = "stall"
    SOFT_LOCK = "soft_lock"
    UNREACHABLE_GOAL = "unreachable_goal"
    REPEATED_FAILED_INTERACTION = "repeated_failed_interaction"
    NAVIGATION_ERROR = "navigation_error"
    COLLIDER_ERROR = "collider_error"
    MISSING_FEEDBACK = "missing_feedback"
    QUEST_STATE_MISMATCH = "quest_state_mismatch"
    RUNTIME_ERROR = "runtime_error"
    PERFORMANCE_REGRESSION = "performance_regression"
    TELEMETRY_LOSS = "telemetry_loss"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BackpinTargetType(str, Enum):
    SCENE_OBJECT = "scene_object"
    ASSET = "asset"
    COMPONENT = "component"
    SCRIPT = "script"
    FEATURE = "feature"
    ACCEPTANCE_CRITERION = "acceptance_criterion"


class BackpinStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class RegressionStatus(str, Enum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    MIXED = "mixed"
    INCOMPARABLE = "incomparable"


class MetricDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class MetricOutcome(str, Enum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    MISSING = "missing"


class Vector3(StrictModel):
    x: float
    y: float
    z: float


class Pose(StrictModel):
    position: Vector3
    rotation_euler_deg: Vector3
    coordinate_space: Literal["unity_world"] = "unity_world"
    axis_convention: Literal["left_handed_y_up_z_forward"] = (
        "left_handed_y_up_z_forward"
    )
    distance_unit: Literal["meter"] = "meter"


class CameraEvidence(StrictModel):
    camera_id: StableId
    pose: Pose
    field_of_view_deg: Annotated[float, Field(gt=0, lt=180)]
    screenshot_artifact_id: Optional[StableId] = None


class ArtifactReference(StrictModel):
    artifact_id: StableId
    artifact_type: str = Field(min_length=1)
    execution_mode: ExecutionMode
    uri: Optional[str] = None
    source_project_id: StableId
    source_version: str = Field(min_length=1)
    source_commit: Optional[str] = None
    related_sceneops_ids: List[StableId] = Field(default_factory=list)
    producing_module: StableId
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    creator_id: StableId
    created_at: UtcDatetime
    approval_state: Literal["unreviewed", "approved", "rejected"]


class TestGoal(StrictModel):
    goal_id: StableId
    description: str = Field(min_length=1)
    acceptance_criterion_ids: List[StableId] = Field(default_factory=list)


class GoalProgress(StrictModel):
    goal_id: StableId
    state: GoalState
    value: Annotated[float, Field(ge=0, le=1)]
    detail: str = ""


class RuntimeErrorRecord(StrictModel):
    error_id: StableId
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source_sceneops_id: Optional[StableId] = None


class AvailableAction(StrictModel):
    action_id: StableId
    kind: ActionKind
    label: str = Field(min_length=1)
    target_sceneops_id: Optional[StableId] = None
    parameters: Dict[str, JsonScalar] = Field(default_factory=dict)
    advances_goal_ids: List[StableId] = Field(default_factory=list)
    goal_relevance: Annotated[float, Field(ge=0, le=1)] = 0
    destructive: bool = False
    registered_action_id: Optional[StableId] = None
    feedback_expected: bool = False

    @model_validator(mode="after")
    def validate_registered_action(self) -> "AvailableAction":
        if self.kind == ActionKind.REGISTERED and not self.registered_action_id:
            raise ValueError("registered actions require registered_action_id")
        if self.kind != ActionKind.REGISTERED and self.registered_action_id:
            raise ValueError("registered_action_id is only valid for registered actions")
        return self


class ActionResult(StrictModel):
    outcome: ActionOutcome
    detail: str = ""
    error_code: Optional[str] = None
    feedback: List[str] = Field(default_factory=list)
    duration_ms: Annotated[int, Field(ge=0)]


class Observation(StrictModel):
    observed_at: UtcDatetime
    telemetry_sequence: Annotated[int, Field(ge=0)]
    build_id: StableId
    scene_id: StableId
    actor_sceneops_id: StableId
    pose: Pose
    camera: CameraEvidence
    game_state: Dict[str, JsonScalar] = Field(default_factory=dict)
    goals: List[GoalProgress]
    available_actions: List[AvailableAction]
    runtime_errors: List[RuntimeErrorRecord] = Field(default_factory=list)
    frame_time_ms: Annotated[float, Field(ge=0)]
    memory_mb: Optional[Annotated[float, Field(ge=0)]] = None

    @model_validator(mode="after")
    def validate_collections(self) -> "Observation":
        goal_ids = [goal.goal_id for goal in self.goals]
        if len(goal_ids) != len(set(goal_ids)):
            raise ValueError("observation goal IDs must be unique")
        action_ids = [action.action_id for action in self.available_actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("observation action IDs must be unique")
        error_ids = [error.error_id for error in self.runtime_errors]
        if len(error_ids) != len(set(error_ids)):
            raise ValueError("observation runtime error IDs must be unique")
        return self


class FailureSignal(StrictModel):
    signal_id: StableId
    kind: FailureKind
    severity: Severity
    message: str = Field(min_length=1)
    detected_at: UtcDatetime
    step_indices: List[Annotated[int, Field(ge=0)]]
    target_sceneops_id: Optional[StableId] = None
    evidence_artifact_ids: List[StableId] = Field(default_factory=list)
    details: Dict[str, JsonScalar] = Field(default_factory=dict)
    producer_id: StableId
    producer_version: str = Field(min_length=1)


class EvidenceBundle(StrictModel):
    evidence_id: StableId
    run_id: RunId
    session_id: StableId
    execution_mode: ExecutionMode
    captured_at: UtcDatetime
    build_id: StableId
    scene_id: StableId
    step_indices: List[Annotated[int, Field(ge=0)]]
    camera: CameraEvidence
    trajectory: List[Pose] = Field(min_length=1)
    artifacts: List[ArtifactReference] = Field(default_factory=list)
    structured_log_ids: List[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "EvidenceBundle":
        if any(
            artifact.execution_mode != self.execution_mode
            for artifact in self.artifacts
        ):
            raise ValueError("evidence artifacts must use the bundle execution mode")
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("evidence artifact IDs must be unique")
        if len(self.structured_log_ids) != len(set(self.structured_log_ids)):
            raise ValueError("evidence structured log IDs must be unique")
        if len(self.step_indices) != len(set(self.step_indices)):
            raise ValueError("evidence step indices must be unique")
        screenshot_id = self.camera.screenshot_artifact_id
        if screenshot_id and screenshot_id not in artifact_ids:
            raise ValueError("camera screenshot must reference an evidence artifact")
        return self


class PlaytestStep(StrictModel):
    run_id: RunId
    step_index: Annotated[int, Field(ge=0)]
    started_at: UtcDatetime
    completed_at: UtcDatetime
    build_id: StableId
    scene_id: StableId
    observation: Observation
    post_observation: Observation
    selected_action: AvailableAction
    target_sceneops_id: Optional[StableId] = None
    result: ActionResult
    progress: List[GoalProgress]
    failure_signals: List[FailureSignal] = Field(default_factory=list)
    evidence: EvidenceBundle

    @model_validator(mode="after")
    def validate_step_identity(self) -> "PlaytestStep":
        if self.observation.build_id != self.build_id:
            raise ValueError("step and observation build_id must match")
        if self.observation.scene_id != self.scene_id:
            raise ValueError("step and observation scene_id must match")
        if self.post_observation.build_id != self.build_id:
            raise ValueError("step and post_observation build_id must match")
        if self.post_observation.scene_id != self.scene_id:
            raise ValueError("step and post_observation scene_id must match")
        if self.evidence.build_id != self.build_id:
            raise ValueError("step and evidence build_id must match")
        if self.evidence.scene_id != self.scene_id:
            raise ValueError("step and evidence scene_id must match")
        if self.evidence.run_id != self.run_id:
            raise ValueError("step and evidence run_id must match")
        if self.evidence.step_indices != [self.step_index]:
            raise ValueError("step evidence must identify exactly this step")
        if self.evidence.camera != self.post_observation.camera:
            raise ValueError("step evidence camera must match post_observation")
        if self.evidence.trajectory[-1] != self.post_observation.pose:
            raise ValueError("step evidence trajectory must end at the post-action pose")
        if self.selected_action.target_sceneops_id != self.target_sceneops_id:
            raise ValueError("step and selected action target_sceneops_id must match")
        advertised = next(
            (
                action
                for action in self.observation.available_actions
                if action.action_id == self.selected_action.action_id
            ),
            None,
        )
        if advertised is None or advertised != self.selected_action:
            raise ValueError("selected action must exactly match a pre-action advertisement")
        if self.progress != self.post_observation.goals:
            raise ValueError("step progress must equal post_observation goals")
        if (
            self.post_observation.telemetry_sequence
            <= self.observation.telemetry_sequence
        ):
            raise ValueError("post_observation telemetry must follow the pre-action observation")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self
