from __future__ import annotations

from collections import defaultdict
from .errors import PlannerDomainError
from .events import drafted_event_payload
from .generation import generate_draft_plan
from .graph import apply_validation, build_graph_view
from .impact import analyze_feature_change
from .models import (
    AcceptanceEvidence,
    ApprovalRequirement,
    Assignment,
    CreatePlanCommandRequest,
    CreatePlanCommandResponse,
    DeliverableLink,
    Estimate,
    EstimateKind,
    ExecutionMode,
    FeatureChangeImpact,
    FeaturePlanningSnapshot,
    Milestone,
    MilestoneState,
    PlanStatus,
    ProductionPlan,
    ProductionTask,
    TaskCommentReference,
    TaskDependency,
    TaskBlocker,
    TaskStatus,
)
from .ports import ApprovalProvider, FeatureSpecProvider, ProductionPlanRepository, RunEvidenceProvider
from .verification import PlannerExecutionContext


TRANSITIONS = {
    TaskStatus.DRAFT: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.WAITING_APPROVAL: {TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


class ProductionPlannerService:
    def __init__(
        self,
        repository: ProductionPlanRepository,
        feature_specs: FeatureSpecProvider,
        run_evidence: RunEvidenceProvider,
        approvals: ApprovalProvider,
    ) -> None:
        self._repository = repository
        self._feature_specs = feature_specs
        self._run_evidence = run_evidence
        self._approvals = approvals

    def create_plan(
        self,
        request: CreatePlanCommandRequest,
        context: PlannerExecutionContext,
    ) -> CreatePlanCommandResponse:
        if context.execution_mode != ExecutionMode.MOCK:
            raise PlannerDomainError(
                "TRUSTED_LIVE_CONTEXT_UNAVAILABLE",
                "core-kernel 未集成前，创建路径只允许可信的 deterministic mock 上下文。",
                details={"mode": context.execution_mode.value, "requested_mode": "blocked"},
                suggested_actions=["integration.open"],
            )
        if context.ai_initiated and not context.change_set_id:
            raise PlannerDomainError(
                "CHANGESET_REQUIRED",
                "AI 发起的计划变更必须引用 ChangeSet。",
                details={"feature_id": request.feature_ref.feature_id},
                suggested_actions=["changeset.create"],
            )
        snapshot = self._read_feature_snapshot(request)
        plan = apply_validation(generate_draft_plan(snapshot, context))
        created = self._repository.create(plan)
        if not created:
            existing = self._repository.get(plan.plan_id)
            if not existing:
                raise PlannerDomainError("CONCURRENT_PLAN_WRITE", "计划创建发生并发冲突，请重试。", retryable=True)
            return CreatePlanCommandResponse(
                created=False,
                plan=existing,
                graph=build_graph_view(existing),
                event_payloads=[],
            )
        return CreatePlanCommandResponse(
            created=True,
            plan=plan,
            graph=build_graph_view(plan),
            event_payloads=[drafted_event_payload(plan)],
        )

    def _read_feature_snapshot(self, request: CreatePlanCommandRequest) -> FeaturePlanningSnapshot:
        try:
            snapshot = self._feature_specs.get_planning_snapshot(request.feature_ref)
        except PlannerDomainError:
            raise
        except Exception as error:
            raise PlannerDomainError(
                "FEATURE_SOURCE_UNAVAILABLE",
                "Feature Spec 公共来源当前不可用。",
                details={"feature_id": request.feature_ref.feature_id, "mode": "blocked"},
                retryable=True,
                suggested_actions=["integration.retry", "design.feature.open"],
            ) from error
        if snapshot.feature_ref != request.feature_ref:
            raise PlannerDomainError(
                "FEATURE_REFERENCE_MISMATCH",
                "Feature Spec 来源返回了不同的稳定引用。",
                details={"requested": request.feature_ref.model_dump(), "received": snapshot.feature_ref.model_dump()},
            )
        if snapshot.source_mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise PlannerDomainError(
                "FEATURE_SOURCE_UNAVAILABLE",
                "Feature Spec 尚未可用，不能据此生成计划。",
                details={"feature_id": request.feature_ref.feature_id, "mode": snapshot.source_mode.value},
                retryable=snapshot.source_mode == ExecutionMode.BLOCKED,
                suggested_actions=["design.feature.open"],
            )
        return snapshot

    def get_plan(self, plan_id: str) -> ProductionPlan:
        plan = self._repository.get(plan_id)
        if not plan:
            raise PlannerDomainError("PLAN_NOT_FOUND", "找不到生产计划。", details={"plan_id": plan_id})
        return plan

    def apply_plan_approval(self, plan_id: str, approval_ref_id: str) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        self._verify_approval(approval_ref_id, "plan", plan_id)
        if plan.status == PlanStatus.APPROVED and plan.approval_ref_id == approval_ref_id:
            return plan
        blockers = build_graph_view(plan).blockers
        if blockers:
            raise PlannerDomainError(
                "PLAN_BLOCKED",
                "计划包含阻断项，不能确认。",
                details={"blocker_ids": [blocker.blocker_id for blocker in blockers]},
            )
        tasks_with_predecessors = {dependency.successor_task_id for dependency in plan.dependencies}
        tasks = [
            task.model_copy(
                update={
                    "confirmed": True,
                    "assignment": task.assignment.model_copy(update={"confirmed": True}),
                    "status": TaskStatus.READY
                    if task.status == TaskStatus.DRAFT and task.task_id not in tasks_with_predecessors
                    else task.status,
                }
            )
            for task in plan.tasks
        ]
        approved = plan.model_copy(
            update={"approval_ref_id": approval_ref_id, "status": PlanStatus.APPROVED, "tasks": tasks}
        )
        return self._persist_update(plan, approved)

    def assign_task(self, plan_id: str, task_id: str, assignment: Assignment) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        self._ensure_task_editable(task)
        updated = task.model_copy(update={"assignment": assignment.model_copy(update={"confirmed": False}), "confirmed": False})
        return self._save_unconfirmed_edit(self._replace_task(plan, updated))

    def edit_task(self, plan_id: str, task_id: str, *, title: str, description: str) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        self._ensure_task_editable(task)
        if not title.strip() or not description.strip():
            raise PlannerDomainError("INVALID_TASK_EDIT", "任务标题和描述不能为空。")
        updated = task.model_copy(update={"title": title, "description": description, "confirmed": False})
        return self._save_unconfirmed_edit(self._replace_task(plan, updated))

    def replace_dependencies(self, plan_id: str, dependencies: list[TaskDependency]) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        self._ensure_plan_structure_editable(plan)
        edited = plan.model_copy(
            update={"dependencies": dependencies, "approval_ref_id": None, "status": PlanStatus.DRAFT_UNCONFIRMED}
        )
        validated = apply_validation(edited)
        return self._persist_update(plan, validated)

    def replace_milestones(self, plan_id: str, milestones: list[Milestone]) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        self._ensure_plan_structure_editable(plan)
        edited = plan.model_copy(
            update={"milestones": milestones, "approval_ref_id": None, "status": PlanStatus.DRAFT_UNCONFIRMED}
        )
        validated = apply_validation(edited)
        return self._persist_update(plan, validated)

    def transition_task(
        self,
        plan_id: str,
        task_id: str,
        target: TaskStatus,
        *,
        approval_ref_id: str | None = None,
        blocker: TaskBlocker | None = None,
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        if target not in TRANSITIONS[task.status]:
            raise PlannerDomainError(
                "INVALID_STATUS_TRANSITION",
                f"任务不能从 {task.status.value} 进入 {target.value}。",
                details={"task_id": task_id, "from": task.status.value, "to": target.value},
            )
        if target not in {TaskStatus.BLOCKED, TaskStatus.CANCELLED} and plan.status != PlanStatus.APPROVED:
            raise PlannerDomainError("PLAN_APPROVAL_REQUIRED", "计划确认后才能推进任务。", details={"plan_id": plan_id})
        if target == TaskStatus.BLOCKED:
            if not blocker or blocker.resolved or task_id not in blocker.task_ids:
                raise PlannerDomainError("BLOCKER_REQUIRED", "进入 blocked 必须提供当前任务的未解决阻断项。")
        if task.status == TaskStatus.BLOCKED and target == TaskStatus.READY:
            unresolved = [item.blocker_id for item in task.blockers if not item.resolved]
            if unresolved:
                raise PlannerDomainError(
                    "BLOCKER_UNRESOLVED",
                    "所有任务阻断项解决后才能恢复 ready。",
                    details={"blocker_ids": unresolved},
                )
        self._check_upstream_complete(plan, task, target)
        self._check_completion(plan, task, target, approval_ref_id)
        approval_refs = task.approval_ref_ids + ([approval_ref_id] if approval_ref_id else [])
        blockers = task.blockers + ([blocker] if blocker else [])
        updated = task.model_copy(
            update={"status": target, "approval_ref_ids": approval_refs, "blockers": blockers}
        )
        changed = self._replace_task(plan, updated)
        if target == TaskStatus.COMPLETED:
            changed = self._refresh_ready_tasks(changed)
        changed = self._refresh_milestones(apply_validation(changed))
        return self._persist_update(plan, changed)

    def resolve_task_blocker(
        self,
        plan_id: str,
        task_id: str,
        blocker_id: str,
        resolution_ref_id: str,
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        if not resolution_ref_id:
            raise PlannerDomainError("BLOCKER_RESOLUTION_REQUIRED", "解决阻断项需要外部结果引用。")
        found = False
        blockers = []
        for blocker in task.blockers:
            if blocker.blocker_id == blocker_id:
                blockers.append(blocker.model_copy(update={"resolved": True, "resolution_ref_id": resolution_ref_id}))
                found = True
            else:
                blockers.append(blocker)
        if not found:
            raise PlannerDomainError("BLOCKER_NOT_FOUND", "找不到任务阻断项。", details={"blocker_id": blocker_id})
        changed = self._replace_task(plan, task.model_copy(update={"blockers": blockers}))
        return self._persist_update(plan, changed)

    def link_evidence(self, plan_id: str, task_id: str, evidence: AcceptanceEvidence) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        requirements = {
            (link.criterion_id, evidence_type)
            for link in task.acceptance
            for evidence_type in link.expected_evidence
        }
        if evidence.task_id != task_id or (evidence.criterion_id, evidence.evidence_type) not in requirements:
            raise PlannerDomainError(
                "EVIDENCE_LINK_INVALID",
                "证据必须引用当前任务声明的验收标准与证据类型。",
                details={
                    "task_id": task_id,
                    "criterion_id": evidence.criterion_id,
                    "evidence_type": evidence.evidence_type,
                },
            )
        updated = task.model_copy(update={"evidence": task.evidence + [evidence]})
        changed = self._replace_task(plan, updated)
        return self._persist_update(plan, changed)

    def link_deliverable(self, plan_id: str, task_id: str, deliverable: DeliverableLink) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        if deliverable.output_id not in {output.output_id for output in task.outputs}:
            raise PlannerDomainError("DELIVERABLE_OUTPUT_MISMATCH", "交付物没有引用当前任务的输出。")
        outputs = [
            output.model_copy(update={"artifact_id": deliverable.artifact_id})
            if output.output_id == deliverable.output_id
            else output
            for output in task.outputs
        ]
        updated = task.model_copy(update={"outputs": outputs, "deliverables": task.deliverables + [deliverable]})
        changed = self._replace_task(plan, updated)
        return self._persist_update(plan, changed)

    def link_comment(self, plan_id: str, task_id: str, comment: TaskCommentReference) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        if task.comment_thread_id and task.comment_thread_id != comment.comment_thread_id:
            raise PlannerDomainError("COMMENT_THREAD_MISMATCH", "任务评论必须属于同一外部评论线程。")
        updated = task.model_copy(
            update={
                "comment_thread_id": comment.comment_thread_id,
                "comments": task.comments + [comment],
            }
        )
        changed = self._replace_task(plan, updated)
        return self._persist_update(plan, changed)

    def record_measured_estimate(
        self,
        plan_id: str,
        task_id: str,
        *,
        run_id: str,
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        task = self._task(plan, task_id)
        timing = self._run_evidence.get_verified_timing(run_id, task_id)
        if timing.run_id != run_id or timing.task_id != task_id:
            raise PlannerDomainError(
                "RUN_EVIDENCE_MISMATCH",
                "run evidence provider 返回了不同的稳定引用。",
                details={"run_id": run_id, "task_id": task_id},
            )
        hours = (timing.completed_at - timing.started_at).total_seconds() / 3600
        measured = Estimate(
            estimate_id=f"estimate:{task_id}:measured:{run_id}",
            kind=EstimateKind.MEASURED,
            hours=hours,
            source="verified-run-timing",
            mode=timing.mode,
            recorded_at=timing.completed_at,
            run_id=timing.run_id,
            originating_live_run_id=timing.originating_live_run_id,
        )
        updated = task.model_copy(update={"estimates": task.estimates + [measured]})
        changed = self._replace_task(plan, updated)
        return self._persist_update(plan, changed)

    def analyze_feature_change(
        self,
        old_snapshot: FeaturePlanningSnapshot,
        new_snapshot: FeaturePlanningSnapshot,
        old_plan: ProductionPlan,
        new_plan: ProductionPlan,
    ) -> FeatureChangeImpact:
        return analyze_feature_change(old_snapshot, new_snapshot, old_plan, new_plan)

    def _check_upstream_complete(self, plan: ProductionPlan, task: ProductionTask, target: TaskStatus) -> None:
        if target not in {TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED}:
            return
        task_map = {candidate.task_id: candidate for candidate in plan.tasks}
        incomplete = [
            dependency.predecessor_task_id
            for dependency in plan.dependencies
            if dependency.successor_task_id == task.task_id
            and task_map[dependency.predecessor_task_id].status != TaskStatus.COMPLETED
        ]
        if incomplete:
            raise PlannerDomainError(
                "UPSTREAM_INCOMPLETE",
                "上游任务尚未完成。",
                details={"task_id": task.task_id, "upstream_task_ids": incomplete},
            )

    def _check_completion(
        self,
        plan: ProductionPlan,
        task: ProductionTask,
        target: TaskStatus,
        approval_ref_id: str | None,
    ) -> None:
        if target != TaskStatus.COMPLETED:
            return
        missing: list[str] = []
        for link in task.acceptance:
            for evidence_type in link.expected_evidence:
                passed = any(
                    evidence.criterion_id == link.criterion_id
                    and evidence.evidence_type == evidence_type
                    and evidence.outcome.value == "passed"
                    and self._evidence_mode_allowed(plan.execution_mode, evidence.mode)
                    for evidence in task.evidence
                )
                if not passed:
                    missing.append(f"{link.criterion_id}:{evidence_type}")
        if missing:
            raise PlannerDomainError(
                "ACCEPTANCE_EVIDENCE_REQUIRED",
                "任务缺少通过的验收证据。",
                details={"task_id": task.task_id, "evidence_requirements": missing},
            )
        if task.approval_requirement == ApprovalRequirement.HUMAN and not approval_ref_id:
            raise PlannerDomainError(
                "TASK_APPROVAL_REQUIRED",
                "任务完成需要外部审批引用。",
                details={"task_id": task.task_id},
                suggested_actions=["approval.open"],
            )
        if approval_ref_id:
            self._verify_approval(approval_ref_id, "task", task.task_id)

    @staticmethod
    def _evidence_mode_allowed(plan_mode: ExecutionMode, evidence_mode: ExecutionMode) -> bool:
        if plan_mode == ExecutionMode.MOCK:
            return evidence_mode == ExecutionMode.MOCK
        if plan_mode == ExecutionMode.LIVE:
            return evidence_mode in {ExecutionMode.LIVE, ExecutionMode.CACHED}
        if plan_mode == ExecutionMode.CACHED:
            return evidence_mode == ExecutionMode.CACHED
        return False

    def _refresh_ready_tasks(self, plan: ProductionPlan) -> ProductionPlan:
        predecessors: dict[str, list[str]] = defaultdict(list)
        for dependency in plan.dependencies:
            predecessors[dependency.successor_task_id].append(dependency.predecessor_task_id)
        task_map = {task.task_id: task for task in plan.tasks}
        tasks = []
        for task in plan.tasks:
            ready = task.status == TaskStatus.DRAFT and all(
                task_map[predecessor_id].status == TaskStatus.COMPLETED
                for predecessor_id in predecessors[task.task_id]
            )
            tasks.append(task.model_copy(update={"status": TaskStatus.READY}) if ready else task)
        return plan.model_copy(update={"tasks": tasks})

    @staticmethod
    def _refresh_milestones(plan: ProductionPlan) -> ProductionPlan:
        task_map = {task.task_id: task for task in plan.tasks}
        milestones = []
        for milestone in plan.milestones:
            complete = all(task_map[task_id].status == TaskStatus.COMPLETED for task_id in milestone.required_task_ids)
            state = MilestoneState.READY if complete and milestone.state == MilestoneState.PLANNED else milestone.state
            milestones.append(milestone.model_copy(update={"state": state}))
        return plan.model_copy(update={"milestones": milestones})

    @staticmethod
    def _task(plan: ProductionPlan, task_id: str) -> ProductionTask:
        for task in plan.tasks:
            if task.task_id == task_id:
                return task
        raise PlannerDomainError("TASK_NOT_FOUND", "找不到生产任务。", details={"task_id": task_id})

    @staticmethod
    def _replace_task(plan: ProductionPlan, replacement: ProductionTask) -> ProductionPlan:
        tasks = [replacement if task.task_id == replacement.task_id else task for task in plan.tasks]
        return plan.model_copy(update={"tasks": tasks})

    def _save_unconfirmed_edit(self, edited: ProductionPlan) -> ProductionPlan:
        unconfirmed = apply_validation(
            edited.model_copy(update={"approval_ref_id": None, "status": PlanStatus.DRAFT_UNCONFIRMED})
        )
        return self._persist_update(edited, unconfirmed)

    @staticmethod
    def _ensure_task_editable(task: ProductionTask) -> None:
        if task.status not in {TaskStatus.DRAFT, TaskStatus.READY, TaskStatus.BLOCKED}:
            raise PlannerDomainError(
                "TASK_REVISION_REQUIRED",
                "进行中或终态任务不能原地改写；请创建新的计划修订。",
                details={"task_id": task.task_id, "status": task.status.value},
            )

    @staticmethod
    def _ensure_plan_structure_editable(plan: ProductionPlan) -> None:
        protected = [
            task.task_id
            for task in plan.tasks
            if task.status not in {TaskStatus.DRAFT, TaskStatus.READY, TaskStatus.BLOCKED}
        ]
        if protected:
            raise PlannerDomainError(
                "PLAN_REVISION_REQUIRED",
                "已开始或结束任务存在时，依赖与里程碑需要新的计划修订。",
                details={"task_ids": protected},
            )

    def _persist_update(self, base: ProductionPlan, candidate: ProductionPlan) -> ProductionPlan:
        updated = candidate.model_copy(update={"plan_version": base.plan_version + 1})
        if not self._repository.replace(updated, expected_version=base.plan_version):
            raise PlannerDomainError(
                "CONCURRENT_PLAN_WRITE",
                "生产计划已被其他操作更新，请重新加载后重试。",
                details={"plan_id": base.plan_id, "expected_version": base.plan_version},
                retryable=True,
            )
        return updated

    def _verify_approval(self, approval_ref_id: str, scope: str, scope_id: str) -> None:
        verified = self._approvals.verify(approval_ref_id, scope, scope_id)
        if (
            verified.approval_ref_id != approval_ref_id
            or verified.scope != scope
            or verified.scope_id != scope_id
        ):
            raise PlannerDomainError(
                "APPROVAL_REFERENCE_MISMATCH",
                "Approval provider 返回了不同的稳定引用或 scope。",
                details={"approval_ref_id": approval_ref_id, "scope": scope, "scope_id": scope_id},
            )
