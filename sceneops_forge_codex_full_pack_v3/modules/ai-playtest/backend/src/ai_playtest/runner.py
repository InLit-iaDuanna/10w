from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from .adapter_contract import (
    preflight_adapter,
    read_observation,
    select_measurement_recipes,
    validate_evidence,
)
from .backpin import BackpinResolver
from .detectors import FailureDetector
from .goal_scope import expected_goal_ids, goals_completed
from .issue_builder import create_issues, create_terminal_issues
from .observation_detection import detect_observation_failures
from .ports import (
    AdapterError,
    BuildMismatchError,
    CancellationToken,
    ExecutionTruthError,
    PlaytestRunnerAdapter,
    RuntimeSession,
)
from .policy import DeterministicActionPolicy
from .schemas import (
    ActionOutcome,
    AvailableAction,
    ExecutionMode,
    FailureSignal,
    Observation,
    PlaytestRun,
    PlaytestBehaviorProvenance,
    PlaytestStep,
    RunFailure,
    RunRequest,
    RunStatus,
    Severity,
)
from .terminal_signals import (
    duration_failure,
    duration_timeout_signal,
    detected_run_failure,
    max_steps_signal,
    telemetry_recovery_signal,
    terminal_telemetry_recovery_signal,
)


Clock = Callable[[], datetime]
MonotonicMilliseconds = Callable[[], float]
StepListener = Callable[[PlaytestStep], None]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def monotonic_ms() -> float:
    return time.monotonic() * 1000


class AIPlaytestRunner:
    version = "1.1.0"

    def __init__(
        self,
        adapter: PlaytestRunnerAdapter,
        detector: Optional[FailureDetector] = None,
        backpin_resolver: Optional[BackpinResolver] = None,
        clock: Clock = utc_now,
        monotonic_clock: MonotonicMilliseconds = monotonic_ms,
    ):
        self.adapter = adapter
        self.detector = detector or FailureDetector()
        self.backpin_resolver = backpin_resolver or BackpinResolver()
        self.clock = clock
        self.monotonic_clock = monotonic_clock

    def run(
        self,
        request: RunRequest,
        cancellation: Optional[CancellationToken] = None,
        on_step: Optional[StepListener] = None,
    ) -> PlaytestRun:
        token = cancellation or CancellationToken()
        capabilities = preflight_adapter(self.adapter, request)
        measurement_recipes = select_measurement_recipes(request, capabilities)
        session = self.adapter.reset(
            request.test_case,
            request.build,
            request.execution_mode,
            request.run_id,
        )
        if session.build != request.build:
            raise BuildMismatchError("adapter reset returned a different build")
        if session.execution_mode != request.execution_mode:
            raise ExecutionTruthError("adapter session contradicts requested execution mode")
        if session.run_id != request.run_id:
            raise ExecutionTruthError("adapter session contradicts requested run identity")
        policy = DeterministicActionPolicy(
            request.test_case, request.replay_action_ids
        )
        run = PlaytestRun(
            run_id=request.run_id,
            test_case=request.test_case,
            build=request.build,
            status=RunStatus.RUNNING,
            execution_mode=request.execution_mode,
            replay_action_ids=list(request.replay_action_ids),
            started_at=self.clock(),
            adapter_provenance=capabilities.provenance,
            measurement_recipes=measurement_recipes,
            behavior_provenance=PlaytestBehaviorProvenance(
                runner_version=self.version,
                detector_version=self.detector.version,
                policy_version=policy.version,
                workflow_version="playtest-regression.v1",
            ),
            limitation_labels=self._limitations(request),
        )
        started_ms = self.monotonic_clock()
        execution_error: Optional[AdapterError] = None
        try:
            self._execute_steps(run, session, policy, token, started_ms, on_step)
        except AdapterError as error:
            execution_error = error
        collection_error = self._collect_adapter_outputs(run, session)
        failure_error = execution_error or collection_error
        if failure_error:
            return self._failed_adapter_run(run, failure_error)
        run.status = self._finish_status(run, token)
        if run.status == RunStatus.FAILED and run.failure is None:
            run.failure = detected_run_failure(run)
        run.comparison_eligible = run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
        }
        run.finished_at = self.clock()
        return self._validated_run(run)

    def _collect_adapter_outputs(
        self, run: PlaytestRun, session: RuntimeSession
    ) -> Optional[AdapterError]:
        first_error: Optional[AdapterError] = None
        try:
            declared = {recipe.metric_id for recipe in run.measurement_recipes}
            run.measurements = {
                metric_id: value
                for metric_id, value in self.adapter.measurements(session).items()
                if metric_id in declared
            }
        except AdapterError as error:
            first_error = error
        try:
            run.adapter_logs = self.adapter.logs(session)
        except AdapterError as error:
            first_error = first_error or error
        return first_error

    def _failed_adapter_run(
        self, run: PlaytestRun, error: AdapterError
    ) -> PlaytestRun:
        run.status = RunStatus.FAILED
        run.finished_at = self.clock()
        run.failure = RunFailure(
            code=error.code,
            message=str(error),
            retryable=error.retryable,
            suggested_actions=["playtest.run"],
        )
        return self._validated_run(run)

    def _execute_steps(
        self,
        run: PlaytestRun,
        session: RuntimeSession,
        policy: DeterministicActionPolicy,
        token: CancellationToken,
        started_ms: float,
        on_step: Optional[StepListener],
    ) -> None:
        controls = run.test_case.controls
        goal_ids = expected_goal_ids(run.test_case)
        last_sequence = -1
        observation: Optional[Observation] = None
        observation_telemetry_lost = False
        for step_index in range(controls.max_steps):
            if token.cancelled:
                self.adapter.cancel(session)
                return
            if self.monotonic_clock() - started_ms >= controls.max_duration_ms:
                self._record_duration_timeout(run, session)
                return
            if observation is None:
                observation, observation_telemetry_lost = read_observation(
                    self.adapter, session, run, last_sequence
                )
                last_sequence = observation.telemetry_sequence
            run.final_goal_progress = observation.goals
            permitted_actions = policy.permitted_actions(observation)
            if step_index == 0:
                initial_signals = detect_observation_failures(
                    run.run_id,
                    observation,
                    controls,
                    goal_ids,
                    permitted_actions,
                    observation.observed_at,
                    [],
                    producer_version=self.detector.version,
                )
                should_stop = (
                    goals_completed(observation.goals, goal_ids)
                    or not permitted_actions
                    or any(
                        signal.severity == Severity.CRITICAL
                        for signal in initial_signals
                    )
                )
                if should_stop and observation_telemetry_lost:
                    initial_signals.append(
                        terminal_telemetry_recovery_signal(
                            run, observation.observed_at
                        )
                    )
                if initial_signals:
                    self._record_terminal_signals(
                        run, session, initial_signals, observation.observed_at
                    )
                if should_stop:
                    if not initial_signals:
                        self._record_terminal_checkpoint(run, session)
                    return
            remaining_ms = int(
                controls.max_duration_ms
                - (self.monotonic_clock() - started_ms)
            )
            if remaining_ms <= 0:
                self._record_duration_timeout(run, session)
                return
            step_timeout_ms = min(controls.action_timeout_ms, remaining_ms)
            action = policy.select(observation, step_index)
            step, post_telemetry_lost = self._execute_step(
                run,
                session,
                observation,
                action,
                step_index,
                token,
                last_sequence,
                step_timeout_ms,
            )
            last_sequence = step.post_observation.telemetry_sequence
            run.final_goal_progress = step.progress
            permitted_post_actions = policy.permitted_actions(
                step.post_observation
            )
            signals = self.detector.evaluate(
                step,
                run.steps,
                controls,
                goal_ids,
                permitted_post_actions,
            )
            if observation_telemetry_lost or post_telemetry_lost:
                signals.append(telemetry_recovery_signal(step))
            duration_exceeded = (
                self.monotonic_clock() - started_ms >= controls.max_duration_ms
                or (
                    step_timeout_ms < controls.action_timeout_ms
                    and step.result.outcome == ActionOutcome.TIMED_OUT
                )
            )
            if duration_exceeded:
                signals.append(
                    duration_timeout_signal(run, step.step_index, self.clock())
                )
                run.failure = duration_failure(controls.max_duration_ms)
            objective_complete = goals_completed(step.progress, goal_ids)
            if step_index == controls.max_steps - 1 and not objective_complete:
                signals.append(max_steps_signal(run, step))
            step = step.model_copy(update={"failure_signals": signals})
            run.steps.append(step)
            self._create_issues(run, session, step)
            observation = step.post_observation
            observation_telemetry_lost = False
            if on_step:
                on_step(step.model_copy(deep=True))
            if token.cancelled:
                self.adapter.cancel(session)
                return
            if (
                duration_exceeded
                or objective_complete
                or any(signal.severity == Severity.CRITICAL for signal in signals)
            ):
                return

    def _execute_step(
        self,
        run: PlaytestRun,
        session: RuntimeSession,
        observation: Observation,
        action: AvailableAction,
        step_index: int,
        token: CancellationToken,
        last_sequence: int,
        action_timeout_ms: int,
    ) -> Tuple[PlaytestStep, bool]:
        started_at = self.clock()
        result = self.adapter.execute_action(
            session,
            action,
            action_timeout_ms,
            token,
        )
        post_observation, telemetry_lost = read_observation(
            self.adapter, session, run, last_sequence
        )
        progress = post_observation.goals
        evidence = self.adapter.capture_evidence(session, step_index)
        validate_evidence(run, session, evidence)
        step = PlaytestStep(
            run_id=run.run_id,
            step_index=step_index,
            started_at=started_at,
            completed_at=self.clock(),
            build_id=run.build.build_id,
            scene_id=run.build.scene_id,
            observation=observation,
            post_observation=post_observation,
            selected_action=action,
            target_sceneops_id=action.target_sceneops_id,
            result=result,
            progress=progress,
            evidence=evidence,
        )
        return step, telemetry_lost

    def _create_issues(
        self, run: PlaytestRun, session: RuntimeSession, step: PlaytestStep
    ) -> None:
        create_issues(
            run, session, step, self.adapter, self.backpin_resolver
        )

    def _record_terminal_signals(
        self,
        run: PlaytestRun,
        session: RuntimeSession,
        signals: List[FailureSignal],
        observed_at: datetime,
    ) -> None:
        evidence = self.adapter.capture_evidence(session, None)
        validate_evidence(run, session, evidence)
        artifact_ids = [artifact.artifact_id for artifact in evidence.artifacts]
        enriched = [
            signal.model_copy(
                update={
                    "evidence_artifact_ids": list(
                        dict.fromkeys(
                            signal.evidence_artifact_ids + artifact_ids
                        )
                    )
                }
            )
            for signal in signals
        ]
        run.terminal_signals.extend(enriched)
        run.terminal_evidence.append(evidence)
        create_terminal_issues(
            run,
            session,
            enriched,
            evidence,
            observed_at,
            self.adapter,
            self.backpin_resolver,
        )

    def _record_terminal_checkpoint(
        self, run: PlaytestRun, session: RuntimeSession
    ) -> None:
        evidence = self.adapter.capture_evidence(session, None)
        validate_evidence(run, session, evidence)
        run.terminal_evidence.append(evidence)

    def _record_duration_timeout(
        self,
        run: PlaytestRun,
        session: RuntimeSession,
    ) -> None:
        run.failure = duration_failure(run.test_case.controls.max_duration_ms)
        signal = duration_timeout_signal(
            run,
            None,
            self.clock(),
        )
        self._record_terminal_signals(
            run, session, [signal], signal.detected_at
        )

    @staticmethod
    def _finish_status(run: PlaytestRun, token: CancellationToken) -> RunStatus:
        if run.failure:
            return RunStatus.FAILED
        signals = run.terminal_signals + [
            signal for step in run.steps for signal in step.failure_signals
        ]
        if any(signal.severity == Severity.CRITICAL for signal in signals):
            return RunStatus.FAILED
        if token.cancelled:
            return RunStatus.CANCELLED
        if goals_completed(
            run.final_goal_progress, expected_goal_ids(run.test_case)
        ):
            return RunStatus.SUCCEEDED
        return RunStatus.FAILED

    @staticmethod
    def _limitations(request: RunRequest) -> List[str]:
        labels = list(request.test_case.limitation_labels)
        if request.test_case.agent_mode.value == "persona":
            labels.append("Persona 是动作选择启发式，不代表真实人群。")
        labels.append("AI Playtest 仅用于预筛和回归，不能替代真人测试。")
        if request.execution_mode == ExecutionMode.MOCK:
            labels.append("本次为确定性 Mock，不是 Unity Live 执行。")
        return list(dict.fromkeys(labels))

    @staticmethod
    def _validated_run(run: PlaytestRun) -> PlaytestRun:
        return PlaytestRun.model_validate(run.model_dump(mode="python"))
