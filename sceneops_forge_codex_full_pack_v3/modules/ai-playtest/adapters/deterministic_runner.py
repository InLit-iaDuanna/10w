from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ai_playtest.ports import (
    ActionRejectedError,
    AdapterCapabilities,
    AdapterHealth,
    AdapterLog,
    BuildMismatchError,
    CancellationToken,
    DryRunResult,
    RetryPolicy,
    RuntimeSession,
    TelemetryLossError,
    UnsupportedExecutionModeError,
)
from ai_playtest.schemas import (
    ActionKind,
    ActionOutcome,
    ActionResult,
    AdapterProvenance,
    ArtifactReference,
    AvailableAction,
    BuildReference,
    CameraEvidence,
    EvidenceBundle,
    ExecutionMode,
    GoalProgress,
    MeasurementRecipeProvenance,
    Observation,
    Pose,
    SourceCandidate,
    TestCase,
    Vector3,
)
from .fixture_schema import DeterministicRuntimeFixture, MetricRule


class DeterministicPlaytestRunnerAdapter:
    """A fixture-backed adapter that never claims to be live."""

    def __init__(self, fixture: dict):
        validated = DeterministicRuntimeFixture.model_validate(deepcopy(fixture))
        self.fixture_model = validated
        self.fixture = validated.model_dump(mode="json")
        self.build = BuildReference.model_validate(self.fixture["build"])
        self._frame_index = 0
        self._visited_frames: List[int] = []
        self._observation_reads = 0
        self._evidence_captures = 0
        self._lost_reads = set()
        self._cancelled = False
        self._logs: List[AdapterLog] = []
        self._executed_actions: List[tuple[AvailableAction, ActionResult]] = []
        self._run_id = "run.unbound"
        self._session_id = "session.unbound"

    @classmethod
    def from_file(cls, path: Path) -> "DeterministicPlaytestRunnerAdapter":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def health_check(self) -> AdapterHealth:
        return AdapterHealth(
            available=bool(self.fixture.get("available", True)),
            checked_at=self.fixture["checked_at"],
            detail=self.fixture.get("health_detail", "deterministic fixture ready"),
        )

    def capabilities(self) -> AdapterCapabilities:
        adapter = self.fixture["adapter"]
        return AdapterCapabilities(
            adapter_id=adapter["adapter_id"],
            adapter_version=adapter["adapter_version"],
            supported_modes=[ExecutionMode.MOCK],
            supported_action_kinds=list(ActionKind),
            telemetry_contract_versions=[1],
            supports_cancellation=True,
            supports_telemetry_recovery=True,
            supports_destructive_containment=adapter.get(
                "supports_destructive_containment", False
            ),
            max_steps=adapter.get("max_steps", 200),
            retry_policy=RetryPolicy(
                max_attempts=2,
                retryable_error_codes=["TELEMETRY_LOSS"],
                action_retry=False,
            ),
            measurement_recipes=[
                MeasurementRecipeProvenance(
                    metric_id=metric_id,
                    implementation_id=f"ai-playtest.fixture.{rule.source}",
                    implementation_version="1.0.0",
                    parameters=rule.model_dump(mode="json", exclude_none=True),
                )
                for metric_id, rule in sorted(
                    self.fixture_model.metric_rules.items()
                )
            ],
            provenance=AdapterProvenance(
                adapter_id=adapter["adapter_id"],
                adapter_version=adapter["adapter_version"],
                tool_name="SceneOps deterministic playtest fixture",
                tool_version=adapter["adapter_version"],
                execution_mode=ExecutionMode.MOCK,
            ),
        )

    def dry_run(
        self, test_case: TestCase, build: BuildReference, mode: ExecutionMode
    ) -> DryRunResult:
        if mode != ExecutionMode.MOCK:
            return DryRunResult(
                accepted=False,
                execution_mode=mode,
                build=build,
                notices=["fixture adapter supports mock only"],
                blocked_reason="requested execution mode is not available",
                error_code=UnsupportedExecutionModeError.code,
            )
        accepted = build == self.build and test_case.project_id == build.project_id
        return DryRunResult(
            accepted=accepted,
            execution_mode=mode,
            build=build,
            notices=["确定性 Mock；不代表 Unity Live。"],
            blocked_reason=None if accepted else "fixture build or project mismatch",
            error_code=None if accepted else BuildMismatchError.code,
        )

    def reset(
        self,
        test_case: TestCase,
        build: BuildReference,
        mode: ExecutionMode,
        run_id: str,
    ) -> RuntimeSession:
        if mode != ExecutionMode.MOCK:
            raise UnsupportedExecutionModeError("fixture adapter supports mock only")
        if build != self.build or test_case.project_id != build.project_id:
            raise BuildMismatchError("fixture does not describe the requested build")
        self._frame_index = 0
        self._visited_frames = []
        self._observation_reads = 0
        self._evidence_captures = 0
        self._lost_reads.clear()
        self._cancelled = False
        self._logs.clear()
        self._executed_actions.clear()
        self._run_id = run_id
        self._session_id = f"session.{run_id}"
        return RuntimeSession(
            session_id=self._session_id,
            run_id=run_id,
            build=build,
            execution_mode=mode,
        )

    def get_observation(self, _: RuntimeSession) -> Observation:
        read_index = self._observation_reads
        self._observation_reads += 1
        loss_reads = set(self.fixture.get("telemetry_loss_on_reads", []))
        if read_index in loss_reads and read_index not in self._lost_reads:
            self._lost_reads.add(read_index)
            raise TelemetryLossError(max(-1, read_index - 1))
        observation = self._observation().model_copy(
            update={"telemetry_sequence": read_index}
        )
        self._visited_frames.append(self._frame_index)
        return observation

    def recover_telemetry(
        self, _: RuntimeSession, after_sequence: int
    ) -> Observation:
        if not self.fixture.get("telemetry_recoverable", True):
            raise TelemetryLossError(after_sequence)
        self._append_log("warning", "TELEMETRY_RECOVERED", "fixture telemetry restored")
        observation = self._observation().model_copy(
            update={"telemetry_sequence": self._observation_reads - 1}
        )
        self._visited_frames.append(self._frame_index)
        return observation

    def get_available_actions(self, _: RuntimeSession) -> List[AvailableAction]:
        return [AvailableAction.model_validate(item) for item in self._frame()["actions"]]

    def execute_action(
        self,
        _: RuntimeSession,
        action: AvailableAction,
        timeout_ms: int,
        cancellation: CancellationToken,
    ) -> ActionResult:
        if cancellation.cancelled or self._cancelled:
            return ActionResult(
                outcome=ActionOutcome.CANCELLED,
                detail="cancelled before fixture action",
                duration_ms=0,
            )
        actions = {
            AvailableAction.model_validate(item).action_id
            for item in self._frame()["actions"]
        }
        if action.action_id not in actions:
            raise ActionRejectedError("action is not advertised by current fixture frame")
        frame = self._frame()
        result = ActionResult.model_validate(frame["results"][action.action_id])
        if result.duration_ms > timeout_ms:
            result = ActionResult(
                outcome=ActionOutcome.TIMED_OUT,
                detail="fixture action exceeded TestCase timeout",
                error_code="ACTION_TIMEOUT",
                duration_ms=timeout_ms,
            )
        else:
            self._frame_index = frame["next_frame"][action.action_id]
        self._executed_actions.append((action, result))
        self._append_log("info", "ACTION_EXECUTED", action.action_id)
        return result

    def get_game_state(self, _: RuntimeSession) -> dict:
        return dict(self._frame().get("game_state", {}))

    def get_goal_progress(self, _: RuntimeSession) -> List[GoalProgress]:
        return [GoalProgress.model_validate(item) for item in self._frame()["goals"]]

    def capture_evidence(
        self, session: RuntimeSession, step_index: Optional[int]
    ) -> EvidenceBundle:
        capture_index = self._evidence_captures
        self._evidence_captures += 1
        observation = self._observation()
        screenshot_id = observation.camera.screenshot_artifact_id
        artifacts = []
        related_sceneops_ids = [
            self.fixture["actor_sceneops_id"],
            self._last_action_target(),
            *[
                item["target_sceneops_id"]
                for item in self._frame()["actions"]
                if item.get("target_sceneops_id")
            ],
        ]
        if screenshot_id:
            artifacts.append(
                ArtifactReference(
                    artifact_id=screenshot_id,
                    artifact_type="game_view_screenshot",
                    execution_mode=ExecutionMode.MOCK,
                    uri=f"fixture://{self._run_id}/frame/{self._frame_index}",
                    source_project_id=self.build.project_id,
                    source_version=self.build.version,
                    related_sceneops_ids=[
                        identifier
                        for identifier in dict.fromkeys(related_sceneops_ids)
                        if identifier is not None
                    ],
                    producing_module="ai-playtest",
                    tool_name="SceneOps deterministic playtest fixture",
                    tool_version=self.fixture["adapter"]["adapter_version"],
                    workflow_version="deterministic-runtime-fixture.v1",
                    creator_id="agent.deterministic-playtest",
                    created_at=observation.observed_at,
                    approval_state="unreviewed",
                )
            )
        return EvidenceBundle(
            evidence_id=f"evidence.{self._run_id}.{capture_index}",
            run_id=self._run_id,
            session_id=session.session_id,
            execution_mode=ExecutionMode.MOCK,
            captured_at=observation.observed_at,
            build_id=self.build.build_id,
            scene_id=self.build.scene_id,
            step_indices=[] if step_index is None else [step_index],
            camera=observation.camera,
            trajectory=(
                [
                    self._pose(self.fixture["frames"][index])
                    for index in self._visited_frames
                ]
                or [self._pose(self._frame())]
            ),
            artifacts=artifacts,
            structured_log_ids=[log.log_id for log in self._logs],
        )

    def source_candidates(
        self, _: RuntimeSession, target_sceneops_id: Optional[str]
    ) -> List[SourceCandidate]:
        candidates = [
            SourceCandidate.model_validate(item)
            for item in self.fixture.get("source_candidates", [])
        ]
        if not target_sceneops_id:
            return candidates
        return [
            candidate
            for candidate in candidates
            if candidate.sceneops_id == target_sceneops_id
            or target_sceneops_id in candidate.related_sceneops_ids
        ]

    def logs(self, _: RuntimeSession) -> List[AdapterLog]:
        return [log.model_copy(deep=True) for log in self._logs]

    def measurements(self, _: RuntimeSession) -> dict:
        measurements = {}
        for metric_id, rule in self.fixture_model.metric_rules.items():
            value = self._measure(rule)
            if value is not None:
                measurements[metric_id] = value
        return measurements

    def cancel(self, _: RuntimeSession) -> None:
        self._cancelled = True
        self._append_log("warning", "RUN_CANCELLED", "fixture run cancelled")

    def _observation(self) -> Observation:
        frame = self._frame()
        return Observation(
            observed_at=frame["observed_at"],
            telemetry_sequence=max(0, self._observation_reads - 1),
            build_id=self.build.build_id,
            scene_id=self.build.scene_id,
            actor_sceneops_id=self.fixture["actor_sceneops_id"],
            pose=self._pose(frame),
            camera=CameraEvidence(
                camera_id="camera.game",
                pose=self._pose(frame),
                field_of_view_deg=60,
                screenshot_artifact_id=(
                    f"artifact.screenshot.{self._run_id}.{self._frame_index}"
                ),
            ),
            game_state=frame.get("game_state", {}),
            goals=frame["goals"],
            available_actions=frame["actions"],
            runtime_errors=frame.get("runtime_errors", []),
            frame_time_ms=frame["frame_time_ms"],
            memory_mb=frame.get("memory_mb"),
        )

    @staticmethod
    def _pose(frame: dict) -> Pose:
        position = frame["position_m"]
        rotation = frame.get("rotation_euler_deg", [0, 0, 0])
        return Pose(
            position=Vector3(x=position[0], y=position[1], z=position[2]),
            rotation_euler_deg=Vector3(x=rotation[0], y=rotation[1], z=rotation[2]),
        )

    def _frame(self) -> Dict[str, object]:
        return self.fixture["frames"][self._frame_index]

    def _last_action_target(self) -> Optional[str]:
        if not self._executed_actions:
            return None
        return self._executed_actions[-1][0].target_sceneops_id

    def _append_log(self, level: str, code: str, message: str) -> None:
        self._logs.append(
            AdapterLog(
                log_id=f"log.{self._run_id}.{len(self._logs)}",
                occurred_at=datetime.fromisoformat(
                    self._frame()["observed_at"].replace("Z", "+00:00")
                ),
                level=level,
                code=code,
                message=message,
            )
        )

    def _measure(self, rule: MetricRule) -> Optional[float]:
        if rule.source == "goal_value":
            if not self._visited_frames:
                return None
            goals = {
                goal.goal_id: goal
                for goal in (
                    GoalProgress.model_validate(item)
                    for item in self.fixture["frames"][self._visited_frames[-1]]["goals"]
                )
            }
            return goals[rule.goal_id].value if rule.goal_id in goals else None
        if rule.source == "action_count":
            return float(
                sum(
                    1
                    for action, _ in self._executed_actions
                    if rule.action_kind is None or action.kind == rule.action_kind
                )
            )
        if rule.source == "failed_action_count":
            return float(
                sum(
                    1
                    for action, result in self._executed_actions
                    if result.outcome == ActionOutcome.FAILED
                    and (rule.action_kind is None or action.kind == rule.action_kind)
                    and (
                        rule.error_code_prefix is None
                        or (result.error_code or "").startswith(rule.error_code_prefix)
                    )
                )
            )
        values = [
            self.fixture["frames"][index].get(rule.observation_field)
            for index in self._visited_frames
        ]
        observed_values = [value for value in values if value is not None]
        return float(max(observed_values)) if observed_values else None
