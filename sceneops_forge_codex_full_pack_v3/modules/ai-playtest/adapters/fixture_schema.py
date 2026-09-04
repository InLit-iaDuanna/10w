from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import Field, model_validator

from ai_playtest.schemas import (
    ActionKind,
    ActionResult,
    AvailableAction,
    BuildReference,
    GoalProgress,
    JsonScalar,
    RuntimeErrorRecord,
    SourceCandidate,
    StableId,
    StrictModel,
    UtcDatetime,
)


class MetricRule(StrictModel):
    source: Literal[
        "goal_value",
        "action_count",
        "failed_action_count",
        "max_observation",
    ]
    goal_id: Optional[StableId] = None
    action_kind: Optional[ActionKind] = None
    error_code_prefix: Optional[str] = None
    observation_field: Optional[Literal["frame_time_ms", "memory_mb"]] = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "MetricRule":
        if self.source == "goal_value" and not self.goal_id:
            raise ValueError("goal_value metric requires goal_id")
        if self.source == "max_observation" and not self.observation_field:
            raise ValueError("max_observation metric requires observation_field")
        allowed_fields = {
            "goal_value": {"goal_id"},
            "action_count": {"action_kind"},
            "failed_action_count": {"action_kind", "error_code_prefix"},
            "max_observation": {"observation_field"},
        }[self.source]
        configured_fields = {
            name
            for name in (
                "goal_id",
                "action_kind",
                "error_code_prefix",
                "observation_field",
            )
            if getattr(self, name) is not None
        }
        if not configured_fields.issubset(allowed_fields):
            raise ValueError(f"{self.source} metric has unrelated parameters")
        return self


class FixtureAdapterMetadata(StrictModel):
    adapter_id: StableId
    adapter_version: str = Field(min_length=1)
    max_steps: int = Field(default=200, ge=1)
    supports_destructive_containment: bool = False


class RuntimeFixtureFrame(StrictModel):
    observed_at: UtcDatetime
    position_m: Tuple[float, float, float]
    rotation_euler_deg: Tuple[float, float, float] = (0, 0, 0)
    frame_time_ms: float = Field(ge=0)
    memory_mb: Optional[float] = Field(default=None, ge=0)
    game_state: Dict[str, JsonScalar] = Field(default_factory=dict)
    goals: List[GoalProgress]
    actions: List[AvailableAction]
    results: Dict[str, ActionResult]
    next_frame: Dict[str, int]
    runtime_errors: List[RuntimeErrorRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_frame_collections(self) -> "RuntimeFixtureFrame":
        goal_ids = [goal.goal_id for goal in self.goals]
        if len(goal_ids) != len(set(goal_ids)):
            raise ValueError("fixture frame goal IDs must be unique")
        action_id_list = [action.action_id for action in self.actions]
        action_ids = set(action_id_list)
        if len(action_id_list) != len(action_ids):
            raise ValueError("fixture frame action IDs must be unique")
        error_ids = [error.error_id for error in self.runtime_errors]
        if len(error_ids) != len(set(error_ids)):
            raise ValueError("fixture frame runtime error IDs must be unique")
        if set(self.results) != action_ids or set(self.next_frame) != action_ids:
            raise ValueError("each advertised action requires one result and next_frame")
        return self


class DeterministicRuntimeFixture(StrictModel):
    schema_version: Literal[1]
    checked_at: UtcDatetime
    adapter: FixtureAdapterMetadata
    build: BuildReference
    actor_sceneops_id: StableId
    available: bool = True
    health_detail: str = "deterministic fixture ready"
    telemetry_recoverable: bool = True
    telemetry_loss_on_reads: List[int] = Field(default_factory=list)
    frames: List[RuntimeFixtureFrame] = Field(min_length=1)
    source_candidates: List[SourceCandidate] = Field(default_factory=list)
    metric_rules: Dict[StableId, MetricRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fixture_graph(self) -> "DeterministicRuntimeFixture":
        frame_count = len(self.frames)
        for frame in self.frames:
            if any(index < 0 or index >= frame_count for index in frame.next_frame.values()):
                raise ValueError("next_frame points outside fixture frames")
        for candidate in self.source_candidates:
            if candidate.build_id != self.build.build_id:
                raise ValueError("source candidate build_id must match fixture build")
        for metric_id, rule in self.metric_rules.items():
            if rule.source == "goal_value" and not any(
                any(goal.goal_id == rule.goal_id for goal in frame.goals)
                for frame in self.frames
            ):
                raise ValueError(f"metric {metric_id} references an unknown goal")
            if rule.source == "max_observation" and not any(
                getattr(frame, rule.observation_field) is not None
                for frame in self.frames
            ):
                raise ValueError(
                    f"metric {metric_id} has no observation values"
                )
        return self
