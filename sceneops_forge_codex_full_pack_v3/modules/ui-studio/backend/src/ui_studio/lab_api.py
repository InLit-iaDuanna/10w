"""Local draft editing and approval; no Unity adapter is constructed here."""
from __future__ import annotations
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .contracts import (ChangeSet, UiMappingRequest, UiFlow, UiScreen, UiElement,
                        ResolutionProfile, SafeArea, ValidationIssue)
from .service import UiStudioService
from .templates import load_warehouse_escape_template


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: Literal["home", "warehouse"]
    event: str
    flow: UiFlow
    profile: ResolutionProfile
    character_limit: int = Field(default=32, ge=1, le=1000)


class Fixture(BaseModel):
    flow: UiFlow
    profile: ResolutionProfile
    mode: Literal["mock"] = "mock"


class Check(BaseModel):
    issues: list[ValidationIssue]
    mode: Literal["live"] = "live"
    message: str = "本地规则已实际执行；不是设备截图或 Unity 验证。"


class Proposal(BaseModel):
    id: str
    title: str
    status: str
    details: str
    approved_at: str | None = None
    mode: Literal["planned"] = "planned"


CONTEXT = {
    "home": ("prj_find_my_way_home", {
        "gameplay.key.picked_up": ("so_key_home_01", "prompt.key-picked"),
        "gameplay.door.unlocked": ("so_door_home_01", "prompt.door-unlocked")}),
    "warehouse": ("prj_warehouse_escape", {
        "gameplay.switch.activated": ("so_switch_warehouse_01", "prompt.switch-on"),
        "gameplay.exit.unlocked": ("so_exit_warehouse_01", "hud.escape")}),
}


def fixture(template: str) -> Fixture:
    if template == "home":
        path = Path(__file__).parents[3] / "frontend/src/fixtures/keyDoorVisualFixture.json"
        records = json.loads(path.read_text())["screens"]
        screens = tuple(UiScreen(row["id"], row["text"], "hud" if i == 0 else "feedback_prompt",
            {"zh-CN": row["text"]}, (records[i + 1]["id"],) if i + 1 < len(records) else (),
            (UiElement(row["id"] + ".text", row["anchor"], 0, 0, 360, 64),))
            for i, row in enumerate(records))
        flow = UiFlow("flow.home", "home", screens[0].id, screens)
    else:
        original = load_warehouse_escape_template()
        flow = replace(original, screens=tuple(replace(screen, elements=(
            UiElement(screen.id + ".text", "safe-bottom-center", 0, 0, 360, 64),))
            for screen in original.screens))
    return Fixture(flow=flow, profile=ResolutionProfile("横屏手机", 1280, 720, SafeArea(48, 24, 48, 24)))


def create_lab_router() -> APIRouter:
    router = APIRouter(prefix="/api/ui", tags=["UI Studio"])
    service = UiStudioService()
    changes: dict[tuple[UUID, str], ChangeSet] = {}

    def view(change: ChangeSet) -> Proposal:
        payload = {key: value for key, value in asdict(change).items()
                   if not key.startswith("_") and key != "mapping_result"}
        return Proposal(id=change.id, title="UI 提示映射", status=change.state.value,
                        details=json.dumps(payload, ensure_ascii=False, indent=2), approved_at=change.approved_at)

    @router.get("/fixture/{template}", response_model=Fixture)
    def get_fixture(template: Literal["home", "warehouse"]):
        return fixture(template)

    @router.post("/check", response_model=Check)
    def check(draft: Draft):
        return Check(issues=list(service.check_flow(draft.flow, draft.profile, draft.character_limit)))

    @router.get("/proposals", response_model=list[Proposal])
    def proposals(session: UUID = Header(alias="X-Lab-Session")):
        return [view(value) for (owner, _), value in changes.items() if owner == session]

    @router.post("/proposals", response_model=Proposal)
    def propose(draft: Draft, session: UUID = Header(alias="X-Lab-Session")):
        issues = service.check_flow(draft.flow, draft.profile, draft.character_limit)
        if issues:
            raise HTTPException(422, "请先修复 UI 校验问题，再创建映射提案。")
        project, events = CONTEXT[draft.template]
        if draft.event not in events:
            raise HTTPException(422, "事件不属于当前演示项目。")
        target, screen_id = events[draft.event]
        if screen_id not in {screen.id for screen in draft.flow.screens}:
            raise HTTPException(422, "事件对应的提示界面不存在。")
        identity = "chg_" + uuid4().hex
        request = UiMappingRequest(identity, draft.flow.id, screen_id, "Canvas/Feedback", "prefab_feedback",
                                   "demo-1", "local-designer", project, (target,))
        change = ChangeSet(identity, request, "demo-1", "unity", (target,), {"mapping": "未映射"},
            {"flow_id": draft.flow.id, "screen_id": screen_id, "unity_canvas_path": request.unity_canvas_path,
             "prefab_id": request.prefab_id, "event": draft.event, "draft": draft.model_dump_json()},
            "统一交互提示", "事件触发对应提示", "仅当前目标 UI", "未在设备验证",
            "连接 Unity 后验证 Canvas 与设备安全区", "恢复 previous_values", ("本地人工审阅；非生产授权",))
        change.validate()
        changes[(session, identity)] = change
        return view(change)

    @router.post("/proposals/{identity}/approve", response_model=Proposal)
    def approve(identity: str, session: UUID = Header(alias="X-Lab-Session")):
        change = changes.get((session, identity))
        if change is None:
            raise HTTPException(404, "提案不存在或会话已重启，请重新创建。")
        if change.state.value != "proposed":
            raise HTTPException(409, "此提案已经审阅。")
        change.approve("local-reviewer", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return view(change)

    return router
