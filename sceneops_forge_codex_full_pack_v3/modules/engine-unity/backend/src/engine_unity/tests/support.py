from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any, Dict, List, Optional, Union

from engine_unity.adapter import UnityAdapter
from engine_unity.contracts import (
    ApprovalState,
    ChangeSet,
    CommandName,
    CommandRequest,
    ExecutionContext,
    ExecutionMode,
    PAYLOAD_MODELS,
)
from engine_unity.mock_runner import FixtureUnityRunner
from engine_unity.security import expected_change_targets


MODULE_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ROOT = MODULE_ROOT / "fixtures" / "unity-projects" / "smoke-template"
MOCK_FIXTURE = MODULE_ROOT / "fixtures" / "mock" / "command-results.json"


def context(
    root: Path = PROJECT_ROOT,
    base_version: str = "git:fixture",
    approved: Optional[List[ChangeSet]] = None,
    actor_id: str = "usr_test",
) -> ExecutionContext:
    trusted = {
        change_set.change_set_id: change_set
        for change_set in approved or []
        if change_set.approval_state is ApprovalState.APPROVED
    }
    return ExecutionContext(
        configured_project_roots=[str(root)],
        permissions={"unity:read", "unity:write", "unity:execute", "unity:build"},
        current_base_version=base_version,
        actor_id=actor_id,
        approved_change_sets=trusted,
    )


DEFAULT_PROPERTY_PAYLOAD = {
    "sceneops_id": "sobj_home_key",
    "component_type": "BoxCollider",
    "property_path": "m_IsTrigger",
    "value": True,
}


def approved_change_set(
    command: CommandName = CommandName.SET_COMPONENT_PROPERTY,
    payload: Optional[Dict[str, Any]] = None,
    *,
    base_version: str = "git:fixture",
    project_id: str = "prj_remember_home",
) -> ChangeSet:
    normalized_payload = PAYLOAD_MODELS[command].model_validate(
        payload if payload is not None else DEFAULT_PROPERTY_PAYLOAD
    )
    draft = CommandRequest(
        request_id="req_change_set_targeting",
        idempotency_key="change-set-targeting",
        command=command,
        project_id=project_id,
        project_root=str(PROJECT_ROOT),
        base_version=base_version,
        mode=ExecutionMode.PLANNED,
        payload=normalized_payload.model_dump(mode="json"),
    )
    return ChangeSet(
        change_set_id=f"chg_fixture_{command.value.replace('.', '_')}",
        base_version=base_version,
        target_integration="unity",
        command=command,
        target_object_ids=expected_change_targets(draft, normalized_payload),
        previous_values={},
        proposed_values=normalized_payload.model_dump(mode="json"),
        rationale="Apply the typed Unity fixture command.",
        expected_result="The typed Unity fixture command completes once.",
        impact_scope="Stable Unity fixture targets",
        risk="low",
        validation_plan=["Run Edit Mode identity tests", "Run Play Mode key-door test"],
        rollback_plan=["Restore the prior collider snapshot"],
        approval_state=ApprovalState.APPROVED,
    )


def request(
    command: CommandName,
    payload: Optional[Dict[str, Any]] = None,
    *,
    mode: ExecutionMode = ExecutionMode.MOCK,
    root: Path = PROJECT_ROOT,
    change_set: Union[ChangeSet, None, str] = "auto",
    request_id: str = "req_fixture_001",
    idempotency_key: str = "fixture-key-001",
    max_attempts: int = 1,
    cache_key: Optional[str] = None,
) -> CommandRequest:
    mutating = command in {
        CommandName.IMPORT_ASSET,
        CommandName.MAP_IDENTITY,
        CommandName.UPSERT_PREFAB,
        CommandName.SET_COMPONENT_PROPERTY,
        CommandName.UPSERT_COLLIDER,
        CommandName.RUN_NAVMESH,
        CommandName.ENTER_PLAY,
        CommandName.EXIT_PLAY,
        CommandName.CAPTURE,
        CommandName.RUN_BUILD,
    }
    effective_payload = payload or {}
    resolved_change_set = (
        approved_change_set(command, effective_payload)
        if change_set == "auto" and mutating
        else change_set
    )
    if resolved_change_set == "auto":
        resolved_change_set = None
    return CommandRequest(
        request_id=request_id,
        idempotency_key=idempotency_key,
        command=command,
        project_id="prj_remember_home",
        project_root=str(root),
        base_version="git:fixture",
        mode=mode,
        payload=effective_payload,
        change_set=resolved_change_set,
        timeout_seconds=2,
        max_attempts=max_attempts,
        cache_key=cache_key,
    )


def context_for(
    command_request: CommandRequest,
    root: Optional[Path] = None,
    *,
    actor_id: str = "usr_test",
) -> ExecutionContext:
    approved = [command_request.change_set] if command_request.change_set else []
    return context(
        root or Path(command_request.project_root),
        base_version=command_request.base_version,
        approved=approved,
        actor_id=actor_id,
    )


class SequenceRunner:
    def __init__(self, outcomes: List[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def execute(
        self,
        command_request: CommandRequest,
        project_root: Path,
        cancellation: Optional[Event] = None,
    ) -> Dict[str, Any]:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def adapter(live_runner=None) -> UnityAdapter:
    return UnityAdapter(
        live_runner=live_runner,
        mock_runner=FixtureUnityRunner(MOCK_FIXTURE),
    )
