#!/usr/bin/env python3
"""Minimal import and approved-mutation smoke check; does not launch Unity."""

from __future__ import annotations

import json
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "backend" / "src"))

from engine_unity import (  # noqa: E402
    ApprovalState,
    ChangeSet,
    CommandName,
    CommandRequest,
    ExecutionContext,
    ExecutionMode,
    UnityAdapter,
)
from engine_unity.security import expected_change_targets  # noqa: E402


def main() -> int:
    project_root = MODULE_ROOT / "fixtures" / "unity-projects" / "smoke-template"
    fixture = MODULE_ROOT / "fixtures" / "mock" / "command-results.json"
    payload = {
        "sceneops_id": "sobj_home_key",
        "component_type": "BoxCollider",
        "property_path": "m_IsTrigger",
        "value": True,
    }
    draft = CommandRequest(
        request_id="req_smoke_component_preview",
        idempotency_key="smoke-component-preview",
        command=CommandName.SET_COMPONENT_PROPERTY,
        project_id="prj_remember_home",
        project_root=str(project_root),
        base_version="git:fixture",
        mode=ExecutionMode.PLANNED,
        payload=payload,
    )
    normalized_payload = draft.typed_payload()
    change_set = ChangeSet(
        change_set_id="chg_smoke_component_property",
        base_version="git:fixture",
        command=CommandName.SET_COMPONENT_PROPERTY,
        target_object_ids=expected_change_targets(draft, normalized_payload),
        previous_values={"value": False},
        proposed_values=normalized_payload.model_dump(mode="json"),
        rationale="Exercise one approved typed adapter path without mutating Unity.",
        expected_result="The deterministic fixture reports a mock component update.",
        impact_scope="sobj_home_key",
        risk="low",
        validation_plan=["Check the structured mock result."],
        rollback_plan=["No rollback is needed for mock execution."],
        approval_state=ApprovalState.APPROVED,
    )
    request = draft.model_copy(
        update={
            "request_id": "req_smoke_component_execute",
            "idempotency_key": "smoke-component-execute",
            "mode": ExecutionMode.MOCK,
            "change_set": change_set,
        }
    )
    context = ExecutionContext(
        configured_project_roots=[str(project_root)],
        permissions={"unity:write"},
        current_base_version="git:fixture",
        actor_id="usr_smoke",
        approved_change_sets={change_set.change_set_id: change_set},
    )
    adapter = UnityAdapter.with_defaults(unity_editor=None, fixture_file=fixture)
    result = adapter.execute(request, context)
    if result.status.value != "succeeded" or result.mode is not ExecutionMode.MOCK:
        print(result.model_dump_json(indent=2))
        return 1
    print(
        json.dumps(
            {
                "command": result.command.value,
                "mode": result.mode.value,
                "status": result.status.value,
                "target_ids": change_set.target_object_ids,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
