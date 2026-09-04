"""Typed command payloads accepted by the module service and API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from .enums import DeploymentTarget, ExecutionMode
from .models_build import BuildManifest, BuildMatrix, BuildRun
from .models_common import Approval, ApprovedChangeSet, DomainModel, StableId
from .models_release import PatchNoteEntry, ReleaseGate


class RecordBuildRequest(DomainModel):
    matrix: BuildMatrix
    run: BuildRun
    manifest: BuildManifest


class CreateCandidateRequest(DomainModel):
    candidate_id: StableId
    manifest_ids: List[StableId] = Field(min_length=2)
    gates: List[ReleaseGate]
    approved_change_set_ids: List[StableId]


class CandidateApprovalRequest(DomainModel):
    candidate_id: StableId
    approval: Approval


class GeneratePatchNoteRequest(DomainModel):
    patch_note_id: StableId
    candidate_id: StableId
    title: str = Field(min_length=1, max_length=160)
    change_sets: List[ApprovedChangeSet]


class EditPatchNoteRequest(DomainModel):
    patch_note_id: StableId
    editor_id: StableId
    entries: List[PatchNoteEntry]
    editorial_note: Optional[str] = Field(default=None, max_length=1000)


class DeployRequest(DomainModel):
    deployment_id: StableId
    candidate_id: StableId
    target: DeploymentTarget
    patch_note_id: StableId
    patch_note_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)
    expected_mode: ExecutionMode
    mark_known_good: bool = False
    approvals: List[Approval]


class PrepareDeploymentRequest(DomainModel):
    deployment_id: StableId
    candidate_id: StableId
    target: DeploymentTarget
    patch_note_id: StableId
    patch_note_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)
    expected_mode: ExecutionMode
    mark_known_good: bool = False


class RetryDeploymentRequest(DomainModel):
    deployment_id: StableId
    approvals: List[Approval]


class CreateRollbackPlanRequest(DomainModel):
    rollback_plan_id: StableId
    activation_deployment_id: StableId
    current_deployment_id: StableId
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ExecuteRollbackRequest(DomainModel):
    rollback_plan_id: StableId
    activation_deployment_id: StableId
    idempotency_key: str = Field(min_length=8, max_length=160)
    approvals: List[Approval]
