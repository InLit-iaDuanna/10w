"""Convert domain plans to the existing core ChangeSet; never apply a scene."""
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sceneops_core_contracts import ChangeSet


class WorldPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: Literal[1]
    mutationKind: Literal["world.scene-object.place", "world.graybox.apply", "world.procedural-placement.apply", "world.graph.update", "world.lighting-target.apply"]
    baseVersion: str = Field(min_length=1)
    targetModule: Literal["world-composer"]
    targetIntegration: Literal["scene-store", "blender", "unity"]
    targetSceneId: str = Field(min_length=1)
    targetObjectIds: List[str]
    previousValues: Optional[Dict[str, JsonValue]]
    proposedValues: Dict[str, JsonValue]
    rationale: str = Field(min_length=1)
    expectedResult: str = Field(min_length=1)
    impactScope: List[str]
    risk: Literal["low", "medium", "high"]
    validationPlan: List[str] = Field(min_length=1)
    rollbackPlan: List[str] = Field(min_length=1)
    approvalRoles: List[str] = Field(min_length=1)
    dryRunRequired: Literal[True]
    mode: Literal["planned"]


workbench_router = APIRouter(prefix="/world", tags=["world-workbench"])


@workbench_router.post("/proposals", response_model=ChangeSet)
def propose_world(plan: WorldPlanRequest):
    try:
        permissions = {"level-designer": "scene:approve", "project-owner": "project:approve"}
        unknown = set(plan.approvalRoles) - set(permissions)
        if unknown:
            raise ValueError("没有审批权限映射的角色：" + ", ".join(sorted(unknown)))
        return ChangeSet(
            change_set_id=f"chg_{uuid4().hex}", base_version=plan.baseVersion,
            target={"module_id": plan.targetModule, "integration_id": plan.targetIntegration,
                    "object_ids": [plan.targetSceneId, *plan.targetObjectIds]},
            previous_values=plan.previousValues or {}, proposed_values=plan.proposedValues,
            rationale=plan.rationale, expected_result=plan.expectedResult,
            impact_scope="scene", risk=plan.risk, status="waiting_approval",
            validation_plan=plan.validationPlan, rollback_plan=plan.rollbackPlan,
            approval_requirements=[{"permission": permissions[role]} for role in dict.fromkeys(plan.approvalRoles)],
            created_by={"type": "user", "id": "usr_world_lab", "display_name": "本地设计师"},
            created_at=datetime.now(timezone.utc),
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
