from __future__ import annotations

from typing import Literal

from .schemas import (
    ExecutionMode,
    Issue,
    RestorationContext,
    RunId,
    StableId,
    StrictModel,
)


class RestoreIssueCommand(StrictModel):
    command_id: Literal["workbench.context.restore"] = "workbench.context.restore"
    issue_id: StableId
    run_id: RunId
    build_id: StableId
    execution_mode: ExecutionMode
    open_editor_id: Literal["playtest.game-view"] = "playtest.game-view"
    context: RestorationContext
    require_confirmation: bool


def create_restore_command(issue: Issue) -> RestoreIssueCommand:
    return RestoreIssueCommand(
        issue_id=issue.issue_id,
        run_id=issue.run_id,
        build_id=issue.evidence.build_id,
        execution_mode=issue.execution_mode,
        context=issue.restoration,
        require_confirmation=issue.execution_mode != ExecutionMode.LIVE,
    )
