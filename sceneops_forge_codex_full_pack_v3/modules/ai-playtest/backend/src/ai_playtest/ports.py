from __future__ import annotations

from typing import List, Optional, Protocol

from pydantic import Field, model_validator

from .schemas import (
    ActionKind,
    ActionResult,
    AdapterLog,
    AdapterProvenance,
    AvailableAction,
    BuildReference,
    EvidenceBundle,
    ExecutionMode,
    GoalProgress,
    MeasurementRecipeProvenance,
    Observation,
    RunId,
    SourceCandidate,
    StableId,
    StrictModel,
    TestCase,
    UtcDatetime,
)


class AdapterError(RuntimeError):
    code = "PLAYTEST_ADAPTER_ERROR"
    retryable = False


class AdapterOfflineError(AdapterError):
    code = "INTEGRATION_OFFLINE"
    retryable = True


class TelemetryLossError(AdapterError):
    code = "TELEMETRY_LOSS"
    retryable = True

    def __init__(self, missing_after_sequence: int):
        super().__init__(f"telemetry unavailable after sequence {missing_after_sequence}")
        self.missing_after_sequence = missing_after_sequence


class BuildMismatchError(AdapterError):
    code = "PLAYTEST_BUILD_MISMATCH"


class UnsupportedExecutionModeError(AdapterError):
    code = "EXECUTION_MODE_UNAVAILABLE"


class ExecutionTruthError(AdapterError):
    code = "EXECUTION_MODE_CONTRADICTION"


class RunAlreadyActiveError(AdapterError):
    code = "PLAYTEST_RUN_ALREADY_ACTIVE"


class RunIdentityConflictError(AdapterError):
    code = "PLAYTEST_RUN_IDENTITY_CONFLICT"


class MeasurementContractError(AdapterError):
    code = "PLAYTEST_MEASUREMENT_CONTRACT_MISMATCH"


class ActionRejectedError(AdapterError):
    code = "ACTION_OUTSIDE_TEST_CONTROLS"


class ReplayUnavailableError(AdapterError):
    code = "REPLAY_ACTION_UNAVAILABLE"


class AdapterHealth(StrictModel):
    available: bool
    checked_at: UtcDatetime
    detail: str


class RetryPolicy(StrictModel):
    max_attempts: int = Field(ge=1, le=10)
    retryable_error_codes: List[str]
    action_retry: bool = False


class AdapterCapabilities(StrictModel):
    adapter_id: StableId
    adapter_version: str
    supported_modes: List[ExecutionMode]
    supported_action_kinds: List[ActionKind]
    telemetry_contract_versions: List[int]
    supports_cancellation: bool
    supports_telemetry_recovery: bool
    supports_destructive_containment: bool
    max_steps: int = Field(ge=1)
    retry_policy: RetryPolicy
    measurement_recipes: List[MeasurementRecipeProvenance]
    provenance: AdapterProvenance

    @model_validator(mode="after")
    def validate_measurement_recipes(self) -> "AdapterCapabilities":
        if self.adapter_id != self.provenance.adapter_id:
            raise ValueError("adapter capability and provenance IDs must match")
        if self.adapter_version != self.provenance.adapter_version:
            raise ValueError("adapter capability and provenance versions must match")
        if self.provenance.execution_mode not in self.supported_modes:
            raise ValueError("adapter provenance mode must be supported")
        metric_ids = [recipe.metric_id for recipe in self.measurement_recipes]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("adapter measurement recipe metric IDs must be unique")
        return self


class DryRunResult(StrictModel):
    accepted: bool
    execution_mode: ExecutionMode
    build: BuildReference
    notices: List[str]
    blocked_reason: Optional[str] = None
    error_code: Optional[str] = None


class RuntimeSession(StrictModel):
    session_id: StableId
    run_id: RunId
    build: BuildReference
    execution_mode: ExecutionMode


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True


class PlaytestRunnerAdapter(Protocol):
    def health_check(self) -> AdapterHealth: ...

    def capabilities(self) -> AdapterCapabilities: ...

    def dry_run(
        self, test_case: TestCase, build: BuildReference, mode: ExecutionMode
    ) -> DryRunResult: ...

    def reset(
        self,
        test_case: TestCase,
        build: BuildReference,
        mode: ExecutionMode,
        run_id: RunId,
    ) -> RuntimeSession: ...

    def get_observation(self, session: RuntimeSession) -> Observation: ...

    def get_available_actions(
        self, session: RuntimeSession
    ) -> List[AvailableAction]: ...

    def execute_action(
        self,
        session: RuntimeSession,
        action: AvailableAction,
        timeout_ms: int,
        cancellation: CancellationToken,
    ) -> ActionResult: ...

    def get_game_state(self, session: RuntimeSession) -> dict: ...

    def get_goal_progress(
        self, session: RuntimeSession
    ) -> List[GoalProgress]: ...

    def capture_evidence(
        self, session: RuntimeSession, step_index: Optional[int]
    ) -> EvidenceBundle: ...

    def recover_telemetry(
        self, session: RuntimeSession, after_sequence: int
    ) -> Observation: ...

    def source_candidates(
        self, session: RuntimeSession, target_sceneops_id: Optional[str]
    ) -> List[SourceCandidate]: ...

    def logs(self, session: RuntimeSession) -> List[AdapterLog]: ...

    def measurements(self, session: RuntimeSession) -> dict: ...

    def cancel(self, session: RuntimeSession) -> None: ...
