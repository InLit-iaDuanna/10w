"""Version-one payloads for module-owned facts; core owns the event envelope."""

from __future__ import annotations

from typing import Dict, List, Type

from pydantic import BaseModel

from .enums import CandidateStatus, DeploymentStatus, ExecutionMode
from .models_common import GitCommit, Sha256Digest, StableId


class BuildManifestRecordedPayload(BaseModel):
    manifest_id: StableId
    build_run_id: StableId
    project_id: StableId
    game_id: StableId
    source_commit: GitCommit
    manifest_checksum: Sha256Digest
    mode: ExecutionMode


class ReleaseCandidateCreatedPayload(BaseModel):
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    source_commit: GitCommit
    manifest_ids: List[StableId]
    status: CandidateStatus
    mode: ExecutionMode


class ReleaseCandidateReadiedPayload(BaseModel):
    candidate_id: StableId
    scope_fingerprint: Sha256Digest
    approval_ids: List[StableId]
    mode: ExecutionMode


class ReleaseDeploymentPayload(BaseModel):
    deployment_id: StableId
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    status: DeploymentStatus
    attempt: int
    operation_scope_fingerprint: Sha256Digest
    deployment_mode: ExecutionMode
    artifact_source_mode: ExecutionMode


class ReleaseRollbackExecutedPayload(BaseModel):
    rollback_plan_id: StableId
    previous_deployment_id: StableId
    activation_deployment_id: StableId
    activated_candidate_id: StableId
    mode: ExecutionMode


EVENT_PAYLOAD_MODELS: Dict[str, Type[BaseModel]] = {
    "build.manifest.recorded@1": BuildManifestRecordedPayload,
    "release.candidate.created@1": ReleaseCandidateCreatedPayload,
    "release.candidate.readied@1": ReleaseCandidateReadiedPayload,
    "release.deployment.succeeded@1": ReleaseDeploymentPayload,
    "release.deployment.failed@1": ReleaseDeploymentPayload,
    "release.rollback.executed@1": ReleaseRollbackExecutedPayload,
}
