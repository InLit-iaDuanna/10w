from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AcceptanceLink,
    ApprovalRequirement,
    Assignment,
    AssignmentKind,
    Estimate,
    EstimateKind,
    FeaturePlanningSnapshot,
    Milestone,
    PlanStatus,
    ProductionPlan,
    ProductionTask,
    Risk,
    TaskDependency,
    TaskInput,
    TaskOutput,
    Workstream,
)
from .verification import PlannerExecutionContext


@dataclass(frozen=True)
class TaskTemplate:
    workstream: Workstream
    title: str
    description: str
    output_type: str
    predicted_hours: float
    assignment_kind: AssignmentKind
    assignee_id: str
    assignee_name: str
    approval: ApprovalRequirement
    editor_id: str


TASK_TEMPLATES = (
    TaskTemplate(Workstream.DESIGN, "确认功能设计", "细化功能边界、交互规则和验收口径。", "feature-design", 4, AssignmentKind.HUMAN, "role:game-designer", "游戏设计负责人", ApprovalRequirement.HUMAN, "design.feature"),
    TaskTemplate(Workstream.CONCEPT, "制作概念方向", "为关键视觉对象与体验建立可评审的概念方向。", "concept-brief", 6, AssignmentKind.AGENT, "agent:concept", "概念代理", ApprovalRequirement.HUMAN, "concept.review"),
    TaskTemplate(Workstream.ASSET, "准备游戏资产", "创建或选用满足规格与来源要求的游戏资产。", "published-asset", 12, AssignmentKind.AGENT, "agent:asset", "资产代理", ApprovalRequirement.HUMAN, "asset.factory"),
    TaskTemplate(Workstream.ANIMATION, "准备动画", "实现功能所需的角色或物件动画与状态。", "animation-set", 8, AssignmentKind.AGENT, "agent:animation", "动画代理", ApprovalRequirement.HUMAN, "animation.timeline"),
    TaskTemplate(Workstream.WORLD, "布置世界内容", "在目标场景中放置对象并配置空间关系。", "scene-change-proposal", 8, AssignmentKind.AGENT, "agent:world", "世界代理", ApprovalRequirement.HUMAN, "scene.viewport.3d"),
    TaskTemplate(Workstream.LOGIC, "实现玩法逻辑", "实现状态、交互、库存与任务逻辑。", "logic-change-proposal", 12, AssignmentKind.AGENT, "agent:logic", "逻辑代理", ApprovalRequirement.HUMAN, "logic.gameplay-state"),
    TaskTemplate(Workstream.UI, "实现界面反馈", "实现玩家可理解的界面提示与状态反馈。", "ui-change-proposal", 5, AssignmentKind.AGENT, "agent:ui", "界面代理", ApprovalRequirement.HUMAN, "ui.flow"),
    TaskTemplate(Workstream.AUDIO, "实现音频反馈", "准备并连接功能所需的音频提示。", "audio-change-proposal", 4, AssignmentKind.AGENT, "agent:audio", "音频代理", ApprovalRequirement.HUMAN, "audio.library"),
    TaskTemplate(Workstream.VFX, "实现视觉反馈", "准备并连接功能所需的视觉特效。", "vfx-change-proposal", 5, AssignmentKind.AGENT, "agent:vfx", "特效代理", ApprovalRequirement.HUMAN, "vfx.preview"),
    TaskTemplate(Workstream.RENDER, "完成视觉评审", "按固定视角输出视觉证据并完成评审。", "render-review", 4, AssignmentKind.AGENT, "agent:render", "渲染代理", ApprovalRequirement.HUMAN, "render.viewer"),
    TaskTemplate(Workstream.BUILD, "生成可玩构建", "在审批后生成包含该功能的可玩构建。", "playable-build", 3, AssignmentKind.AGENT, "agent:build", "构建代理", ApprovalRequirement.HUMAN, "build.matrix"),
    TaskTemplate(Workstream.TEST, "验证功能验收", "执行验收测试并关联结构化证据。", "acceptance-report", 6, AssignmentKind.HUMAN, "role:qa-owner", "测试负责人", ApprovalRequirement.HUMAN, "playtest.test-case"),
)


DEPENDENCY_PAIRS = (
    (Workstream.DESIGN, Workstream.CONCEPT),
    (Workstream.CONCEPT, Workstream.ASSET),
    (Workstream.ASSET, Workstream.ANIMATION),
    (Workstream.DESIGN, Workstream.WORLD),
    (Workstream.ASSET, Workstream.WORLD),
    (Workstream.DESIGN, Workstream.LOGIC),
    (Workstream.WORLD, Workstream.LOGIC),
    (Workstream.LOGIC, Workstream.UI),
    (Workstream.LOGIC, Workstream.AUDIO),
    (Workstream.CONCEPT, Workstream.VFX),
    (Workstream.LOGIC, Workstream.VFX),
    (Workstream.WORLD, Workstream.RENDER),
    (Workstream.VFX, Workstream.RENDER),
    (Workstream.ANIMATION, Workstream.BUILD),
    (Workstream.WORLD, Workstream.BUILD),
    (Workstream.LOGIC, Workstream.BUILD),
    (Workstream.UI, Workstream.BUILD),
    (Workstream.AUDIO, Workstream.BUILD),
    (Workstream.VFX, Workstream.BUILD),
    (Workstream.RENDER, Workstream.BUILD),
    (Workstream.BUILD, Workstream.TEST),
)


def task_id(feature_id: str, workstream: Workstream) -> str:
    return f"task:{feature_id}:{workstream.value}"


def output_id(feature_id: str, workstream: Workstream) -> str:
    return f"output:{feature_id}:{workstream.value}"


def _acceptance_links(snapshot: FeaturePlanningSnapshot, workstream: Workstream) -> list[AcceptanceLink]:
    criteria = [
        criterion
        for criterion in snapshot.acceptance_criteria
        if workstream in criterion.workstreams
    ]
    if not criteria:
        criteria = snapshot.acceptance_criteria
    return [
        AcceptanceLink(
            criterion_id=criterion.criterion_id,
            expected_evidence=criterion.required_evidence,
        )
        for criterion in criteria
    ]


def _task_risks(feature_id: str, workstream: Workstream) -> list[Risk]:
    risks = {
        Workstream.ASSET: ("资产规格或来源未通过评审。", "在发布前执行资产 QA 与来源检查。"),
        Workstream.LOGIC: ("交互状态与设计验收口径不一致。", "用状态图与自动化测试逐条验证验收条件。"),
        Workstream.BUILD: ("依赖内容未合入导致构建不可验证。", "仅在所有硬依赖完成后进入构建。"),
        Workstream.TEST: ("证据不足导致功能无法验收。", "为每条验收标准绑定可追溯证据。"),
    }
    if workstream not in risks:
        return []
    description, mitigation = risks[workstream]
    return [
        Risk(
            risk_id=f"risk:{feature_id}:{workstream.value}",
            description=description,
            likelihood="medium",
            impact="high",
            mitigation=mitigation,
        )
    ]


def _dependencies(feature_id: str) -> list[TaskDependency]:
    output_types = {template.workstream: template.output_type for template in TASK_TEMPLATES}
    return [
        TaskDependency(
            dependency_id=f"dependency:{feature_id}:{before.value}:{after.value}",
            predecessor_task_id=task_id(feature_id, before),
            successor_task_id=task_id(feature_id, after),
            required_output_type=output_types[before],
        )
        for before, after in DEPENDENCY_PAIRS
    ]


def _task_inputs(
    snapshot: FeaturePlanningSnapshot,
    template: TaskTemplate,
    dependencies: list[TaskDependency],
) -> list[TaskInput]:
    inputs = [
        TaskInput(
            input_id=f"input:{snapshot.feature_ref.feature_id}:{template.workstream.value}:feature",
            source_kind="feature_spec",
            source_id=snapshot.feature_ref.feature_id,
            required_artifact_type="feature-spec",
        )
    ]
    for dependency in dependencies:
        if dependency.successor_task_id == task_id(snapshot.feature_ref.feature_id, template.workstream):
            inputs.append(
                TaskInput(
                    input_id=f"input:{dependency.dependency_id}",
                    source_kind="task_output",
                    source_id=dependency.predecessor_task_id,
                    required_artifact_type=dependency.required_output_type,
                )
            )
    return inputs


def _tasks(
    context: PlannerExecutionContext,
    snapshot: FeaturePlanningSnapshot,
    dependencies: list[TaskDependency],
) -> list[ProductionTask]:
    feature_id = snapshot.feature_ref.feature_id
    tasks: list[ProductionTask] = []
    for template in TASK_TEMPLATES:
        tasks.append(
            ProductionTask(
                task_id=task_id(feature_id, template.workstream),
                workstream=template.workstream,
                title=template.title,
                description=template.description,
                assignment=Assignment(
                    assignment_id=f"assignment:{feature_id}:{template.workstream.value}",
                    kind=template.assignment_kind,
                    assignee_id=template.assignee_id,
                    display_name=template.assignee_name,
                ),
                inputs=_task_inputs(snapshot, template, dependencies),
                outputs=[TaskOutput(output_id=output_id(feature_id, template.workstream), artifact_type=template.output_type)],
                acceptance=_acceptance_links(snapshot, template.workstream),
                estimates=[
                    Estimate(
                        estimate_id=f"estimate:{feature_id}:{template.workstream.value}:predicted",
                        kind=EstimateKind.PREDICTED,
                        hours=template.predicted_hours,
                        source="sceneops-planner-template@1",
                        mode=context.execution_mode,
                        recorded_at=context.occurred_at,
                    )
                ],
                approval_requirement=template.approval,
                recommended_editor_id=template.editor_id,
                risks=_task_risks(feature_id, template.workstream),
            )
        )
    return tasks


def _milestones(feature_id: str) -> list[Milestone]:
    groups = (
        ("design-ready", "设计已确认", (Workstream.DESIGN,)),
        ("content-ready", "内容已准备", (Workstream.CONCEPT, Workstream.ASSET, Workstream.ANIMATION)),
        ("implementation-ready", "功能已实现", (Workstream.WORLD, Workstream.LOGIC, Workstream.UI, Workstream.AUDIO, Workstream.VFX)),
        ("visual-review-ready", "视觉评审已完成", (Workstream.RENDER,)),
        ("playable-build-ready", "可玩构建已生成", (Workstream.BUILD,)),
        ("acceptance-ready", "功能验收已完成", (Workstream.TEST,)),
    )
    return [
        Milestone(
            milestone_id=f"milestone:{feature_id}:{suffix}",
            title=title,
            required_task_ids=[task_id(feature_id, workstream) for workstream in workstreams],
        )
        for suffix, title, workstreams in groups
    ]


def generate_draft_plan(
    snapshot: FeaturePlanningSnapshot,
    context: PlannerExecutionContext,
) -> ProductionPlan:
    feature_id = snapshot.feature_ref.feature_id
    dependencies = _dependencies(feature_id)
    return ProductionPlan(
        plan_id=f"plan:{feature_id}:r{snapshot.feature_ref.revision}",
        project_id=snapshot.feature_ref.project_id,
        feature_id=feature_id,
        feature_revision=snapshot.feature_ref.revision,
        feature_title=snapshot.title,
        source_contract_version=snapshot.source_contract_version,
        status=PlanStatus.DRAFT_UNCONFIRMED,
        execution_mode=context.execution_mode,
        feature_source_mode=snapshot.source_mode,
        generated_at=context.occurred_at,
        change_set_id=context.change_set_id,
        tasks=_tasks(context, snapshot, dependencies),
        dependencies=dependencies,
        milestones=_milestones(feature_id),
        risks=[
            Risk(
                risk_id=f"risk:{feature_id}:scope",
                description="功能范围变化可能影响既有依赖与里程碑。",
                likelihood="medium",
                impact="medium",
                mitigation="每次 Feature Spec 修订后运行计划影响分析。",
            )
        ],
    )
