"""Public façade for build-release application behavior."""

from __future__ import annotations

from typing import Dict, Optional

from .authority import UnavailableReleaseAuthority
from .candidate_service import CandidateService
from .deployment_service import DeploymentService
from .patch_note_service import PatchNoteService
from .rollback_service import RollbackService
from .models_build import BuildManifest
from .models_release import (
    Deployment,
    DeploymentPlan,
    FeedbackLink,
    PatchNote,
    ReleaseCandidate,
    RollbackPlan,
)
from .ports import ArtifactCatalog, Clock, DeploymentAdapter, ReleaseAuthority
from .repository import InMemoryReleaseRepository
from .requests import (
    CandidateApprovalRequest,
    CreateCandidateRequest,
    CreateRollbackPlanRequest,
    DeployRequest,
    EditPatchNoteRequest,
    ExecuteRollbackRequest,
    GeneratePatchNoteRequest,
    PrepareDeploymentRequest,
    RecordBuildRequest,
    RetryDeploymentRequest,
)
from .enums import DeploymentTarget


class BuildReleaseService:
    def __init__(
        self,
        repository: InMemoryReleaseRepository,
        artifact_catalog: ArtifactCatalog,
        adapters: Dict[DeploymentTarget, DeploymentAdapter],
        clock: Clock,
        authority: Optional[ReleaseAuthority] = None,
    ) -> None:
        release_authority = authority or UnavailableReleaseAuthority()
        self.repository = repository
        self._candidates = CandidateService(
            repository, artifact_catalog, clock, release_authority
        )
        self._patch_notes = PatchNoteService(repository, clock)
        self._deployments = DeploymentService(
            repository, artifact_catalog, adapters, clock, release_authority
        )
        self._rollbacks = RollbackService(
            repository, artifact_catalog, adapters, clock, release_authority
        )

    def record_build(self, request: RecordBuildRequest) -> BuildManifest:
        return self._candidates.record_build(request)

    def create_candidate(
        self, request: CreateCandidateRequest
    ) -> ReleaseCandidate:
        return self._candidates.create_candidate(request)

    def approve_candidate(
        self, request: CandidateApprovalRequest
    ) -> ReleaseCandidate:
        return self._candidates.approve_candidate(request)

    def generate_patch_note(self, request: GeneratePatchNoteRequest) -> PatchNote:
        return self._patch_notes.generate(request)

    def edit_patch_note(self, request: EditPatchNoteRequest) -> PatchNote:
        return self._patch_notes.edit(request)

    def add_feedback_link(self, link: FeedbackLink) -> FeedbackLink:
        return self._candidates.add_feedback_link(link)

    def prepare_deployment(
        self, request: PrepareDeploymentRequest
    ) -> DeploymentPlan:
        return self._deployments.prepare_deployment(request)

    def deploy(self, request: DeployRequest) -> Deployment:
        return self._deployments.deploy(request)

    def retry_deployment(
        self, request: RetryDeploymentRequest
    ) -> Deployment:
        return self._deployments.retry_deployment(request)

    def create_rollback_plan(
        self, request: CreateRollbackPlanRequest
    ) -> RollbackPlan:
        return self._rollbacks.create_plan(request)

    def execute_rollback(
        self, request: ExecuteRollbackRequest
    ) -> RollbackPlan:
        return self._rollbacks.execute(request)
