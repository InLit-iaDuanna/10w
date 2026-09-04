from __future__ import annotations

from collections import defaultdict, deque

from .models import (
    CriticalPath,
    Estimate,
    EstimateKind,
    GraphEdge,
    GraphNode,
    MilestoneReadiness,
    MilestoneState,
    PlanStatus,
    ProductionGraphView,
    ProductionPlan,
    TaskBlocker,
    TaskStatus,
)


def effective_estimate(task) -> Estimate:
    measured = [estimate for estimate in task.estimates if estimate.kind == EstimateKind.MEASURED]
    if measured:
        return max(measured, key=lambda estimate: estimate.recorded_at)
    predicted = [estimate for estimate in task.estimates if estimate.kind == EstimateKind.PREDICTED]
    if not predicted:
        raise ValueError(f"task {task.task_id} has no predicted or measured estimate")
    return predicted[0]


def _cycle_nodes(plan: ProductionPlan) -> list[str]:
    task_ids = {task.task_id for task in plan.tasks}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for dependency in plan.dependencies:
        if dependency.predecessor_task_id in task_ids and dependency.successor_task_id in task_ids:
            adjacency[dependency.predecessor_task_id].append(dependency.successor_task_id)
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(task_id: str) -> list[str]:
        if task_id in visiting:
            index = stack.index(task_id)
            return stack[index:] + [task_id]
        if task_id in visited:
            return []
        visiting.add(task_id)
        stack.append(task_id)
        for successor_id in adjacency[task_id]:
            cycle = visit(successor_id)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(task_id)
        visited.add(task_id)
        return []

    for task_id in sorted(task_ids):
        cycle = visit(task_id)
        if cycle:
            return cycle
    return []


def _dependency_blockers(plan: ProductionPlan) -> list[TaskBlocker]:
    task_map = {task.task_id: task for task in plan.tasks}
    blockers: list[TaskBlocker] = []
    for dependency in plan.dependencies:
        predecessor = task_map.get(dependency.predecessor_task_id)
        successor = task_map.get(dependency.successor_task_id)
        missing_ids = [task_id for task_id, task in ((dependency.predecessor_task_id, predecessor), (dependency.successor_task_id, successor)) if task is None]
        if missing_ids:
            blockers.append(
                TaskBlocker(
                    blocker_id=f"blocker:{dependency.dependency_id}:missing-task",
                    code="missing_prerequisite",
                    message=f"依赖引用了不存在的任务：{', '.join(missing_ids)}。",
                    task_ids=missing_ids,
                )
            )
            continue
        matching_output = any(output.artifact_type == dependency.required_output_type for output in predecessor.outputs)
        matching_input = any(
            task_input.source_kind == "task_output"
            and task_input.source_id == predecessor.task_id
            and task_input.required_artifact_type == dependency.required_output_type
            for task_input in successor.inputs
        )
        if not matching_output or not matching_input:
            blockers.append(
                TaskBlocker(
                    blocker_id=f"blocker:{dependency.dependency_id}:missing-output",
                    code="missing_prerequisite",
                    message=f"任务依赖缺少声明的输入或输出：{dependency.required_output_type}。",
                    task_ids=[predecessor.task_id, successor.task_id],
                )
            )
    return blockers


def _task_input_blockers(plan: ProductionPlan) -> list[TaskBlocker]:
    task_map = {task.task_id: task for task in plan.tasks}
    blockers: list[TaskBlocker] = []
    for task in plan.tasks:
        for task_input in task.inputs:
            if task_input.source_kind == "feature_spec":
                if task_input.source_id != plan.feature_id:
                    blockers.append(
                        TaskBlocker(
                            blocker_id=f"blocker:{task_input.input_id}:feature-ref",
                            code="missing_prerequisite",
                            message="任务输入引用了不同的 Feature Spec。",
                            task_ids=[task.task_id],
                        )
                    )
                continue
            source = task_map.get(task_input.source_id)
            has_output = source and any(
                output.artifact_type == task_input.required_artifact_type for output in source.outputs
            )
            has_dependency = any(
                dependency.predecessor_task_id == task_input.source_id
                and dependency.successor_task_id == task.task_id
                and dependency.required_output_type == task_input.required_artifact_type
                for dependency in plan.dependencies
            )
            if not has_output or not has_dependency:
                blockers.append(
                    TaskBlocker(
                        blocker_id=f"blocker:{task_input.input_id}:orphan-input",
                        code="missing_prerequisite",
                        message=f"任务输入没有匹配的来源输出与依赖：{task_input.input_id}。",
                        task_ids=[task_input.source_id, task.task_id],
                    )
                )
    return blockers


def _prerequisite_blockers(plan: ProductionPlan) -> list[TaskBlocker]:
    return _dependency_blockers(plan) + _task_input_blockers(plan)


def _milestone_blockers(plan: ProductionPlan) -> list[TaskBlocker]:
    task_map = {task.task_id: task for task in plan.tasks}
    blockers: list[TaskBlocker] = []
    for milestone in plan.milestones:
        missing = [task_id for task_id in milestone.required_task_ids if task_id not in task_map]
        incomplete = [task_id for task_id in milestone.required_task_ids if task_id in task_map and task_map[task_id].status != TaskStatus.COMPLETED]
        impossible_state = milestone.state in {MilestoneState.READY, MilestoneState.COMPLETED} and (missing or incomplete)
        if missing or impossible_state:
            detail = missing if missing else incomplete
            blockers.append(
                TaskBlocker(
                    blocker_id=f"blocker:{milestone.milestone_id}:impossible",
                    code="impossible_milestone_state",
                    message=f"里程碑状态与所需任务不一致：{', '.join(detail)}。",
                    task_ids=detail,
                    milestone_id=milestone.milestone_id,
                )
            )
    return blockers


def validate_plan(plan: ProductionPlan) -> list[TaskBlocker]:
    blockers = _prerequisite_blockers(plan) + _milestone_blockers(plan)
    cycle = _cycle_nodes(plan)
    if cycle:
        blockers.append(
            TaskBlocker(
                blocker_id=f"blocker:{plan.plan_id}:cycle",
                code="dependency_cycle",
                message=f"任务依赖形成循环：{' -> '.join(cycle)}。",
                task_ids=cycle,
            )
        )
    return blockers


def operational_blockers(plan: ProductionPlan) -> list[TaskBlocker]:
    return [
        blocker
        for task in plan.tasks
        for blocker in task.blockers
        if not blocker.resolved
    ]


def apply_validation(plan: ProductionPlan) -> ProductionPlan:
    blockers = validate_plan(plan)
    if blockers:
        status = PlanStatus.BLOCKED
    elif plan.approval_ref_id:
        status = PlanStatus.APPROVED
    else:
        status = PlanStatus.DRAFT_UNCONFIRMED
    return plan.model_copy(update={"blockers": blockers, "status": status})


def _topological_order(plan: ProductionPlan) -> list[str]:
    task_ids = [task.task_id for task in plan.tasks]
    known = set(task_ids)
    indegree = {task_id: 0 for task_id in task_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for dependency in plan.dependencies:
        if dependency.predecessor_task_id not in known or dependency.successor_task_id not in known:
            continue
        adjacency[dependency.predecessor_task_id].append(dependency.successor_task_id)
        indegree[dependency.successor_task_id] += 1
    queue = deque(sorted(task_id for task_id, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        task_id = queue.popleft()
        order.append(task_id)
        for successor_id in sorted(adjacency[task_id]):
            indegree[successor_id] -= 1
            if indegree[successor_id] == 0:
                queue.append(successor_id)
    return order if len(order) == len(task_ids) else []


def calculate_critical_path(plan: ProductionPlan) -> CriticalPath:
    order = _topological_order(plan)
    if not order or validate_plan(plan):
        return CriticalPath(task_ids=[], total_hours=0, estimate_basis=[])
    task_map = {task.task_id: task for task in plan.tasks}
    predecessors: dict[str, list[str]] = defaultdict(list)
    for dependency in plan.dependencies:
        predecessors[dependency.successor_task_id].append(dependency.predecessor_task_id)
    total: dict[str, float] = {}
    parent: dict[str, str] = {}
    for task_id in order:
        estimate = effective_estimate(task_map[task_id])
        prior = predecessors[task_id]
        best = max(prior, key=lambda predecessor_id: total[predecessor_id]) if prior else None
        total[task_id] = estimate.hours + (total[best] if best else 0)
        if best:
            parent[task_id] = best
    final_task_id = max(order, key=lambda task_id: total[task_id])
    path = [final_task_id]
    while path[-1] in parent:
        path.append(parent[path[-1]])
    path.reverse()
    return CriticalPath(
        task_ids=path,
        total_hours=total[final_task_id],
        estimate_basis=[effective_estimate(task_map[task_id]).kind for task_id in path],
    )


def _milestone_readiness(plan: ProductionPlan, blockers: list[TaskBlocker]) -> list[MilestoneReadiness]:
    task_map = {task.task_id: task for task in plan.tasks}
    readiness: list[MilestoneReadiness] = []
    for milestone in plan.milestones:
        relevant = [
            blocker
            for blocker in blockers
            if blocker.milestone_id == milestone.milestone_id
            or any(task_id in milestone.required_task_ids for task_id in blocker.task_ids)
        ]
        incomplete = [
            task_id
            for task_id in milestone.required_task_ids
            if task_id not in task_map or task_map[task_id].status != TaskStatus.COMPLETED
        ]
        if relevant:
            state = MilestoneState.BLOCKED
        elif incomplete:
            state = MilestoneState.PLANNED
        elif milestone.state == MilestoneState.COMPLETED:
            state = MilestoneState.COMPLETED
        else:
            state = MilestoneState.READY
        readiness.append(
            MilestoneReadiness(
                milestone_id=milestone.milestone_id,
                state=state,
                incomplete_task_ids=incomplete,
                blocker_ids=[blocker.blocker_id for blocker in relevant],
            )
        )
    return readiness


def build_graph_view(plan: ProductionPlan) -> ProductionGraphView:
    blockers = validate_plan(plan) + operational_blockers(plan)
    blocked_task_ids = {task_id for blocker in blockers for task_id in blocker.task_ids}
    nodes = []
    for task in plan.tasks:
        estimate = effective_estimate(task)
        nodes.append(
            GraphNode(
                task_id=task.task_id,
                title=task.title,
                workstream=task.workstream,
                status=task.status,
                assignment_kind=task.assignment.kind,
                assignment_label=task.assignment.display_name,
                estimate_kind=estimate.kind,
                estimate_hours=estimate.hours,
                blocked=task.task_id in blocked_task_ids or task.status == TaskStatus.BLOCKED,
            )
        )
    return ProductionGraphView(
        plan_id=plan.plan_id,
        mode=plan.execution_mode,
        nodes=nodes,
        edges=[GraphEdge(dependency_id=dependency.dependency_id, source_task_id=dependency.predecessor_task_id, target_task_id=dependency.successor_task_id) for dependency in plan.dependencies],
        critical_path=calculate_critical_path(plan),
        blockers=blockers,
        milestone_readiness=_milestone_readiness(plan, blockers),
    )


def downstream_task_ids(plan: ProductionPlan, starting_task_ids: set[str]) -> set[str]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for dependency in plan.dependencies:
        adjacency[dependency.predecessor_task_id].append(dependency.successor_task_id)
    affected = set(starting_task_ids)
    queue = deque(sorted(starting_task_ids))
    while queue:
        task_id = queue.popleft()
        for successor_id in adjacency[task_id]:
            if successor_id not in affected:
                affected.add(successor_id)
                queue.append(successor_id)
    return affected
