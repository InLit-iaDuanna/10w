from __future__ import annotations

from typing import List, Tuple

from .ports import (
    ActionRejectedError,
    AdapterCapabilities,
    AdapterOfflineError,
    BuildMismatchError,
    ExecutionTruthError,
    MeasurementContractError,
    PlaytestRunnerAdapter,
    RuntimeSession,
    TelemetryLossError,
    UnsupportedExecutionModeError,
)
from .schemas import (
    EvidenceBundle,
    MeasurementRecipeProvenance,
    Observation,
    PlaytestRun,
    RunRequest,
)


def preflight_adapter(
    adapter: PlaytestRunnerAdapter, request: RunRequest
) -> AdapterCapabilities:
    if request.test_case.project_id != request.build.project_id:
        raise BuildMismatchError("TestCase and build project_id differ")
    if request.test_case.scene_id != request.build.scene_id:
        raise BuildMismatchError("TestCase and build scene_id differ")
    health = adapter.health_check()
    if not health.available:
        raise AdapterOfflineError(health.detail)
    capabilities = adapter.capabilities()
    _validate_capabilities(request, capabilities)
    dry_run = adapter.dry_run(
        request.test_case, request.build, request.execution_mode
    )
    if dry_run.execution_mode != request.execution_mode:
        raise ExecutionTruthError("adapter dry-run contradicts requested execution mode")
    if dry_run.build != request.build:
        raise BuildMismatchError("adapter dry-run returned a different build")
    if not dry_run.accepted:
        if dry_run.error_code == BuildMismatchError.code:
            raise BuildMismatchError(dry_run.blocked_reason or "build mismatch")
        raise ActionRejectedError(dry_run.blocked_reason or "adapter rejected dry-run")
    return capabilities


def _validate_capabilities(
    request: RunRequest, capabilities: AdapterCapabilities
) -> None:
    if capabilities.adapter_id != capabilities.provenance.adapter_id:
        raise ExecutionTruthError(
            "adapter capability and provenance identities differ"
        )
    if capabilities.adapter_version != capabilities.provenance.adapter_version:
        raise ExecutionTruthError(
            "adapter capability and provenance versions differ"
        )
    if request.execution_mode not in capabilities.supported_modes:
        raise UnsupportedExecutionModeError(
            f"adapter cannot execute {request.execution_mode.value}"
        )
    if capabilities.provenance.execution_mode != request.execution_mode:
        raise ExecutionTruthError(
            "adapter provenance contradicts requested execution mode"
        )
    if not capabilities.supports_cancellation:
        raise ActionRejectedError("playtest adapter must support cancellation")
    if not capabilities.supports_telemetry_recovery:
        raise ActionRejectedError("playtest adapter must support telemetry recovery")
    if (
        request.build.telemetry_contract_version
        not in capabilities.telemetry_contract_versions
    ):
        raise BuildMismatchError("telemetry contract version is unsupported")
    if request.test_case.controls.max_steps > capabilities.max_steps:
        raise ActionRejectedError("TestCase max_steps exceeds adapter capability")
    unsupported = set(request.test_case.controls.allowed_action_kinds) - set(
        capabilities.supported_action_kinds
    )
    if unsupported:
        names = ", ".join(sorted(action.value for action in unsupported))
        raise ActionRejectedError(
            f"TestCase allows action kinds unsupported by adapter: {names}"
        )
    if (
        request.test_case.controls.allow_destructive
        and not capabilities.supports_destructive_containment
    ):
        raise ActionRejectedError(
            "adapter does not provide destructive-test containment"
        )


def select_measurement_recipes(
    request: RunRequest, capabilities: AdapterCapabilities
) -> List[MeasurementRecipeProvenance]:
    by_metric_id = {
        recipe.metric_id: recipe for recipe in capabilities.measurement_recipes
    }
    required_ids = [
        metric.metric_id for metric in request.test_case.regression_metrics
    ]
    missing = sorted(set(required_ids) - set(by_metric_id))
    if missing:
        raise MeasurementContractError(
            f"adapter has no measurement recipe for: {', '.join(missing)}"
        )
    return [by_metric_id[metric_id] for metric_id in required_ids]


def read_observation(
    adapter: PlaytestRunnerAdapter,
    session: RuntimeSession,
    run: PlaytestRun,
    last_sequence: int,
) -> Tuple[Observation, bool]:
    telemetry_lost = False
    expected_sequence = last_sequence + 1
    try:
        observation = adapter.get_observation(session)
    except TelemetryLossError:
        observation = adapter.recover_telemetry(session, last_sequence)
        telemetry_lost = True
    if not telemetry_lost and observation.telemetry_sequence != expected_sequence:
        observation = adapter.recover_telemetry(session, last_sequence)
        telemetry_lost = True
    if observation.telemetry_sequence != expected_sequence:
        raise TelemetryLossError(last_sequence)
    _validate_observation(run, observation)
    if adapter.get_available_actions(session) != observation.available_actions:
        raise ExecutionTruthError(
            "available-action channel contradicts the observation snapshot"
        )
    if adapter.get_game_state(session) != observation.game_state:
        raise ExecutionTruthError(
            "game-state channel contradicts the observation snapshot"
        )
    if adapter.get_goal_progress(session) != observation.goals:
        raise ExecutionTruthError(
            "goal-progress channel contradicts the observation snapshot"
        )
    return observation, telemetry_lost


def _validate_observation(run: PlaytestRun, observation: Observation) -> None:
    if observation.build_id != run.build.build_id:
        raise BuildMismatchError("observation build_id differs from requested build")
    if observation.scene_id != run.build.scene_id:
        raise BuildMismatchError("observation scene_id differs from requested scene")


def validate_evidence(
    run: PlaytestRun, session: RuntimeSession, evidence: EvidenceBundle
) -> None:
    if evidence.execution_mode != run.execution_mode:
        raise ExecutionTruthError(
            "captured evidence contradicts the run execution mode"
        )
    if evidence.build_id != run.build.build_id:
        raise BuildMismatchError("captured evidence build_id differs from run")
    if evidence.scene_id != run.build.scene_id:
        raise BuildMismatchError("captured evidence scene_id differs from run")
    if evidence.run_id != run.run_id or evidence.session_id != session.session_id:
        raise ExecutionTruthError(
            "captured evidence has the wrong run or session identity"
        )
    if any(
        artifact.source_project_id != run.test_case.project_id
        or artifact.source_version != run.build.version
        for artifact in evidence.artifacts
    ):
        raise ExecutionTruthError(
            "captured artifacts contradict the run project or build version"
        )
