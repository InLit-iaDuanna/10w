"""Application service for command execution and restore proposals."""

from __future__ import annotations

from threading import Event
from typing import Optional

from .adapter import UnityAdapter
from .contracts import (
    ApprovalState,
    ChangePreview,
    ChangeSet,
    CommandRequest,
    CommandResult,
    ExecutionContext,
)


class UnityEngineService:
    def __init__(self, adapter: UnityAdapter) -> None:
        self.adapter = adapter

    def preview(
        self, request: CommandRequest, context: ExecutionContext
    ) -> ChangePreview:
        return self.adapter.dry_run(request, context)

    def execute(
        self,
        request: CommandRequest,
        context: ExecutionContext,
        cancellation: Optional[Event] = None,
    ) -> CommandResult:
        return self.adapter.execute(request, context, cancellation)

    def propose_restore(
        self,
        original: ChangeSet,
        *,
        restore_change_set_id: str,
        current_base_version: str,
    ) -> ChangeSet:
        return ChangeSet(
            change_set_id=restore_change_set_id,
            base_version=current_base_version,
            target_integration="unity",
            command=original.command,
            target_object_ids=list(original.target_object_ids),
            previous_values=dict(original.proposed_values),
            proposed_values=dict(original.previous_values),
            rationale=f"Restore proposal for {original.change_set_id}.",
            expected_result="Restore the approved Unity values captured before the change.",
            impact_scope=original.impact_scope,
            risk=original.risk,
            validation_plan=list(original.validation_plan),
            rollback_plan=[f"Reapply approved ChangeSet {original.change_set_id}."],
            approval_state=ApprovalState.PENDING,
        )
