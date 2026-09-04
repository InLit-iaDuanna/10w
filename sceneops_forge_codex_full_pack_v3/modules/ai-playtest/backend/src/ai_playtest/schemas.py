from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from .step_schemas import (
    ActionKind,
    ActionOutcome,
    ActionResult,
    AgentMode,
    ArtifactReference,
    AvailableAction,
    BackpinStatus,
    BackpinTargetType,
    CameraEvidence,
    EvidenceBundle,
    ExecutionMode,
    FailureKind,
    FailureSignal,
    GoalProgress,
    GoalState,
    JsonScalar,
    MetricDirection,
    MetricOutcome,
    Observation,
    PlaytestStep,
    Pose,
    RegressionStatus,
    RunId,
    RuntimeErrorRecord,
    RunStatus,
    Severity,
    StableId,
    StrictModel,
    TestGoal,
    UtcDatetime,
    Vector3,
)


class SourceCandidate(StrictModel):
    source_record_id: StableId
    source_record_uri: str = Field(min_length=1)
    target_type: BackpinTargetType
    target_id: StableId
    sceneops_id: Optional[StableId] = None
    locator: str = Field(min_length=1)
    owning_module: StableId
    build_id: StableId
    component_id: Optional[StableId] = None
    related_sceneops_ids: List[StableId] = Field(default_factory=list)
    failure_kinds: List[FailureKind] = Field(default_factory=list)
    evidence_artifact_ids: List[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_record_reference(self) -> "SourceCandidate":
        if "#" not in self.source_record_uri:
            raise ValueError("source_record_uri must include a record fragment")
        _, fragment = self.source_record_uri.rsplit("#", 1)
        if fragment != self.source_record_id:
            raise ValueError("source_record_uri fragment must match source_record_id")
        return self


class SourceRecord(StrictModel):
    source_record_id: StableId
    project_id: StableId
    build_id: StableId
    source_version: str = Field(min_length=1)
    target_type: BackpinTargetType
    target_id: StableId
    sceneops_id: Optional[StableId] = None
    locator: str = Field(min_length=1)
    owning_module: StableId
    component_id: Optional[StableId] = None
    related_sceneops_ids: List[StableId] = Field(default_factory=list)


class SourceCatalog(StrictModel):
    schema_version: Literal[1]
    catalog_id: StableId
    records: Dict[StableId, SourceRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_record_keys(self) -> "SourceCatalog":
        if any(
            record_id != record.source_record_id
            for record_id, record in self.records.items()
        ):
            raise ValueError("source catalog keys must match source_record_id")
        return self


class Backpin(StrictModel):
    backpin_id: StableId
    source_record_id: Optional[StableId] = None
    source_record_uri: Optional[str] = None
    target_type: Optional[BackpinTargetType] = None
    target_id: Optional[StableId] = None
    sceneops_id: Optional[StableId] = None
    locator: Optional[str] = None
    owning_module: Optional[StableId] = None
    status: BackpinStatus
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence_ids: List[StableId] = Field(min_length=1)
    reasons: List[str] = Field(min_length=1)
    alternatives: List[StableId] = Field(default_factory=list)
    reviewed_by: Optional[StableId] = None
    reviewed_at: Optional[UtcDatetime] = None

    @model_validator(mode="after")
    def validate_review(self) -> "Backpin":
        if bool(self.reviewed_by) != bool(self.reviewed_at):
            raise ValueError("reviewed_by and reviewed_at must be recorded together")
        if self.status == BackpinStatus.REJECTED and not self.reviewed_by:
            raise ValueError("rejected backpins require a recorded reviewer")
        if self.status in {BackpinStatus.RESOLVED, BackpinStatus.AMBIGUOUS} and not all(
            (
                self.target_type,
                self.target_id,
                self.source_record_id,
                self.source_record_uri,
                self.locator,
                self.owning_module,
            )
        ):
            raise ValueError("resolved or ambiguous backpins require a source target")
        if self.status == BackpinStatus.AMBIGUOUS and not self.alternatives:
            raise ValueError("ambiguous backpins require at least one alternative")
        if self.status == BackpinStatus.UNRESOLVED and any(
            (
                self.target_type,
                self.target_id,
                self.source_record_id,
                self.source_record_uri,
                self.sceneops_id,
                self.locator,
                self.owning_module,
            )
        ):
            raise ValueError("unresolved backpins cannot claim a source target")
        if self.source_record_uri:
            _, separator, fragment = self.source_record_uri.rpartition("#")
            if not separator or fragment != self.source_record_id:
                raise ValueError(
                    "backpin source_record_uri fragment must match source_record_id"
                )
        return self


class RestorationContext(StrictModel):
    scene_id: StableId
    selected_sceneops_ids: List[StableId]
    camera: CameraEvidence
    trajectory: List[Pose] = Field(min_length=1)
    timeline_time_seconds: Annotated[float, Field(ge=0)]
    step_index: Optional[Annotated[int, Field(ge=0)]] = None


class Issue(StrictModel):
    issue_id: StableId
    run_id: RunId
    test_case_id: StableId
    title: str = Field(min_length=1)
    created_at: UtcDatetime
    execution_mode: ExecutionMode
    failure_signal: FailureSignal
    evidence: EvidenceBundle
    backpin: Backpin
    restoration: RestorationContext
    status: Literal["open", "triaged", "resolved", "closed"] = "open"
    limitation_labels: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_execution_truth(self) -> "Issue":
        if self.evidence.execution_mode != self.execution_mode:
            raise ValueError("issue evidence must match issue execution mode")
        if self.evidence.run_id != self.run_id:
            raise ValueError("issue evidence must match issue run_id")
        if self.evidence.scene_id != self.restoration.scene_id:
            raise ValueError("issue restoration must use the evidence scene")
        if self.evidence.camera != self.restoration.camera:
            raise ValueError("issue restoration camera must match evidence")
        if self.evidence.trajectory != self.restoration.trajectory:
            raise ValueError("issue restoration trajectory must match evidence")
        if self.evidence.step_indices:
            if self.restoration.step_index != self.evidence.step_indices[-1]:
                raise ValueError("issue restoration must identify its evidence step")
        elif self.restoration.step_index is not None:
            raise ValueError("terminal issue restoration cannot claim an action step")
        if self.evidence.evidence_id not in self.backpin.evidence_ids:
            raise ValueError("issue backpin must retain its evidence bundle identity")
        artifact_ids = {artifact.artifact_id for artifact in self.evidence.artifacts}
        if not set(self.failure_signal.evidence_artifact_ids).issubset(artifact_ids):
            raise ValueError("issue failure signal references evidence outside its bundle")
        if self.failure_signal.step_indices:
            if self.evidence.step_indices != [self.failure_signal.step_indices[-1]]:
                raise ValueError("issue evidence must capture the final implicated step")
        elif self.evidence.step_indices:
            raise ValueError("terminal issue signal cannot claim step evidence")
        return self


class RegressionMetricSpec(StrictModel):
    metric_id: StableId
    direction: MetricDirection
    tolerance: Annotated[float, Field(ge=0)] = 0
    unit: str = Field(min_length=1)


class MetricComparison(StrictModel):
    metric_id: StableId
    baseline: Optional[float]
    candidate: Optional[float]
    delta: Optional[float]
    direction: MetricDirection
    tolerance: float
    unit: str
    outcome: MetricOutcome


class PersonaHeuristic(StrictModel):
    label: str = Field(min_length=1)
    base_mode: Literal["smoke", "goal_driven", "explorer"]
    description: str = Field(min_length=1)


class TestControls(StrictModel):
    max_steps: Annotated[int, Field(ge=1, le=10000)]
    max_duration_ms: Annotated[int, Field(ge=1, le=86_400_000)]
    action_timeout_ms: Annotated[int, Field(ge=1, le=300_000)]
    allowed_action_kinds: List[ActionKind]
    registered_action_ids: List[StableId] = Field(default_factory=list)
    allow_destructive: bool = False
    destructive_sandbox_id: Optional[StableId] = None
    stall_steps: Annotated[int, Field(ge=2)] = 3
    repeated_failure_threshold: Annotated[int, Field(ge=2)] = 2
    pose_epsilon_m: Annotated[float, Field(gt=0)] = 0.05
    max_frame_time_ms: Optional[Annotated[float, Field(gt=0)]] = None
    max_memory_mb: Optional[Annotated[float, Field(gt=0)]] = None

    @model_validator(mode="after")
    def validate_destructive_containment(self) -> "TestControls":
        if self.allow_destructive and not self.destructive_sandbox_id:
            raise ValueError("destructive tests require destructive_sandbox_id")
        if len(self.allowed_action_kinds) != len(set(self.allowed_action_kinds)):
            raise ValueError("allowed action kinds must be unique")
        if len(self.registered_action_ids) != len(set(self.registered_action_ids)):
            raise ValueError("registered action IDs must be unique")
        return self


class TestCase(StrictModel):
    schema_version: Literal[1]
    test_case_id: StableId
    version: Annotated[int, Field(ge=1)]
    project_id: StableId
    name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    scene_id: StableId
    agent_mode: AgentMode
    seed: int
    goals: List[TestGoal]
    controls: TestControls
    regression_metrics: List[RegressionMetricSpec]
    persona: Optional[PersonaHeuristic] = None
    limitation_labels: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_agent_mode(self) -> "TestCase":
        if self.agent_mode == AgentMode.PERSONA and not self.persona:
            raise ValueError("persona mode requires a labelled heuristic")
        if self.agent_mode != AgentMode.PERSONA and self.persona:
            raise ValueError("persona is only valid for persona mode")
        if self.agent_mode == AgentMode.DESTRUCTIVE and not self.controls.allow_destructive:
            raise ValueError("destructive mode requires explicit destructive controls")
        goal_ids = [goal.goal_id for goal in self.goals]
        if not goal_ids or len(goal_ids) != len(set(goal_ids)):
            raise ValueError("TestCase goals must be non-empty and have unique IDs")
        metric_ids = [metric.metric_id for metric in self.regression_metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("regression metric IDs must be unique")
        return self


class BuildReference(StrictModel):
    build_id: StableId
    project_id: StableId
    version: str = Field(min_length=1)
    scene_id: StableId
    telemetry_contract_version: Literal[1]


class AdapterProvenance(StrictModel):
    adapter_id: StableId
    adapter_version: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    execution_mode: ExecutionMode


class MeasurementRecipeProvenance(StrictModel):
    metric_id: StableId
    implementation_id: StableId
    implementation_version: str = Field(min_length=1)
    parameters: Dict[str, JsonScalar] = Field(default_factory=dict)


class AdapterLog(StrictModel):
    log_id: StableId
    occurred_at: UtcDatetime
    level: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class PlaytestBehaviorProvenance(StrictModel):
    runner_version: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)


class RunFailure(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    suggested_actions: List[StableId] = Field(min_length=1)


class CancelRunResult(StrictModel):
    run_id: RunId
    accepted: bool
    status: Literal["cancel_requested", "not_running"]


class PlaytestRun(StrictModel):
    run_id: RunId
    test_case: TestCase
    build: BuildReference
    status: RunStatus
    execution_mode: ExecutionMode
    replay_action_ids: List[StableId] = Field(default_factory=list)
    started_at: UtcDatetime
    finished_at: Optional[UtcDatetime] = None
    steps: List[PlaytestStep] = Field(default_factory=list)
    final_goal_progress: List[GoalProgress] = Field(default_factory=list)
    terminal_signals: List[FailureSignal] = Field(default_factory=list)
    terminal_evidence: List[EvidenceBundle] = Field(default_factory=list)
    adapter_logs: List[AdapterLog] = Field(default_factory=list)
    issues: List[Issue] = Field(default_factory=list)
    measurements: Dict[str, float] = Field(default_factory=dict)
    adapter_provenance: AdapterProvenance
    measurement_recipes: List[MeasurementRecipeProvenance]
    behavior_provenance: PlaytestBehaviorProvenance
    limitation_labels: List[str] = Field(min_length=1)
    comparison_eligible: bool = False
    failure: Optional[RunFailure] = None
    blocked_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_execution_truth(self) -> "PlaytestRun":
        if self.test_case.project_id != self.build.project_id:
            raise ValueError("run TestCase and build project_id must match")
        if self.test_case.scene_id != self.build.scene_id:
            raise ValueError("run TestCase and build scene_id must match")
        if self.adapter_provenance.execution_mode != self.execution_mode:
            raise ValueError("adapter provenance must match run execution mode")
        if any(
            step.evidence.execution_mode != self.execution_mode
            for step in self.steps
        ):
            raise ValueError("step evidence must match run execution mode")
        if any(issue.execution_mode != self.execution_mode for issue in self.issues):
            raise ValueError("issues must match run execution mode")
        if any(
            step.run_id != self.run_id
            or step.build_id != self.build.build_id
            or step.scene_id != self.build.scene_id
            for step in self.steps
        ):
            raise ValueError("steps must match run, build, and scene identity")
        if any(
            evidence.run_id != self.run_id
            or evidence.build_id != self.build.build_id
            or evidence.scene_id != self.build.scene_id
            or evidence.execution_mode != self.execution_mode
            for evidence in self.terminal_evidence
        ):
            raise ValueError("terminal evidence must match run execution identity")
        if any(evidence.step_indices for evidence in self.terminal_evidence):
            raise ValueError("terminal evidence cannot claim an action step")
        if any(
            issue.run_id != self.run_id
            or issue.test_case_id != self.test_case.test_case_id
            for issue in self.issues
        ):
            raise ValueError("issues must match run and TestCase identity")
        evidence_by_id = {
            evidence.evidence_id: evidence
            for evidence in self.terminal_evidence
            + [step.evidence for step in self.steps]
        }
        if any(
            evidence_by_id.get(issue.evidence.evidence_id) != issue.evidence
            for issue in self.issues
        ):
            raise ValueError("issue evidence must be owned by this run")
        recipe_ids = [recipe.metric_id for recipe in self.measurement_recipes]
        if len(recipe_ids) != len(set(recipe_ids)):
            raise ValueError("measurement recipe metric IDs must be unique")
        declared_metric_ids = [
            metric.metric_id for metric in self.test_case.regression_metrics
        ]
        if recipe_ids != declared_metric_ids:
            raise ValueError("measurement recipes must match declared metrics in order")
        if not set(self.measurements).issubset(declared_metric_ids):
            raise ValueError("run measurements must be declared by the TestCase")
        if [step.step_index for step in self.steps] != list(range(len(self.steps))):
            raise ValueError("run step indices must be contiguous from zero")
        final_goal_ids = [goal.goal_id for goal in self.final_goal_progress]
        if len(final_goal_ids) != len(set(final_goal_ids)):
            raise ValueError("final goal progress IDs must be unique")
        if self.steps and self.final_goal_progress != self.steps[-1].progress:
            raise ValueError("final goal progress must match the final recorded step")
        if any(
            current.observation != previous.post_observation
            for previous, current in zip(self.steps, self.steps[1:])
        ):
            raise ValueError("each step must reuse the previous post observation")
        session_ids = {
            evidence.session_id
            for evidence in self.terminal_evidence
            + [step.evidence for step in self.steps]
        }
        if len(session_ids) > 1:
            raise ValueError("all run evidence must belong to one runtime session")
        issue_ids = [issue.issue_id for issue in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("run issue IDs must be unique")
        evidence_ids = list(evidence_by_id)
        expected_evidence_count = len(self.terminal_evidence) + len(self.steps)
        if len(evidence_ids) != expected_evidence_count:
            raise ValueError("run evidence IDs must be unique")
        log_ids = [log.log_id for log in self.adapter_logs]
        if len(log_ids) != len(set(log_ids)):
            raise ValueError("adapter log IDs must be unique")
        all_evidence = self.terminal_evidence + [
            step.evidence for step in self.steps
        ]
        if any(
            artifact.source_project_id != self.test_case.project_id
            or artifact.source_version != self.build.version
            for evidence in all_evidence
            for artifact in evidence.artifacts
        ):
            raise ValueError(
                "evidence artifacts must match the run project and build version"
            )
        if self.comparison_eligible and any(
            not set(evidence.structured_log_ids).issubset(log_ids)
            for evidence in all_evidence
        ):
            raise ValueError(
                "comparable run evidence can only reference owned adapter logs"
            )
        terminal_statuses = {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.BLOCKED,
        }
        if self.status in terminal_statuses and self.finished_at is None:
            raise ValueError("terminal runs require finished_at")
        if self.status not in terminal_statuses and self.finished_at is not None:
            raise ValueError("active runs cannot have finished_at")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        if self.status == RunStatus.FAILED and self.failure is None:
            raise ValueError("failed runs require a structured failure")
        if self.status != RunStatus.FAILED and self.failure is not None:
            raise ValueError("only failed runs can carry a structured failure")
        if self.status == RunStatus.BLOCKED and not self.blocked_reason:
            raise ValueError("blocked runs require blocked_reason")
        if self.status != RunStatus.BLOCKED and self.blocked_reason is not None:
            raise ValueError("only blocked runs can carry blocked_reason")
        if self.comparison_eligible and self.status not in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
        }:
            raise ValueError("only completed gameplay runs can be comparison eligible")
        if self.status == RunStatus.SUCCEEDED and not self.comparison_eligible:
            raise ValueError("succeeded runs must be comparison eligible")
        if self.status == RunStatus.SUCCEEDED:
            progress = {
                goal.goal_id: goal.state for goal in self.final_goal_progress
            }
            if any(
                progress.get(goal.goal_id) != GoalState.COMPLETED
                for goal in self.test_case.goals
            ):
                raise ValueError("succeeded runs require every TestCase goal to complete")
            all_signals = self.terminal_signals + [
                signal for step in self.steps for signal in step.failure_signals
            ]
            if any(signal.severity == Severity.CRITICAL for signal in all_signals):
                raise ValueError("succeeded runs cannot contain critical failure signals")
        return self


class RegressionComparison(StrictModel):
    comparison_id: StableId
    test_case_id: StableId
    baseline_run_id: RunId
    candidate_run_id: RunId
    baseline_build_id: StableId
    candidate_build_id: StableId
    exact_configuration: Literal[True] = True
    status: RegressionStatus
    metrics: List[MetricComparison]
    new_issue_ids: List[StableId]
    resolved_issue_ids: List[StableId]
    persistent_issue_ids: List[StableId]
    execution_mode: ExecutionMode
    compared_at: UtcDatetime
    limitation_labels: List[str] = Field(min_length=1)


class ChangeSetProposal(StrictModel):
    proposal_id: StableId
    command_id: Literal["changeset.propose"] = "changeset.propose"
    owning_module: StableId
    base_version: str = Field(min_length=1)
    target_integration: str = Field(min_length=1)
    target_object_ids: List[StableId] = Field(min_length=1)
    previous_values: Dict[str, JsonScalar]
    proposed_values: Dict[str, JsonScalar]
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: str = Field(min_length=1)
    risk: Literal["low", "medium", "high", "critical"]
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    approval_requirements: List[str] = Field(min_length=1)
    execution_mode: Literal[ExecutionMode.PLANNED] = ExecutionMode.PLANNED
    source_issue_id: StableId

    @model_validator(mode="after")
    def validate_proposal(self) -> "ChangeSetProposal":
        if len(self.target_object_ids) != len(set(self.target_object_ids)):
            raise ValueError("ChangeSet target object IDs must be unique")
        if self.previous_values == self.proposed_values:
            raise ValueError("ChangeSet proposal must describe an actual value change")
        return self


class RunRequest(StrictModel):
    run_id: RunId
    test_case: TestCase
    build: BuildReference
    execution_mode: ExecutionMode
    replay_action_ids: List[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_runnable_mode(self) -> "RunRequest":
        if self.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.CACHED,
            ExecutionMode.MOCK,
        }:
            raise ValueError("run execution_mode must be live, cached, or mock")
        if self.test_case.project_id != self.build.project_id:
            raise ValueError("RunRequest TestCase and build project_id must match")
        if self.test_case.scene_id != self.build.scene_id:
            raise ValueError("RunRequest TestCase and build scene_id must match")
        return self
