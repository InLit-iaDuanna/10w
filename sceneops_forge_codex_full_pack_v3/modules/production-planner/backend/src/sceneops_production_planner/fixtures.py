from __future__ import annotations

import json
from pathlib import Path

from .errors import PlannerDomainError
from .models import (
    FeaturePlanningSnapshot,
    FeatureSpecReference,
)
from .verification import PlannerExecutionContext, VerifiedApproval, VerifiedRunTiming


def key_door_snapshot() -> FeaturePlanningSnapshot:
    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "examples"
        / "key-door-feature-planning-snapshot.json"
    )
    return FeaturePlanningSnapshot.model_validate_json(fixture_path.read_text(encoding="utf-8"))


class StaticFeatureSpecProvider:
    """Typed deterministic mock provider used by module-local tests and examples."""

    def __init__(self, snapshots: list[FeaturePlanningSnapshot]) -> None:
        self._snapshots = {self._key(snapshot.feature_ref): snapshot for snapshot in snapshots}

    def get_planning_snapshot(self, feature_ref: FeatureSpecReference) -> FeaturePlanningSnapshot:
        snapshot = self._snapshots.get(self._key(feature_ref))
        if not snapshot:
            raise PlannerDomainError(
                "FEATURE_SOURCE_UNAVAILABLE",
                "确定性 Feature Spec fixture 中不存在该引用。",
                details={"feature_ref": feature_ref.model_dump(), "mode": "blocked"},
            )
        return snapshot.model_copy(deep=True)

    @staticmethod
    def _key(feature_ref: FeatureSpecReference) -> tuple[str, str, int]:
        return feature_ref.project_id, feature_ref.feature_id, feature_ref.revision


class UnavailableFeatureSpecProvider:
    """Truthful default until the public design-room provider is composed."""

    def get_planning_snapshot(self, feature_ref: FeatureSpecReference) -> FeaturePlanningSnapshot:
        raise PlannerDomainError(
            "FEATURE_SOURCE_UNAVAILABLE",
            "design-room 公共 Feature Spec 来源尚未集成。",
            details={"feature_ref": feature_ref.model_dump(), "mode": "blocked"},
            retryable=True,
            suggested_actions=["design.feature.open"],
        )


class StaticExecutionContextProvider:
    def __init__(self, context: PlannerExecutionContext) -> None:
        self._context = context

    def get_context(self) -> PlannerExecutionContext:
        return self._context.model_copy(deep=True)


class UnavailableExecutionContextProvider:
    def get_context(self) -> PlannerExecutionContext:
        raise PlannerDomainError(
            "CORE_CONTEXT_UNAVAILABLE",
            "core-kernel 尚未提供可信命令上下文。",
            details={"mode": "blocked"},
            retryable=True,
            suggested_actions=["integration.retry"],
        )


class StaticRunEvidenceProvider:
    def __init__(self, timings: list[VerifiedRunTiming]) -> None:
        self._timings = {(timing.run_id, timing.task_id): timing for timing in timings}

    def get_verified_timing(self, run_id: str, task_id: str) -> VerifiedRunTiming:
        timing = self._timings.get((run_id, task_id))
        if not timing:
            raise PlannerDomainError(
                "RUN_EVIDENCE_UNAVAILABLE",
                "找不到已验证的运行计时证据。",
                details={"run_id": run_id, "task_id": task_id, "mode": "blocked"},
            )
        return timing.model_copy(deep=True)


class UnavailableRunEvidenceProvider:
    def get_verified_timing(self, run_id: str, task_id: str) -> VerifiedRunTiming:
        raise PlannerDomainError(
            "RUN_EVIDENCE_UNAVAILABLE",
            "真实 run evidence provider 尚未集成。",
            details={"run_id": run_id, "task_id": task_id, "mode": "blocked"},
            retryable=True,
        )


class StaticApprovalProvider:
    def __init__(self, approvals: list[VerifiedApproval]) -> None:
        self._approvals = {
            (approval.approval_ref_id, approval.scope, approval.scope_id): approval
            for approval in approvals
        }

    def verify(self, approval_ref_id: str, scope: str, scope_id: str) -> VerifiedApproval:
        approval = self._approvals.get((approval_ref_id, scope, scope_id))
        if not approval:
            raise PlannerDomainError(
                "APPROVAL_NOT_VERIFIED",
                "外部审批引用未通过 provider 验证。",
                details={"approval_ref_id": approval_ref_id, "scope": scope, "scope_id": scope_id},
            )
        return approval.model_copy(deep=True)


class UnavailableApprovalProvider:
    def verify(self, approval_ref_id: str, scope: str, scope_id: str) -> VerifiedApproval:
        raise PlannerDomainError(
            "APPROVAL_PROVIDER_UNAVAILABLE",
            "core approval provider 尚未集成。",
            details={"approval_ref_id": approval_ref_id, "scope": scope, "scope_id": scope_id, "mode": "blocked"},
            retryable=True,
        )
