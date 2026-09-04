from __future__ import annotations

from typing import Dict, List

from .schemas import BackpinStatus, ChangeSetProposal, Issue, JsonScalar


class ChangeSetProposalError(ValueError):
    code = "CHANGESET_PROPOSAL_INVALID"


class BackpinNotConfirmedError(ChangeSetProposalError):
    code = "BACKPIN_NOT_RESOLVED"


def propose_change_set(
    issue: Issue,
    proposal_id: str,
    base_version: str,
    target_integration: str,
    previous_values: Dict[str, JsonScalar],
    proposed_values: Dict[str, JsonScalar],
    rationale: str,
    expected_result: str,
    impact_scope: str,
    risk: str,
    validation_plan: List[str],
    rollback_plan: List[str],
    approval_requirements: List[str],
) -> ChangeSetProposal:
    backpin = issue.backpin
    if (
        backpin.status != BackpinStatus.RESOLVED
        or not backpin.target_id
        or not backpin.owning_module
        or not backpin.reviewed_by
        or not backpin.reviewed_at
    ):
        raise BackpinNotConfirmedError(
            "a ChangeSet proposal requires a reviewed, unambiguous source target"
        )
    if previous_values == proposed_values:
        raise ChangeSetProposalError(
            "a ChangeSet proposal must describe an actual value change"
        )
    return ChangeSetProposal(
        proposal_id=proposal_id,
        owning_module=backpin.owning_module,
        base_version=base_version,
        target_integration=target_integration,
        target_object_ids=[backpin.target_id],
        previous_values=previous_values,
        proposed_values=proposed_values,
        rationale=rationale,
        expected_result=expected_result,
        impact_scope=impact_scope,
        risk=risk,
        validation_plan=validation_plan,
        rollback_plan=rollback_plan,
        approval_requirements=approval_requirements,
        source_issue_id=issue.issue_id,
    )
