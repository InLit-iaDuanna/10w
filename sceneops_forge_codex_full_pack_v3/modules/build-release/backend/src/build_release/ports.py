"""Typed adapter and clock ports; vendor types never enter the domain service."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional, Protocol

from pydantic import Field, model_validator

from .enums import DeploymentTarget, ExecutionMode
from .models_build import BuildManifest, BuildMatrix, BuildRun
from .models_common import (
    Approval,
    ArtifactRef,
    DomainModel,
    Sha256Digest,
    StableId,
    UtcModel,
)


class Clock(Protocol):
    def now(self) -> datetime:
        ...


class ArtifactInspection(DomainModel):
    artifact_id: StableId
    available: bool
    checksum_matches: bool
    size_matches: bool
    observed_checksum: Optional[Sha256Digest] = None
    observed_size_bytes: Optional[int] = Field(default=None, ge=0)
    reason: str = Field(min_length=1, max_length=500)


class ArtifactCatalog(Protocol):
    def inspect(self, artifact: ArtifactRef) -> ArtifactInspection:
        ...


class AuthorityVerification(DomainModel):
    verified: bool
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class ReleaseAuthority(Protocol):
    """Trusted boundary implemented by Git/provenance and approval owners."""

    def verify_source(
        self,
        matrix: BuildMatrix,
        run: BuildRun,
        manifest: BuildManifest,
    ) -> AuthorityVerification:
        ...

    def verify_approval(self, approval: Approval) -> AuthorityVerification:
        ...


class AdapterCapabilities(DomainModel):
    adapter_id: StableId
    adapter_version: str = Field(min_length=1, max_length=80)
    targets: List[DeploymentTarget]
    execution_mode: ExecutionMode
    supports_dry_run: bool
    supports_rollback: bool


class IntegrationHealth(DomainModel):
    healthy: bool
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class DeploymentPreview(DomainModel):
    target: DeploymentTarget
    destination: str = Field(min_length=1, max_length=512)
    artifact_id: StableId
    source_checksum: Sha256Digest
    would_activate: bool
    mode: ExecutionMode


class DeploymentCommand(DomainModel):
    operation_id: StableId
    candidate_id: StableId
    project_id: StableId
    game_id: StableId
    build_target_id: StableId
    target: DeploymentTarget
    artifact: ArtifactRef
    idempotency_key: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def artifact_scope_matches_command(self) -> "DeploymentCommand":
        if (
            self.artifact.project_id != self.project_id
            or self.artifact.game_id != self.game_id
        ):
            raise ValueError("deployment artifact must match project and game scope")
        return self


class AdapterProgress(UtcModel):
    operation_id: StableId
    sequence: int = Field(ge=1)
    phase: str = Field(min_length=1, max_length=80)
    percent: int = Field(ge=0, le=100)
    message: str = Field(min_length=1, max_length=500)
    occurred_at: datetime


class AdapterResult(DomainModel):
    operation_id: StableId
    mode: ExecutionMode
    deployed_uri: str = Field(min_length=1, max_length=512)
    deployed_checksum: Sha256Digest
    logs: List[str]
    adapter_id: StableId
    adapter_version: str = Field(min_length=1, max_length=80)


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool:
        ...


ProgressSink = Callable[[AdapterProgress], None]


class DeploymentAdapter(Protocol):
    def capabilities(self) -> AdapterCapabilities:
        ...

    def health_check(self) -> IntegrationHealth:
        ...

    def dry_run(self, command: DeploymentCommand) -> DeploymentPreview:
        ...

    def execute(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        ...

    def rollback(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        ...
