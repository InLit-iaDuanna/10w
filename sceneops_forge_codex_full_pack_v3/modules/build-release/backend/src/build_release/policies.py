"""Fail-closed gate, execution-mode, and approval policies."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .enums import (
    ApprovalAction,
    ApprovalDecision,
    BuildProfile,
    DeploymentTarget,
    ExecutionMode,
    GateCategory,
    GateStatus,
)
from .errors import PolicyError
from .models_build import BuildManifest
from .models_common import Approval
from .models_release import GateBlocker, GateReport, ReleaseGate
from .ports import ArtifactCatalog

REQUIRED_GATE_CATEGORIES: Tuple[GateCategory, ...] = (
    GateCategory.ASSET,
    GateCategory.SCENE,
    GateCategory.CODE,
    GateCategory.RENDER,
    GateCategory.UNITY_TESTS,
    GateCategory.PERFORMANCE,
    GateCategory.AI_REGRESSION,
)

_MODE_PRIORITY: Dict[ExecutionMode, int] = {
    ExecutionMode.LIVE: 0,
    ExecutionMode.CACHED: 1,
    ExecutionMode.MOCK: 2,
    ExecutionMode.PLANNED: 3,
    ExecutionMode.BLOCKED: 4,
}

_ALLOWED_SOURCE_MODES: Dict[BuildProfile, Set[ExecutionMode]] = {
    BuildProfile.DEVELOPMENT: {
        ExecutionMode.LIVE,
        ExecutionMode.CACHED,
        ExecutionMode.MOCK,
    },
    BuildProfile.QA: {
        ExecutionMode.LIVE,
        ExecutionMode.CACHED,
        ExecutionMode.MOCK,
    },
    BuildProfile.JUDGE: {ExecutionMode.LIVE, ExecutionMode.CACHED},
    BuildProfile.RELEASE_CANDIDATE: {ExecutionMode.LIVE},
}


def aggregate_execution_mode(modes: Iterable[ExecutionMode]) -> ExecutionMode:
    unique = list(set(modes))
    if not unique:
        return ExecutionMode.BLOCKED
    return max(unique, key=lambda mode: _MODE_PRIORITY[mode])


def required_approval_roles(
    profile: BuildProfile,
    action: ApprovalAction,
    target: DeploymentTarget = DeploymentTarget.LOCAL,
) -> List[str]:
    if action == ApprovalAction.CREATE_CANDIDATE:
        return {
            BuildProfile.DEVELOPMENT: [],
            BuildProfile.QA: ["qa_owner"],
            BuildProfile.JUDGE: ["judge_owner"],
            BuildProfile.RELEASE_CANDIDATE: ["qa_owner", "release_owner"],
        }[profile]

    target_role = "judge_operator" if target == DeploymentTarget.JUDGE else "release_operator"
    if action == ApprovalAction.DEPLOY:
        roles = [target_role]
        if profile == BuildProfile.RELEASE_CANDIDATE:
            roles.append("release_owner")
        return roles
    if action == ApprovalAction.ROLLBACK:
        roles = [target_role, "rollback_owner"]
        if profile == BuildProfile.RELEASE_CANDIDATE:
            roles.append("release_owner")
        return roles
    if action == ApprovalAction.MARK_KNOWN_GOOD:
        return ["release_owner" if profile == BuildProfile.RELEASE_CANDIDATE else "qa_owner"]
    raise AssertionError(f"unsupported approval action: {action}")


def validate_approvals(
    approvals: Sequence[Approval],
    *,
    action: ApprovalAction,
    target_id: str,
    scope_fingerprint: str,
    required_roles: Sequence[str],
) -> None:
    for approval in approvals:
        if (
            approval.action != action
            or approval.target_id != target_id
            or approval.scope_fingerprint != scope_fingerprint
        ):
            raise PolicyError(
                "APPROVAL_SCOPE_MISMATCH",
                "Approval does not match the exact release action scope.",
                details={
                    "approval_id": approval.approval_id,
                    "expected_action": action.value,
                    "expected_target_id": target_id,
                    "expected_scope_fingerprint": scope_fingerprint,
                },
            )
    rejected_roles = {
        approval.role
        for approval in approvals
        if approval.decision == ApprovalDecision.REJECTED
    }
    if rejected_roles:
        raise PolicyError(
            "APPROVAL_REJECTED",
            "A required release approval was rejected.",
            details={"roles": sorted(rejected_roles)},
        )
    approved_roles = {
        approval.role
        for approval in approvals
        if approval.decision == ApprovalDecision.APPROVED
    }
    missing = sorted(set(required_roles) - approved_roles)
    if missing:
        raise PolicyError(
            "APPROVAL_REQUIRED",
            "Explicit approval is required for this release action.",
            details={"missing_roles": missing, "action": action.value},
        )


def evaluate_release_gates(
    manifest: BuildManifest,
    gates: Sequence[ReleaseGate],
    catalog: ArtifactCatalog,
    now: datetime,
) -> GateReport:
    blockers: List[GateBlocker] = []
    warnings: List[GateBlocker] = []
    grouped: Dict[GateCategory, List[ReleaseGate]] = {}
    source_modes: List[ExecutionMode] = [
        manifest.mode,
        *[artifact.mode for artifact in manifest.artifacts],
        *[evidence.mode for evidence in manifest.test_evidence],
    ]

    for gate in gates:
        grouped.setdefault(gate.category, []).append(gate)
        source_modes.append(gate.mode)
        source_modes.extend(evidence.mode for evidence in gate.evidence)

    passed: List[GateCategory] = []
    for category in REQUIRED_GATE_CATEGORIES:
        matching = grouped.get(category, [])
        if not matching:
            blockers.append(_blocker("MISSING_GATE", "Required release gate is missing.", now, category))
            continue
        if len(matching) > 1:
            blockers.append(
                _blocker("CONFLICTING_GATES", "Multiple results exist for one required gate.", now, category)
            )
            continue
        gate = matching[0]
        gate_findings = _evaluate_gate(manifest, gate, catalog, now)
        if not gate.blocking:
            gate_findings.append(
                _blocker(
                    "REQUIRED_GATE_NON_BLOCKING",
                    "A required release gate cannot be downgraded to non-blocking.",
                    now,
                    category,
                    gate.gate_id,
                )
            )
        blockers.extend(gate_findings)
        if not gate_findings and gate.status == GateStatus.PASSED:
            passed.append(category)

    for category, matching in grouped.items():
        if category in REQUIRED_GATE_CATEGORIES:
            continue
        for gate in matching:
            warnings.extend(_evaluate_gate(manifest, gate, catalog, now))

    allowed_modes = _ALLOWED_SOURCE_MODES[manifest.profile]
    disallowed = sorted(
        {mode.value for mode in source_modes if mode not in allowed_modes}
    )
    if disallowed:
        blockers.append(
            GateBlocker(
                code="EXECUTION_MODE_NOT_ALLOWED",
                message=f"Profile {manifest.profile.value} does not allow modes: {', '.join(disallowed)}.",
                detected_at=now,
            )
        )

    return GateReport(
        source_commit=manifest.source_commit,
        required_categories=list(REQUIRED_GATE_CATEGORIES),
        passed_categories=passed,
        blockers=blockers,
        warnings=warnings,
        source_modes=sorted(set(source_modes), key=lambda mode: mode.value),
        mode=ExecutionMode.BLOCKED if blockers else aggregate_execution_mode(source_modes),
        can_release=not blockers,
        evaluated_at=now,
    )


def _evaluate_gate(
    manifest: BuildManifest,
    gate: ReleaseGate,
    catalog: ArtifactCatalog,
    now: datetime,
) -> List[GateBlocker]:
    findings: List[GateBlocker] = []
    manifest_evidence = {
        item.artifact_id: item for item in manifest.test_evidence
    }
    if gate.source_commit.lower() != manifest.source_commit.lower():
        findings.append(_blocker("STALE_GATE", "Gate was evaluated for another commit.", now, gate.category, gate.gate_id))
    if gate.status != GateStatus.PASSED:
        findings.append(_blocker("GATE_NOT_PASSED", f"Gate status is {gate.status.value}.", now, gate.category, gate.gate_id))
    if gate.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
        findings.append(_blocker("GATE_NOT_EXECUTED", f"Gate mode is {gate.mode.value}.", now, gate.category, gate.gate_id))
    for evidence in gate.evidence:
        if manifest_evidence.get(evidence.artifact_id) != evidence:
            findings.append(
                _blocker(
                    "UNBOUND_GATE_EVIDENCE",
                    "Gate evidence is not an exact immutable manifest evidence record.",
                    now,
                    gate.category,
                    gate.gate_id,
                )
            )
        if evidence.project_id != manifest.project_id or evidence.game_id != manifest.game_id:
            findings.append(_blocker("CROSS_PROJECT_EVIDENCE", "Gate evidence belongs to another project or game.", now, gate.category, gate.gate_id))
        if evidence.build_run_id != manifest.build_run_id:
            findings.append(_blocker("STALE_EVIDENCE", "Gate evidence belongs to another build run.", now, gate.category, gate.gate_id))
        inspection = catalog.inspect(evidence)
        if not inspection.available:
            findings.append(_blocker("MISSING_ARTIFACT", inspection.reason, now, gate.category, gate.gate_id))
        elif not inspection.checksum_matches or not inspection.size_matches:
            findings.append(_blocker("CORRUPT_ARTIFACT", inspection.reason, now, gate.category, gate.gate_id))
    return findings


def _blocker(
    code: str,
    message: str,
    now: datetime,
    category: GateCategory,
    gate_id: str = None,
) -> GateBlocker:
    return GateBlocker(
        code=code,
        message=message,
        category=category,
        gate_id=gate_id,
        detected_at=now,
    )
