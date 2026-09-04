from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Callable, Collection
from uuid import uuid4

from .models import (
    ApprovalRecord,
    ApprovalRequirement,
    ChangeSetStatus,
    CodeChangeProposal,
    CodeChangeSet,
    ExecutionMode,
)
from .unity_adapter import AdapterExecutionContext, UnityCodeChangeAdapter


class CodeChangeProposalError(ValueError):
    pass


class ApprovalRequiredError(PermissionError):
    pass


class AdapterUnavailableError(RuntimeError):
    pass


def _default_id() -> str:
    return f"chg_{uuid4().hex}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CodeChangeCoordinator:
    def __init__(
        self,
        *,
        id_factory: Callable[[], str] = _default_id,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self._id_factory = id_factory
        self._clock = clock

    def propose(self, proposal: CodeChangeProposal) -> CodeChangeSet:
        _validate_proposal(proposal)
        return CodeChangeSet(
            change_set_id=self._id_factory(),
            proposal_id=proposal.proposal_id,
            graph_id=proposal.graph_id,
            graph_version=proposal.graph_version,
            base_version=proposal.base_version,
            target_objects=list(proposal.target_sceneops_ids),
            target_paths=list(proposal.target_paths),
            previous_values={"project_version": proposal.base_version},
            proposed_values={"unified_diff": proposal.unified_diff},
            rationale=proposal.rationale,
            expected_result=proposal.expected_result,
            impact_scope=proposal.impact_scope,
            risk=proposal.risk,
            validation_plan=list(proposal.validation_plan),
            rollback_plan=list(proposal.rollback_plan),
            approval_requirements=[
                ApprovalRequirement(
                    permission="logic:code:approve",
                    reason="C# changes can modify Unity project behavior.",
                )
            ],
            status=ChangeSetStatus.WAITING_APPROVAL,
            mode=ExecutionMode.PLANNED,
        )

    def approve(
        self,
        change_set: CodeChangeSet,
        *,
        approver_id: str,
        permissions: Collection[str],
    ) -> CodeChangeSet:
        if change_set.status != ChangeSetStatus.WAITING_APPROVAL:
            raise ApprovalRequiredError(
                f"ChangeSet status is '{change_set.status.value}', not waiting_approval."
            )
        required = {
            requirement.permission for requirement in change_set.approval_requirements
        }
        missing = sorted(required - set(permissions))
        if missing:
            raise ApprovalRequiredError(
                "Approver lacks permissions: " + ", ".join(missing)
            )
        approval = ApprovalRecord(
            approver_id=approver_id,
            approved_at=self._clock(),
            permission="logic:code:approve",
        )
        return change_set.model_copy(
            update={"status": ChangeSetStatus.APPROVED, "approval": approval}
        )

    def apply(
        self,
        change_set: CodeChangeSet,
        adapter: UnityCodeChangeAdapter,
        context: AdapterExecutionContext,
    ) -> CodeChangeSet:
        if change_set.status != ChangeSetStatus.APPROVED or change_set.approval is None:
            raise ApprovalRequiredError(
                "An explicitly approved ChangeSet is required before adapter apply."
            )
        health = adapter.health_check()
        if health.status != "online":
            raise AdapterUnavailableError(health.reason or "Unity adapter is offline.")
        capabilities = adapter.capabilities()
        required_commands = {
            "unity.code_change.dry_run",
            "unity.code_change.apply",
            "unity.compile_and_test",
            "unity.code_change.rollback",
        }
        if not required_commands.issubset(set(capabilities.allowed_commands)):
            raise AdapterUnavailableError(
                "Unity adapter does not expose the complete allowlisted code-change flow."
            )

        preview = adapter.dry_run(change_set, context)
        if not preview.accepted:
            return change_set.model_copy(
                update={
                    "status": ChangeSetStatus.FAILED,
                    "mode": preview.mode,
                    "last_error": preview.rejection_code or "DRY_RUN_REJECTED",
                }
            )
        if set(preview.impacted_paths) != set(change_set.target_paths):
            return change_set.model_copy(
                update={
                    "status": ChangeSetStatus.FAILED,
                    "mode": preview.mode,
                    "last_error": "DRY_RUN_SCOPE_MISMATCH",
                }
            )

        applying = change_set.model_copy(update={"status": ChangeSetStatus.APPLYING})
        receipt = adapter.apply(applying, context)
        result = adapter.compile_and_test(receipt, context)
        execution_fields = {
            "execution_receipt_id": receipt.receipt_id,
            "rollback_token": receipt.rollback_token,
            "validation_result": result,
            "mode": result.mode,
        }
        if result.succeeded:
            return applying.model_copy(
                update={**execution_fields, "status": ChangeSetStatus.SUCCEEDED}
            )

        rollback = adapter.rollback(receipt.rollback_token, context)
        status = (
            ChangeSetStatus.ROLLED_BACK
            if rollback.succeeded
            else ChangeSetStatus.FAILED
        )
        error = "COMPILE_TEST_FAILED" if rollback.succeeded else "ROLLBACK_FAILED"
        return applying.model_copy(
            update={
                **execution_fields,
                "status": status,
                "rollback_result": rollback,
                "last_error": error,
            }
        )

    def rollback(
        self,
        change_set: CodeChangeSet,
        adapter: UnityCodeChangeAdapter,
        context: AdapterExecutionContext,
    ) -> CodeChangeSet:
        if change_set.status != ChangeSetStatus.SUCCEEDED:
            raise ValueError("Only a succeeded ChangeSet can be explicitly rolled back.")
        if not change_set.rollback_token:
            raise ValueError("ChangeSet has no rollback token.")
        result = adapter.rollback(change_set.rollback_token, context)
        return change_set.model_copy(
            update={
                "status": (
                    ChangeSetStatus.ROLLED_BACK
                    if result.succeeded
                    else ChangeSetStatus.FAILED
                ),
                "rollback_result": result,
                "mode": result.mode,
                "last_error": None if result.succeeded else "ROLLBACK_FAILED",
            }
        )


def _validate_proposal(proposal: CodeChangeProposal) -> None:
    if proposal.mode != ExecutionMode.PLANNED:
        raise CodeChangeProposalError("New code proposals must use planned mode.")
    if "GIT binary patch" in proposal.unified_diff:
        raise CodeChangeProposalError("Binary patches are not valid C# proposals.")
    declared_paths = set(proposal.target_paths)
    if len(declared_paths) != len(proposal.target_paths):
        raise CodeChangeProposalError("Target paths must be unique.")
    for raw_path in declared_paths:
        path = PurePosixPath(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise CodeChangeProposalError(
                f"Target path '{raw_path}' escapes the Unity project boundary."
            )
        if not path.parts or path.parts[0] != "Assets" or path.suffix.lower() != ".cs":
            raise CodeChangeProposalError(
                f"Target path '{raw_path}' must be an Assets/**/*.cs path."
            )
    diff_paths = _read_diff_paths(proposal.unified_diff)
    if diff_paths != declared_paths:
        missing = sorted(declared_paths - diff_paths)
        unexpected = sorted(diff_paths - declared_paths)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("undeclared: " + ", ".join(unexpected))
        raise CodeChangeProposalError(
            "Unified diff scope does not match target_paths (" + "; ".join(details) + ")."
        )


def _read_diff_paths(unified_diff: str) -> set[str]:
    paths = set()
    for line in unified_diff.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        marker = line[4:].split("\t", 1)[0]
        if marker == "/dev/null":
            continue
        if not (marker.startswith("a/") or marker.startswith("b/")):
            raise CodeChangeProposalError(
                f"Unified diff path '{marker}' is not project-relative."
            )
        paths.add(marker[2:])
    if not paths:
        raise CodeChangeProposalError("Unified diff contains no file headers.")
    return paths
