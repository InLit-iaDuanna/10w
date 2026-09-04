from __future__ import annotations

from .errors import PlannerDomainError
from .models import (
    PlannerEventPayload,
    ProductionPlan,
    ProductionPlanApprovedPayload,
    ProductionPlanDraftedPayload,
)


def drafted_event_payload(plan: ProductionPlan) -> PlannerEventPayload:
    payload = ProductionPlanDraftedPayload(
        plan_id=plan.plan_id,
        feature_id=plan.feature_id,
        feature_revision=plan.feature_revision,
        task_count=len(plan.tasks),
    )
    return PlannerEventPayload(
        event_type="production.plan.drafted",
        payload=payload.model_dump(mode="json"),
    )


def approved_event_payload(plan: ProductionPlan) -> PlannerEventPayload:
    if not plan.approval_ref_id:
        raise PlannerDomainError("APPROVAL_REFERENCE_REQUIRED", "计划尚未关联外部审批。")
    payload = ProductionPlanApprovedPayload(
        plan_id=plan.plan_id,
        approval_id=plan.approval_ref_id,
    )
    return PlannerEventPayload(
        event_type="production.plan.approved",
        payload=payload.model_dump(mode="json"),
    )
