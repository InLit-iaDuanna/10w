from __future__ import annotations

from datetime import datetime, timezone

from sceneops_production_planner.fixtures import (
    StaticApprovalProvider,
    StaticFeatureSpecProvider,
    StaticRunEvidenceProvider,
    key_door_snapshot,
)
from sceneops_production_planner.models import (
    AcceptanceEvidence,
    CreatePlanCommandRequest,
    ExecutionMode,
    FeaturePlanningSnapshot,
    ProductionPlan,
)
from sceneops_production_planner.repository import InMemoryProductionPlanRepository
from sceneops_production_planner.service import ProductionPlannerService
from sceneops_production_planner.verification import (
    PlannerExecutionContext,
    VerifiedApproval,
    VerifiedRunTiming,
)


FIXED_TIME = datetime(2026, 9, 4, 1, 2, 3, tzinfo=timezone.utc)


def create_request(snapshot: FeaturePlanningSnapshot) -> CreatePlanCommandRequest:
    return CreatePlanCommandRequest(feature_ref=snapshot.feature_ref)


def create_context(**updates) -> PlannerExecutionContext:
    values = {
        "actor_id": "user:producer",
        "ai_initiated": False,
        "occurred_at": FIXED_TIME,
        "execution_mode": ExecutionMode.MOCK,
        "correlation_id": "correlation:key-door-plan",
        "command_id": "command:create-key-door-plan",
    }
    values.update(updates)
    return PlannerExecutionContext(**values)


def create_service(
    *snapshots: FeaturePlanningSnapshot,
    run_timings: list[VerifiedRunTiming] | None = None,
    approvals: list[VerifiedApproval] | None = None,
) -> ProductionPlannerService:
    selected = list(snapshots) or [key_door_snapshot()]
    default_approvals = [
        VerifiedApproval(
            approval_ref_id="approval:plan:1",
            scope="plan",
            scope_id="plan:feature:key-and-door:r1",
            mode="mock",
        ),
        VerifiedApproval(
            approval_ref_id="approval:task:design",
            scope="task",
            scope_id="task:feature:key-and-door:design",
            mode="mock",
        ),
    ]
    return ProductionPlannerService(
        InMemoryProductionPlanRepository(),
        StaticFeatureSpecProvider(selected),
        StaticRunEvidenceProvider(run_timings or []),
        StaticApprovalProvider(approvals or default_approvals),
    )


def create_plan(service: ProductionPlannerService | None = None) -> tuple[ProductionPlannerService, ProductionPlan]:
    planner = service or create_service()
    snapshot = key_door_snapshot()
    return planner, planner.create_plan(create_request(snapshot), create_context()).plan


def evidence_for(
    task,
    criterion_id: str,
    suffix: str = "1",
    evidence_type: str | None = None,
) -> AcceptanceEvidence:
    selected_type = evidence_type or task.acceptance[0].expected_evidence[0]
    return AcceptanceEvidence(
        evidence_id=f"evidence:{task.task_id}:{suffix}",
        criterion_id=criterion_id,
        evidence_type=selected_type,
        task_id=task.task_id,
        artifact_id=f"artifact:{task.task_id}:{suffix}",
        run_id=f"run:{task.task_id}:{suffix}",
        outcome="passed",
        mode="mock",
        captured_at=FIXED_TIME,
    )
