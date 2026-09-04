"""Isolated planning sandbox: real domain service, explicitly mock identity/approval."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from threading import RLock
from fastapi import APIRouter, FastAPI
from pydantic import Field
from .models import (ContractModel, FeaturePlanningSnapshot, CreatePlanCommandRequest,
    CreatePlanCommandResponse, ProductionPlan, ProductionGraphView, Assignment,
    TaskDependency, Milestone, TaskStatus, TaskBlocker)
from .fixtures import UnavailableRunEvidenceProvider, StaticApprovalProvider
from .repository import InMemoryProductionPlanRepository
from .service import ProductionPlannerService
from .verification import PlannerExecutionContext, VerifiedApproval
from .router import create_app
from .graph import build_graph_view
from .errors import PlannerDomainError

class LabCreateRequest(ContractModel):
    snapshot: FeaturePlanningSnapshot

class LabEditRequest(ContractModel):
    expected_version: int = Field(ge=1)
    task_id: str
    title: str
    description: str

class LabAssignmentRequest(ContractModel):
    expected_version: int = Field(ge=1)
    task_id: str
    assignment: Assignment

class LabDependenciesRequest(ContractModel):
    expected_version: int = Field(ge=1)
    dependencies: list[TaskDependency]

class LabMilestonesRequest(ContractModel):
    expected_version: int = Field(ge=1)
    milestones: list[Milestone]

class LabApprovalRequest(ContractModel):
    expected_version: int = Field(ge=1)

class LabTransitionRequest(LabApprovalRequest):
    task_id: str
    target: TaskStatus
    blocker: Optional[TaskBlocker] = None

class LabResolutionRequest(LabApprovalRequest):
    task_id: str
    blocker_id: str
    resolution_ref_id: str = Field(min_length=1)

class LabApprovals:
    def __init__(self):
        self.records = []
    def add(self, approval):
        self.records.append(approval)
    def verify(self, approval_ref_id, scope, scope_id):
        return StaticApprovalProvider(self.records).verify(approval_ref_id, scope, scope_id)

class LabSources:
    def __init__(self):
        self.snapshots = {}
    def get_planning_snapshot(self, feature_ref):
        return self.snapshots[(feature_ref.project_id, feature_ref.feature_id, feature_ref.revision)]
    def get_context(self):
        return PlannerExecutionContext(actor_id="user:local-sandbox", ai_initiated=False,
            occurred_at=datetime.now(timezone.utc), execution_mode="mock",
            correlation_id=str(uuid4()), command_id=str(uuid4()))


def create_planning_lab_app(*, repository=None, project_id=None) -> FastAPI:
    sources = LabSources()
    approvals = LabApprovals()
    service = ProductionPlannerService(repository or InMemoryProductionPlanRepository(), sources,
        UnavailableRunEvidenceProvider(), approvals)
    app = create_app(service, sources)
    lock = RLock()

    def mutate(plan_id, request, operation):
        with lock:
            if service.get_plan(plan_id).plan_version != request.expected_version:
                raise PlannerDomainError("CONCURRENT_PLAN_WRITE", "计划版本已变化，请刷新后重试。")
            return operation()

    @app.post('/v1/planning-lab/create', response_model=CreatePlanCommandResponse)
    def create(request: LabCreateRequest):
        snapshot = request.snapshot
        if project_id and snapshot.feature_ref.project_id != project_id:
            raise PlannerDomainError('PROJECT_MISMATCH', '设计投影不属于当前项目。')
        if snapshot.source_mode.value != 'mock':
            raise PlannerDomainError('MOCK_ONLY', '隔离工作台仅接收明确标记 mock 的设计投影。')
        ref = snapshot.feature_ref
        with lock:
            key = (ref.project_id, ref.feature_id, ref.revision)
            existing = sources.snapshots.get(key)
            if existing is not None and existing != snapshot:
                raise PlannerDomainError('FEATURE_VERSION_CONFLICT', '同一设计版本不能对应不同内容，请保存新版本。')
            sources.snapshots[key] = snapshot
            return service.create_plan(CreatePlanCommandRequest(feature_ref=ref), sources.get_context())

    @app.post('/v1/planning-lab/{plan_id}/edit', response_model=ProductionPlan)
    def edit(plan_id: str, request: LabEditRequest):
        return mutate(plan_id, request, lambda: service.edit_task(plan_id, request.task_id,
            title=request.title, description=request.description))

    @app.post('/v1/planning-lab/{plan_id}/assignment', response_model=ProductionPlan)
    def assign(plan_id: str, request: LabAssignmentRequest):
        return mutate(plan_id, request, lambda: service.assign_task(plan_id, request.task_id, request.assignment))

    @app.post('/v1/planning-lab/{plan_id}/dependencies', response_model=ProductionPlan)
    def dependencies(plan_id: str, request: LabDependenciesRequest):
        return mutate(plan_id, request, lambda: service.replace_dependencies(plan_id, request.dependencies))

    @app.post('/v1/planning-lab/{plan_id}/milestones', response_model=ProductionPlan)
    def milestones(plan_id: str, request: LabMilestonesRequest):
        return mutate(plan_id, request, lambda: service.replace_milestones(plan_id, request.milestones))

    @app.post('/v1/planning-lab/{plan_id}/approve', response_model=ProductionPlan)
    def approve(plan_id: str, request: LabApprovalRequest):
        def apply():
            approval = VerifiedApproval(approval_ref_id=f'mock-approval:{uuid4()}', scope='plan', scope_id=plan_id, mode='mock')
            approvals.add(approval)
            return service.apply_plan_approval(plan_id, approval.approval_ref_id)
        return mutate(plan_id, request, apply)

    @app.post('/v1/planning-lab/{plan_id}/transition', response_model=ProductionPlan)
    def transition(plan_id: str, request: LabTransitionRequest):
        return mutate(plan_id, request, lambda: service.transition_task(plan_id, request.task_id, request.target, blocker=request.blocker))

    @app.post('/v1/planning-lab/{plan_id}/resolve', response_model=ProductionPlan)
    def resolve(plan_id: str, request: LabResolutionRequest):
        return mutate(plan_id, request, lambda: service.resolve_task_blocker(plan_id, request.task_id, request.blocker_id, request.resolution_ref_id))

    return app


def create_workspace_router(database, project_id):
    """Composition-compatible routes with an empty, persistent project repository."""
    from .sqlite_repository import SqliteProductionPlanRepository
    app = create_planning_lab_app(repository=SqliteProductionPlanRepository(database, project_id), project_id=project_id)
    router = APIRouter()
    router.include_router(app.router)
    return router
