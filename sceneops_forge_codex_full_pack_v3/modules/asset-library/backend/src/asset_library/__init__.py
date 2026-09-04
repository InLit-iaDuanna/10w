"""Public backend surface for the Asset Library module."""

from .repository import AssetRepository, InMemoryAssetRepository
from .router import create_router
from .schemas import (
    AIProvenance,
    ArtifactOutput,
    ArtifactProvenance,
    AssetObjectIdentity,
    AssetRecord,
    AssetSearchFilter,
    AssetSpec,
    AssetVersion,
    ExecutionMode,
    GateStatus,
    GeometryMetrics,
    PublicationRequest,
    PublicationStatus,
    QualityGate,
    SourceAsset,
    UnityStatus,
    UsageReference,
    Vector3Meters,
)
from .service import AssetLibraryService, AssetNotFoundError, PublicationBlockedError
from .verification import (
    ArtifactVerifier,
    FinalizedCandidateResolver,
    PublicationApprovalVerifier,
)

__all__ = [
    "AIProvenance",
    "ArtifactOutput",
    "ArtifactProvenance",
    "AssetLibraryService",
    "AssetNotFoundError",
    "AssetObjectIdentity",
    "AssetRecord",
    "AssetRepository",
    "AssetSearchFilter",
    "AssetSpec",
    "AssetVersion",
    "ArtifactVerifier",
    "ExecutionMode",
    "FinalizedCandidateResolver",
    "GateStatus",
    "GeometryMetrics",
    "InMemoryAssetRepository",
    "PublicationBlockedError",
    "PublicationApprovalVerifier",
    "PublicationRequest",
    "PublicationStatus",
    "QualityGate",
    "SourceAsset",
    "UnityStatus",
    "UsageReference",
    "Vector3Meters",
    "create_router",
]
