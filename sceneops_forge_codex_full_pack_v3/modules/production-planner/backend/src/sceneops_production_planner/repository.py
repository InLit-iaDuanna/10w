from __future__ import annotations

from copy import deepcopy

from .models import ProductionPlan


class InMemoryProductionPlanRepository:
    """Deterministic mock repository for module tests and local examples only."""

    def __init__(self) -> None:
        self._plans: dict[str, ProductionPlan] = {}

    def get(self, plan_id: str) -> ProductionPlan | None:
        plan = self._plans.get(plan_id)
        return deepcopy(plan) if plan else None

    def create(self, plan: ProductionPlan) -> bool:
        if plan.plan_id in self._plans:
            return False
        self._plans[plan.plan_id] = deepcopy(plan)
        return True

    def replace(self, plan: ProductionPlan, expected_version: int) -> bool:
        current = self._plans.get(plan.plan_id)
        if not current or current.plan_version != expected_version:
            return False
        self._plans[plan.plan_id] = deepcopy(plan)
        return True
