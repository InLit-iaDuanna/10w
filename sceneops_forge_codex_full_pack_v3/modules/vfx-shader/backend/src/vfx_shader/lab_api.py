"""Local recipe editing; preview is an explicit mock plan, never a renderer."""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .fixtures import load_recipe_fixture
from .models import ApprovalState, ChangeSet, PreviewPlan, QualityTier, VfxShaderRecipe
from .service import plan_preview


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    template: Literal["home", "warehouse"]
    event: str
    parameters: dict[str, str | float | bool]
    quality_tier: QualityTier
    particle_count: int = Field(ge=0, le=10000)
    estimated_overdraw_layers: float = Field(ge=0, le=100)
    estimated_screen_coverage_percent: float = Field(ge=0, le=100)
    binding_enabled: bool


class Evaluation(BaseModel):
    recipe: VfxShaderRecipe
    preview: PreviewPlan
    mode: Literal["mock"] = "mock"
    message: str = "已执行本地参数与预算校验；预览是确定性计划，不是 Unity 或 Render 实测。"


class Proposal(BaseModel):
    id: str
    title: str
    status: str
    details: str
    approved_at: str | None = None
    mode: Literal["planned"] = "planned"


def create_lab_router() -> APIRouter:
    router = APIRouter(prefix="/api/vfx", tags=["VFX Shader"])
    changes: dict[tuple[UUID, str], ChangeSet] = {}

    def recipe_for(template: str):
        return load_recipe_fixture("hero_home_highlight" if template == "home" else "warehouse_escape")

    def view(change: ChangeSet) -> Proposal:
        payload = {key: value for key, value in asdict(change).items() if key != "approval_snapshot"}
        return Proposal(id=change.change_set_id, title="特效配方与事件绑定", status=change.approval_state.value,
                        details=json.dumps(payload, ensure_ascii=False, indent=2), approved_at=change.approved_at)

    @router.get("/fixture/{template}", response_model=VfxShaderRecipe)
    def fixture(template: Literal["home", "warehouse"]):
        return recipe_for(template)

    @router.post("/evaluate", response_model=Evaluation)
    def evaluate(draft: Draft):
        base = recipe_for(draft.template)
        if draft.event not in {binding.event_name for binding in base.bindings}:
            raise HTTPException(422, "事件不属于当前演示配方。")
        recipe = replace(base, parameters=draft.parameters, quality_tier=draft.quality_tier,
            particle_count=draft.particle_count, estimated_overdraw_layers=draft.estimated_overdraw_layers,
            estimated_screen_coverage_percent=draft.estimated_screen_coverage_percent,
            bindings=tuple(replace(binding, enabled=draft.binding_enabled if binding.event_name == draft.event else False)
                           for binding in base.bindings))
        errors = recipe.validate()
        if errors:
            raise HTTPException(422, "参数校验失败：" + "；".join(errors))
        return Evaluation(recipe=recipe, preview=plan_preview(recipe))

    @router.get("/proposals", response_model=list[Proposal])
    def proposals(session: UUID = Header(alias="X-Lab-Session")):
        return [view(value) for (owner, _), value in changes.items() if owner == session]

    @router.post("/proposals", response_model=Proposal)
    def propose(draft: Draft, session: UUID = Header(alias="X-Lab-Session")):
        result = evaluate(draft)
        recipe = result.recipe
        identity = "chg_" + uuid4().hex
        proposed = {"operation": "publish_recipe", "recipe_version": recipe.version,
            "template_id": recipe.template_id, "shader_family": recipe.shader_family,
            "quality_tier": recipe.quality_tier.value, "parameters": dict(recipe.parameters),
            "particle_count": recipe.particle_count, "estimated_overdraw_layers": recipe.estimated_overdraw_layers,
            "estimated_screen_coverage_percent": recipe.estimated_screen_coverage_percent,
            "bindings": [asdict(binding) for binding in recipe.bindings]}
        change = ChangeSet(identity, recipe.provenance.source_version, "unity",
            tuple(binding.target_sceneops_id for binding in recipe.bindings),
            {"recipe": asdict(recipe_for(draft.template))}, proposed,
            "可选交互反馈", "当前事件显示柔和高亮", "配方中的目标对象", "预算为估计值，尚未渲染",
            ("连接后实测粒子与 overdraw", "检查不同设备画质"), ("恢复 previous_values 配方",),
            ("本地人工审阅；非生产授权",), ApprovalState.PROPOSED)
        errors = change.validate()
        if errors:
            raise HTTPException(422, "提案校验失败：" + "；".join(errors))
        changes[(session, identity)] = change
        return view(change)

    @router.post("/proposals/{identity}/approve", response_model=Proposal)
    def approve(identity: str, session: UUID = Header(alias="X-Lab-Session")):
        change = changes.get((session, identity))
        if change is None:
            raise HTTPException(404, "提案不存在或会话已重启，请重新创建。")
        if change.approval_state is not ApprovalState.PROPOSED:
            raise HTTPException(409, "此提案已经审阅。")
        changes[(session, identity)] = change.approve("local-reviewer", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return view(changes[(session, identity)])

    return router
