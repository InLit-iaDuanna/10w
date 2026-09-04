"""Local graph editing and deterministic preview; no engine execution endpoints."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sceneops_core_contracts import ChangeSet

from .models import (CodeChangeProposal, CodeChangeSet, CompileTemplateRequest,
                     GameplayGraph, GameplayGraphDiff, GraphValidationReport, StrictModel)
from .runtime import GameplayGraphRuntime
from .serialization import diff_gameplay_graphs
from .service import LogicStudioService


class PreviewStep(StrictModel):
    target_node_id: str
    event_id: Optional[str] = None


class PreviewRequest(StrictModel):
    graph: GameplayGraph
    steps: List[PreviewStep] = Field(default_factory=list, max_length=200)


class PreviewResponse(StrictModel):
    current_node_id: str
    state: Dict[str, Any]
    events: List[str]
    available: List[PreviewStep]
    mode: str = "mock"
    executor_mode: str = "live"


class GraphProposalRequest(StrictModel):
    graph: GameplayGraph
    rationale: str = Field(min_length=1, max_length=4000)


class GraphProposalResponse(StrictModel):
    change_set: ChangeSet
    diff: GameplayGraphDiff
    mode: str = "planned"


_service = LogicStudioService()
_binding = Path(__file__).resolve().parents[3] / "contracts/examples/world-workbench.binding.json"
_demo = _service.compile_template(CompileTemplateRequest.model_validate(json.loads(_binding.read_text())))
workbench_router = APIRouter(prefix="/logic", tags=["logic-workbench"])


def _validate_scene_binding(graph: GameplayGraph) -> None:
    if graph.graph_id != _demo.graph_id or graph.project_id != _demo.project_id:
        raise ValueError("图不属于当前隔离样例。")
    if graph.scene_objects != _demo.scene_objects:
        raise ValueError("场景对象目录不可由玩法图改写；请使用场景的稳定 ID。")


@workbench_router.get("/demo", response_model=GameplayGraph)
def demo_graph():
    return _demo


@workbench_router.post("/validate", response_model=GraphValidationReport)
def validate_graph(graph: GameplayGraph):
    try:
        _validate_scene_binding(graph)
        return _service.validate_graph(graph)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@workbench_router.post("/preview", response_model=PreviewResponse)
def preview(request: PreviewRequest):
    try:
        _validate_scene_binding(request.graph)
        runtime = GameplayGraphRuntime(request.graph)
        for step in request.steps:
            runtime.step(step.target_node_id, step.event_id)
        available = []
        for event_id in [None] + [event.event_id for event in request.graph.events]:
            for edge in runtime.available_transitions(event_id):
                step = PreviewStep(target_node_id=edge.target_node_id, event_id=edge.event_id)
                if step not in available:
                    available.append(step)
        return PreviewResponse(current_node_id=runtime.current_node_id, state=runtime.state,
                               events=runtime.event_log, available=available)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@workbench_router.post("/proposals", response_model=GraphProposalResponse)
def propose_graph(request: GraphProposalRequest):
    try:
        _validate_scene_binding(request.graph)
        if request.graph.version != _demo.version + 1:
            raise ValueError("草稿版本必须为当前样例版本 + 1。")
        report = _service.validate_graph(request.graph)
        if not report.valid:
            raise ValueError("玩法图存在错误：" + ", ".join(issue.code for issue in report.issues))
        diff = diff_gameplay_graphs(_demo, request.graph)
        if not diff.entries:
            raise ValueError("没有可提议的玩法图修改。")
        change_set = ChangeSet(
            change_set_id=f"chg_{uuid4().hex}", base_version=str(_demo.version),
            target={"module_id": "logic-studio", "integration_id": "unity",
                    "object_ids": [obj.sceneops_id for obj in request.graph.scene_objects]},
            previous_values={"graph": _demo.model_dump(mode="json")},
            proposed_values={"graph": request.graph.model_dump(mode="json")},
            rationale=request.rationale, expected_result="按所审阅的玩法图更新数据驱动交互。",
            impact_scope="scene", risk="medium", status="waiting_approval",
            validation_plan=["审阅对象绑定与图差异", "获授权后执行 Unity 编译与相关测试"],
            rollback_plan=[f"恢复 graph {_demo.graph_id} version {_demo.version}"],
            approval_requirements=[{"permission": "logic:approve"}],
            created_by={"type": "user", "id": "usr_world_lab", "display_name": "本地设计师"},
            created_at=datetime.now(timezone.utc),
        )
        return GraphProposalResponse(change_set=change_set, diff=diff)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@workbench_router.post("/code-proposals", response_model=CodeChangeSet)
def propose_code(proposal: CodeChangeProposal):
    try:
        if proposal.graph_id != _demo.graph_id:
            raise ValueError("代码提案必须引用当前玩法图。")
        return _service.propose_code_change(proposal)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
