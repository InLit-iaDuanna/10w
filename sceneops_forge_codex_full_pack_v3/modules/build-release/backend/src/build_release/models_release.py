"""Release gate, candidate, deployment, notes, and rollback contracts."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from .checksum import canonical_sha256
from .enums import (
    BuildProfile,
    CandidateStatus,
    DeploymentStatus,
    DeploymentTarget,
    ExecutionMode,
    FeedbackKind,
    GateCategory,
    GateStatus,
    PatchNoteStatus,
    RollbackStatus,
)
from .models_common import (
    Approval,
    ArtifactRef,
    GateEvidence,
    GitCommit,
    Sha256Digest,
    StableId,
    UtcModel,
)


class ReleaseGate(UtcModel):
    gate_id: StableId
    category: GateCategory
    status: GateStatus
    blocking: bool = True
    source_commit: GitCommit
    evidence: List[GateEvidence] = Field(default_factory=list)
    mode: ExecutionMode
    summary: str = Field(min_length=1, max_length=500)
    evaluated_at: datetime

    @model_validator(mode="after")
    def evidence_matches_gate(self) -> "ReleaseGate":
        if self.status == GateStatus.PASSED and not self.evidence:
            raise ValueError("passed gates require evidence")
        for item in self.evidence:
            if item.category != self.category:
                raise ValueError("gate evidence category must match its gate")
            if item.source_commit.lower() != self.source_commit.lower():
                raise ValueError("gate evidence source_commit must match its gate")
        if self.status == GateStatus.PASSED:
            if any(item.result != GateStatus.PASSED for item in self.evidence):
                raise ValueError("passed gates cannot contain non-passing evidence")
        return self


class GateBlocker(UtcModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    category: Optional[GateCategory] = None
    gate_id: Optional[StableId] = None
    detected_at: datetime


class GateReport(UtcModel):
    source_commit: GitCommit
    required_categories: List[GateCategory]
    passed_categories: List[GateCategory]
    blockers: List[GateBlocker]
    warnings: List[GateBlocker]
    source_modes: List[ExecutionMode]
    mode: ExecutionMode
    can_release: bool
    evaluated_at: datetime

    @model_validator(mode="after")
    def release_decision_matches_blockers(self) -> "GateReport":
        if self.can_release == bool(self.blockers):
            raise ValueError("can_release must be true exactly when no blockers exist")
        return self


class ReproducibilityEvidence(UtcModel):
    manifest_ids: List[StableId] = Field(min_length=2)
    input_fingerprint: Sha256Digest
    output_fingerprint: Sha256Digest
    inputs_match: bool
    outputs_match: bool
    verified_at: datetime

    @field_validator("manifest_ids")
    @classmethod
    def manifest_ids_are_unique(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("reproducibility manifests must be distinct")
        return value


class ReleaseCandidate(UtcModel):
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    profile: BuildProfile
    source_commit: GitCommit
    build_manifest_ids: List[StableId] = Field(min_length=2)
    release_artifact: ArtifactRef
    reproducibility: ReproducibilityEvidence
    gates: List[ReleaseGate]
    gate_report: GateReport
    approved_change_set_ids: List[StableId]
    required_approval_roles: List[str]
    approvals: List[Approval]
    scope_fingerprint: Sha256Digest
    source_modes: List[ExecutionMode]
    mode: ExecutionMode
    status: CandidateStatus
    blockers: List[str]
    created_at: datetime
    readied_at: Optional[datetime] = None

    @model_validator(mode="after")
    def ready_candidate_is_complete(self) -> "ReleaseCandidate":
        if self.release_artifact.source_commit.lower() != self.source_commit.lower():
            raise ValueError("candidate artifact must match source_commit")
        if self.status == CandidateStatus.READY:
            if self.blockers or not self.gate_report.can_release:
                raise ValueError("ready candidate cannot have blockers")
            if not self.reproducibility.inputs_match or not self.reproducibility.outputs_match:
                raise ValueError("ready candidate requires verified reproducibility")
            approved_roles = {
                approval.role
                for approval in self.approvals
                if approval.decision.value == "approved"
                and approval.scope_fingerprint == self.scope_fingerprint
            }
            if not set(self.required_approval_roles).issubset(approved_roles):
                raise ValueError("ready candidate lacks required approvals")
            if self.readied_at is None:
                raise ValueError("ready candidate requires readied_at")
        if self.status == CandidateStatus.BLOCKED and self.mode != ExecutionMode.BLOCKED:
            raise ValueError("blocked candidate must use blocked mode")
        if self.status in {
            CandidateStatus.READY,
            CandidateStatus.DEPLOYED,
            CandidateStatus.ROLLED_BACK,
        } and self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("ready or historical candidates require an executed source mode")
        return self


class DeploymentAttempt(UtcModel):
    attempt: int = Field(ge=1)
    status: DeploymentStatus
    mode: ExecutionMode
    started_at: datetime
    finished_at: datetime
    deployed_uri: Optional[str] = None
    deployed_checksum: Optional[Sha256Digest] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    logs: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def attempt_outcome_is_consistent(self) -> "DeploymentAttempt":
        if self.status == DeploymentStatus.SUCCEEDED:
            if not self.deployed_uri or not self.deployed_checksum:
                raise ValueError("successful attempts require deployed artifact evidence")
            if self.error_code or self.error_message:
                raise ValueError("successful attempts cannot include an error")
        if self.status == DeploymentStatus.FAILED:
            if not self.error_code or not self.error_message:
                raise ValueError("failed attempts require a structured error")
        return self


class Deployment(UtcModel):
    deployment_id: StableId
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    profile: BuildProfile
    build_target_id: StableId
    target: DeploymentTarget
    source_commit: GitCommit
    candidate_scope_fingerprint: Sha256Digest
    operation_scope_fingerprint: Sha256Digest
    base_deployment_id: Optional[StableId] = None
    idempotency_key: str = Field(min_length=8, max_length=160)
    patch_note_id: StableId
    patch_note_revision: int = Field(ge=1)
    patch_note_checksum: Sha256Digest
    requested_known_good: bool
    status: DeploymentStatus
    mode: ExecutionMode
    artifact_source_mode: ExecutionMode
    approvals: List[Approval]
    attempts: List[DeploymentAttempt] = Field(min_length=1)
    known_good: bool
    rollback_of_deployment_id: Optional[StableId] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def deployment_history_is_consistent(self) -> "Deployment":
        numbers = [attempt.attempt for attempt in self.attempts]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("deployment attempt numbers must be contiguous")
        last_status = self.attempts[-1].status
        if self.status == DeploymentStatus.SUCCEEDED and last_status != DeploymentStatus.SUCCEEDED:
            raise ValueError("successful deployment requires a successful final attempt")
        if self.status == DeploymentStatus.FAILED and last_status != DeploymentStatus.FAILED:
            raise ValueError("failed deployment requires a failed final attempt")
        if self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            raise ValueError("deployment records require an executed adapter mode")
        return self


class DeploymentPlan(UtcModel):
    deployment_id: StableId
    candidate_id: StableId
    target: DeploymentTarget
    patch_note_id: StableId
    patch_note_revision: int = Field(ge=1)
    patch_note_checksum: Sha256Digest
    base_deployment_id: Optional[StableId] = None
    operation_scope_fingerprint: Sha256Digest
    required_approval_roles: List[str] = Field(min_length=1)
    mark_known_good_approval_roles: List[str]
    expected_mode: ExecutionMode
    adapter_id: StableId
    adapter_version: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=512)
    created_at: datetime


class PatchNoteEntry(UtcModel):
    change_set_id: StableId
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=1000)
    approval_ids: List[StableId] = Field(min_length=1)
    approved_at: datetime


class PatchNoteEdit(UtcModel):
    revision: int = Field(ge=2)
    editor_id: StableId
    edited_at: datetime
    title: str = Field(min_length=1, max_length=160)
    entries: List[PatchNoteEntry]
    editorial_note: Optional[str] = Field(default=None, max_length=1000)
    content_checksum: Sha256Digest

    @model_validator(mode="after")
    def edit_checksum_matches_snapshot(self) -> "PatchNoteEdit":
        expected = patch_note_content_checksum(
            self.title, self.entries, self.editorial_note
        )
        if self.content_checksum != expected:
            raise ValueError("patch-note edit checksum does not match its snapshot")
        return self


class PatchNote(UtcModel):
    patch_note_id: StableId
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    title: str = Field(min_length=1, max_length=160)
    entries: List[PatchNoteEntry]
    original_entries: List[PatchNoteEntry]
    editorial_note: Optional[str] = Field(default=None, max_length=1000)
    revision: int = Field(ge=1)
    original_content_checksum: Sha256Digest
    content_checksum: Sha256Digest
    status: PatchNoteStatus
    edits: List[PatchNoteEdit] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("entries", "original_entries")
    @classmethod
    def entries_keep_unique_change_set_anchors(
        cls, value: List[PatchNoteEntry]
    ) -> List[PatchNoteEntry]:
        ids = [entry.change_set_id for entry in value]
        if len(ids) != len(set(ids)):
            raise ValueError("patch-note ChangeSet anchors must be unique")
        return value

    @model_validator(mode="after")
    def revision_history_is_reconstructable(self) -> "PatchNote":
        original_checksum = patch_note_content_checksum(
            self.title, self.original_entries, None
        )
        if self.original_content_checksum != original_checksum:
            raise ValueError("original patch-note checksum does not match its snapshot")
        current_checksum = patch_note_content_checksum(
            self.title, self.entries, self.editorial_note
        )
        if self.content_checksum != current_checksum:
            raise ValueError("patch-note checksum does not match current content")
        if [item.revision for item in self.edits] != list(
            range(2, self.revision + 1)
        ):
            raise ValueError("patch-note edit revisions must be contiguous")
        if self.edits:
            current = self.edits[-1]
            if (
                current.title != self.title
                or current.entries != self.entries
                or current.editorial_note != self.editorial_note
                or current.content_checksum != self.content_checksum
            ):
                raise ValueError("latest patch-note edit must match current content")
        elif self.revision != 1:
            raise ValueError("patch-note revisions after one require edit snapshots")
        return self


def patch_note_content_checksum(
    title: str,
    entries: List[PatchNoteEntry],
    editorial_note: Optional[str],
) -> str:
    return canonical_sha256(
        {
            "title": title,
            "entries": [item.model_dump(mode="json") for item in entries],
            "editorial_note": editorial_note,
        }
    )


class FeedbackLink(UtcModel):
    feedback_link_id: StableId
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    kind: FeedbackKind
    target_id: StableId
    deployment_id: Optional[StableId] = None
    label: str = Field(min_length=1, max_length=160)
    created_at: datetime


class RollbackPlan(UtcModel):
    rollback_plan_id: StableId
    activation_deployment_id: StableId
    current_deployment_id: StableId
    target_deployment_id: StableId
    target_candidate_id: StableId
    project_id: StableId
    game_id: StableId
    deployment_target: DeploymentTarget
    profile: BuildProfile
    current_scope_fingerprint: Sha256Digest
    operation_scope_fingerprint: Sha256Digest
    idempotency_key: str = Field(min_length=8, max_length=160)
    adapter_id: StableId
    adapter_version: str = Field(min_length=1, max_length=80)
    expected_mode: ExecutionMode
    destination: str = Field(min_length=1, max_length=512)
    target_patch_note_checksum: Sha256Digest
    reason: str = Field(min_length=1, max_length=500)
    required_approval_roles: List[str] = Field(min_length=1)
    approvals: List[Approval]
    status: RollbackStatus
    mode: ExecutionMode
    attempts: List[DeploymentAttempt] = Field(default_factory=list)
    created_at: datetime
    executed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def rollback_state_is_consistent(self) -> "RollbackPlan":
        if self.status == RollbackStatus.WAITING_APPROVAL:
            if self.mode != ExecutionMode.PLANNED or self.attempts:
                raise ValueError("waiting rollback must be planned with no attempts")
        if self.status == RollbackStatus.SUCCEEDED:
            if self.mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
                raise ValueError("successful rollback requires an executed mode")
            if not self.attempts or self.attempts[-1].status != DeploymentStatus.SUCCEEDED:
                raise ValueError("successful rollback requires successful attempt evidence")
        if self.status == RollbackStatus.FAILED:
            if not self.attempts or self.attempts[-1].status != DeploymentStatus.FAILED:
                raise ValueError("failed rollback requires failed attempt evidence")
        return self
