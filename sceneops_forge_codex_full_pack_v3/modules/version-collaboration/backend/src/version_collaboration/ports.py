from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Protocol

from pydantic import Field

from .base import ExecutionMode, FrozenModel, StableId, VersionReference
from .git_models import (
    GitCapabilities,
    GitRepositoryState,
    GitRollbackCommand,
    GitRollbackResult,
    GitVersionDiff,
    IntegrationHealth,
    LfsLockResult,
    LfsUnlockResult,
    RollbackPreview,
)


class ChangeSetDraft(FrozenModel):
    intent: str = Field(default="rollback", pattern=r"^rollback$")
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    base_version: VersionReference
    target_integration: str = Field(default="git", pattern=r"^git$")
    target_objects: tuple[str, ...]
    previous_values: dict[str, str]
    proposed_values: dict[str, str]
    rationale: str
    expected_result: str
    impact_scope: str
    risk: str
    validation_plan: tuple[str, ...]
    rollback_plan: str
    approval_requirements: tuple[str, ...]


class ChangeSetReference(FrozenModel):
    change_set_id: StableId
    version: int = Field(ge=1)
    state: str = Field(pattern=r"^(awaiting_approval|approved|rejected|executed)$")
    mode: ExecutionMode


class ApprovalBinding(FrozenModel):
    review_id: StableId
    review_revision_id: StableId
    diff_bundle_id: StableId
    subject_kind: str = Field(pattern=r"^(review|changeset|rollback)$")
    subject_id: StableId
    subject_version: int = Field(ge=1)
    base_version: VersionReference


class VerifiedApproval(FrozenModel):
    approval_id: StableId
    binding: ApprovalBinding
    approver_id: StableId
    outcome: str = Field(pattern=r"^(approved|rejected)$")
    rationale: str
    evidence_ids: tuple[StableId, ...]
    approved_at: datetime
    mode: ExecutionMode


class GitAdapter(Protocol):
    def health_check(self, project_root: Path) -> IntegrationHealth: ...

    def capabilities(self, project_root: Path) -> GitCapabilities: ...

    def inspect(self, project_id: str, repository_id: str, project_root: Path) -> GitRepositoryState: ...

    def compare_versions(
        self,
        repository_id: str,
        project_root: Path,
        base_commit: str,
        target_commit: str,
    ) -> GitVersionDiff: ...

    def dry_run_rollback(self, project_root: Path, command: GitRollbackCommand) -> RollbackPreview: ...

    def acquire_lfs_lock(
        self, project_root: Path, path: str, operation_id: str
    ) -> LfsLockResult: ...

    def inspect_lfs_lock(
        self, project_root: Path, path: str
    ) -> LfsLockResult | None: ...

    def release_lfs_lock(
        self,
        project_root: Path,
        external_lock_id: str,
        expected_path: str,
        operation_id: str,
    ) -> LfsUnlockResult: ...

    def execute_rollback(
        self,
        project_root: Path,
        command: GitRollbackCommand,
        *,
        cancellation: Event | None = None,
    ) -> GitRollbackResult: ...


class ChangeSetGateway(Protocol):
    def create(self, draft: ChangeSetDraft) -> ChangeSetReference: ...


class ApprovalVerifier(Protocol):
    def verify(self, approval_id: str, binding: ApprovalBinding) -> VerifiedApproval: ...


class EventPublisher(Protocol):
    def publish(self, event: object) -> None: ...


class UnavailableChangeSetGateway:
    def create(self, draft: ChangeSetDraft) -> ChangeSetReference:
        from .errors import ErrorCode, VersionCollaborationError

        raise VersionCollaborationError(
            ErrorCode.INVALID_STATE,
            "Core ChangeSet service is not connected.",
            details={
                "review_id": draft.review_id,
                "integration_id": "core-changeset",
                "mode": ExecutionMode.BLOCKED.value,
            },
            suggested_actions=("integration.open",),
        )


class UnavailableApprovalVerifier:
    def verify(self, approval_id: str, binding: ApprovalBinding) -> VerifiedApproval:
        from .errors import ErrorCode, VersionCollaborationError

        raise VersionCollaborationError(
            ErrorCode.APPROVAL_REQUIRED,
            "Core approval service is not connected; mutation remains blocked.",
            details={
                "approval_id": approval_id,
                "subject_id": binding.subject_id,
                "integration_id": "core-approval",
                "mode": ExecutionMode.BLOCKED.value,
            },
            suggested_actions=("integration.open", "review.approval.open"),
        )
