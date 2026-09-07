"""Public backend surface for the Asset Factory module."""

from .adapter import BlenderAdapterPort
from .authorization import (
    AssetApprovalAuthority,
    AssetApprovalRecord,
    InMemoryAssetApprovalAuthority,
    InMemoryProjectRootRegistry,
    ProjectArtifactVerifier,
    ProjectRootRegistry,
    canonical_command_scope,
)
from .errors import PipelineConflictError, PipelineExecutionError, PipelineNotFoundError
from .finalization import FinalizedCandidateStore, InMemoryFinalizedCandidateStore
from .jobs import JOBS, JobDefinition
from .router import create_router
from .run_ledger import CancellationToken, InMemoryRequestLedger, RequestLedgerPort
from .schemas import (
    AssetChangeSet,
    ChangeSetState,
    PipelineErrorResponse,
    PipelineRequest,
    PipelineRun,
    PipelineState,
    ProcessingLog,
    ProcessingStep,
    ProcessingStepKind,
    RetryPolicy,
    RiskLevel,
    StepState,
)
from .service import AssetPipelineService

__all__ = [
    "AssetChangeSet",
    "AssetApprovalAuthority",
    "AssetApprovalRecord",
    "AssetPipelineService",
    "BlenderAdapterPort",
    "CancellationToken",
    "ChangeSetState",
    "FinalizedCandidateStore",
    "InMemoryAssetApprovalAuthority",
    "InMemoryFinalizedCandidateStore",
    "InMemoryProjectRootRegistry",
    "InMemoryRequestLedger",
    "JOBS",
    "JobDefinition",
    "PipelineConflictError",
    "PipelineErrorResponse",
    "PipelineExecutionError",
    "PipelineNotFoundError",
    "PipelineRequest",
    "PipelineRun",
    "PipelineState",
    "ProcessingLog",
    "ProcessingStep",
    "ProcessingStepKind",
    "ProjectArtifactVerifier",
    "ProjectRootRegistry",
    "RequestLedgerPort",
    "RetryPolicy",
    "RiskLevel",
    "StepState",
    "create_router",
    "canonical_command_scope",
]

from .concept_handoff import ConceptAssetHandoff, asset_spec_from_concept
from .workflow import build_workflow_plan
from .lab_service import ConceptAssetLab, LabAction, LabSnapshot, create_lab_router
from .card_asset_models import (
    CardAssetError,
    CardAssetList,
    CardAssetProposal,
    CardAssetRecord,
    CardAssetReference,
    CardAssetVersion,
    LiveModelUpdateRequest,
    LiveModelUpdateResult,
    ModelPlanContent,
    ModelPlanRequest,
    NormalizeRequest,
    PrimitivePart,
    SaveToLibraryRequest,
)
from .card_asset_router import create_card_asset_router
from .card_asset_service import CardAssetService

__all__ += ["ConceptAssetHandoff", "asset_spec_from_concept", "build_workflow_plan",
            "ConceptAssetLab", "LabAction", "LabSnapshot", "create_lab_router",
            "CardAssetError", "CardAssetList", "CardAssetProposal", "CardAssetRecord",
            "CardAssetReference", "CardAssetVersion", "LiveModelUpdateRequest", "LiveModelUpdateResult",
            "ModelPlanContent", "ModelPlanRequest",
            "NormalizeRequest", "PrimitivePart", "SaveToLibraryRequest",
            "CardAssetService", "create_card_asset_router"]

from .native_source import inspect_native_glb, preserve_native_source
