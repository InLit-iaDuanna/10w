from __future__ import annotations

from typing import Protocol

from .models import (
    FeaturePlanningSnapshot,
    FeatureSpecReference,
    ProductionPlan,
)
from .verification import PlannerExecutionContext, VerifiedApproval, VerifiedRunTiming


class FeatureSpecProvider(Protocol):
    """Planner-facing projection port implemented by the future design-room module."""

    def get_planning_snapshot(self, feature_ref: FeatureSpecReference) -> FeaturePlanningSnapshot:
        ...


class ProductionPlanRepository(Protocol):
    def get(self, plan_id: str) -> ProductionPlan | None:
        ...

    def create(self, plan: ProductionPlan) -> bool:
        ...

    def replace(self, plan: ProductionPlan, expected_version: int) -> bool:
        ...


class PlannerExecutionContextProvider(Protocol):
    def get_context(self) -> PlannerExecutionContext:
        ...


class RunEvidenceProvider(Protocol):
    def get_verified_timing(self, run_id: str, task_id: str) -> VerifiedRunTiming:
        ...


class ApprovalProvider(Protocol):
    def verify(self, approval_ref_id: str, scope: str, scope_id: str) -> VerifiedApproval:
        ...
