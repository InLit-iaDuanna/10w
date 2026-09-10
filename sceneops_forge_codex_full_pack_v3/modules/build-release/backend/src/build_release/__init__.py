"""Public backend entrypoint for the SceneOps Build and Release module."""

from .jobs import JOB_DEFINITIONS
from .router import create_router
from .schemas import (
    Approval,
    ApprovedChangeSet,
    ArtifactRef,
    BuildManifest,
    BuildMatrix,
    BuildRun,
    BuildTarget,
    Deployment,
    DeploymentPlan,
    FeedbackLink,
    PatchNote,
    ReleaseCandidate,
    ReleaseGate,
    RollbackPlan,
    VersionBinding,
)
from .service import BuildReleaseService
from .ports import AuthorityVerification, ReleaseAuthority

__all__ = [
    "Approval",
    "ApprovedChangeSet",
    "ArtifactRef",
    "AuthorityVerification",
    "BuildManifest",
    "BuildMatrix",
    "BuildReleaseService",
    "BuildRun",
    "BuildTarget",
    "Deployment",
    "DeploymentPlan",
    "FeedbackLink",
    "JOB_DEFINITIONS",
    "PatchNote",
    "ReleaseCandidate",
    "ReleaseGate",
    "ReleaseAuthority",
    "RollbackPlan",
    "VersionBinding",
    "create_router",
]

from .workbench_service import UnityBuildWorkbenchService
from .workbench_router import create_workbench_router

__all__ += ['UnityBuildWorkbenchService', 'create_workbench_router']

# Local playable exports are independent of formal release approvals.
from .export_models import CreateExportRequest, ExportTask, ExportMessageRequest, ExportVerificationRequest, ExportConsentRequest
from .export_service import ExportService
from .export_router import create_export_router

__all__ += ['CreateExportRequest', 'ExportTask', 'ExportMessageRequest', 'ExportVerificationRequest', 'ExportService', 'create_export_router', 'ExportConsentRequest']
