"""Version tree and preview-gated local branch operations."""
from pathlib import Path
from typing import Callable, Literal
from fastapi import APIRouter, HTTPException
from pydantic import Field
from .git_adapter import GitCliAdapter
from .git_models import GitRepositoryState, GitFileChange
from .base import CommitId, ExecutionMode, FrozenModel
from .errors import VersionCollaborationError


class TreeProgress(FrozenModel):
    stage: str
    confirmed_versions: int
    planned_cards: int
    card_branches: int
    milestones: dict[str, str]
    branch_labels: dict[str, str]


class VersionTreeState(GitRepositoryState):
    progress: TreeProgress | None = None


class BranchPreviewRequest(FrozenModel):
    operation: Literal["create", "switch"]
    branch_name: str = Field(min_length=1, max_length=255)
    source_commit: CommitId | None = None


class BranchChangeSet(FrozenModel):
    operation: Literal["create", "switch"]
    branch_name: str
    expected_head: CommitId
    source_commit: CommitId
    current_branch: str | None
    blocked_reasons: tuple[str, ...]
    mode: ExecutionMode = ExecutionMode.LIVE
    dry_run: bool = True


class ApplyBranchRequest(FrozenModel):
    change_set: BranchChangeSet
    confirmed: bool


class BranchOperationResult(FrozenModel):
    current_branch: str
    head_commit: CommitId
    mode: ExecutionMode = ExecutionMode.LIVE


def create_tree_router(project_id: str, resolve_root: Callable[[], Path], progress: Callable[[], TreeProgress | None] = lambda: None) -> APIRouter:
    router = APIRouter(prefix="/api/version-collaboration")

    def repository():
        try:
            root = resolve_root()
            return root, GitCliAdapter([root])
        except (KeyError, ValueError) as error:
            raise HTTPException(409, "当前项目尚未绑定可读取的本地文件夹。") from error

    def preview(body: BranchPreviewRequest) -> BranchChangeSet:
        root, git = repository()
        state = git.inspect(project_id, project_id, root)
        branches = {branch.name: branch for branch in state.branches}
        reasons: list[str] = []
        if not git.valid_branch_name(root, body.branch_name):
            reasons.append("invalid_branch_name")
        if state.dirty:
            reasons.append("dirty_worktree")
        if state.conflicted:
            reasons.append("merge_conflict")
        if body.operation == "create":
            if body.branch_name in branches:
                reasons.append("branch_exists")
            source = body.source_commit or state.version.commit_id
            if source not in {commit.commit_id for commit in state.commits}:
                reasons.append("unknown_source_commit")
                source = state.version.commit_id
        else:
            target = branches.get(body.branch_name)
            if target is None:
                reasons.append("branch_missing")
                source = state.version.commit_id
            else:
                source = target.commit_id
                if target.current:
                    reasons.append("already_current")
        return BranchChangeSet(
            operation=body.operation,
            branch_name=body.branch_name,
            expected_head=state.version.commit_id,
            source_commit=source,
            current_branch=state.version.branch,
            blocked_reasons=tuple(reasons),
        )

    @router.get("/tree", response_model=VersionTreeState)
    def version_tree():
        try:
            root = resolve_root()
        except (KeyError, ValueError) as error:
            raise HTTPException(409, "当前项目尚未绑定可读取的本地文件夹。") from error
        try:
            state = GitCliAdapter([root]).inspect(project_id, project_id, root)
            return VersionTreeState(**state.model_dump(), progress=progress())
        except VersionCollaborationError as error:
            raise HTTPException(409, "暂时无法读取版本树，请检查 Git 仓库是否可用且已有提交。") from error

    @router.get("/tree/commits/{commit_id}/files", response_model=tuple[GitFileChange, ...])
    def commit_files(commit_id: str):
        try:
            root = resolve_root()
            return GitCliAdapter([root]).commit_changes(root, commit_id)
        except (KeyError, ValueError, VersionCollaborationError) as error:
            raise HTTPException(409, "无法读取此提交的变更文件，请刷新版本树后重试。") from error

    @router.post("/tree/branches/preview", response_model=BranchChangeSet)
    def preview_branch(body: BranchPreviewRequest):
        try:
            return preview(body)
        except VersionCollaborationError as error:
            raise HTTPException(409, "无法准备分支操作，请刷新版本树后重试。") from error

    @router.post("/tree/branches/apply", response_model=BranchOperationResult)
    def apply_branch(body: ApplyBranchRequest):
        if not body.confirmed:
            raise HTTPException(409, "请先确认分支操作。")
        current = preview(BranchPreviewRequest(
            operation=body.change_set.operation,
            branch_name=body.change_set.branch_name,
            source_commit=body.change_set.source_commit,
        ))
        if current != body.change_set:
            raise HTTPException(409, "仓库状态已变化，请重新预览分支操作。")
        if current.blocked_reasons:
            raise HTTPException(409, "当前仓库状态不允许执行此分支操作。")
        root, git = repository()
        try:
            if current.operation == "create":
                git.create_branch_and_switch(
                    root, current.branch_name, current.source_commit, current.expected_head
                )
            else:
                git.switch_branch(root, current.branch_name, current.expected_head)
            state = git.inspect(project_id, project_id, root)
            return BranchOperationResult(
                current_branch=state.version.branch or current.branch_name,
                head_commit=state.version.commit_id,
            )
        except VersionCollaborationError as error:
            raise HTTPException(409, "Git 未能完成分支操作，请刷新后检查仓库状态。") from error

    return router
