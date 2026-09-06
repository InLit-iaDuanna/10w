"""Public typed boundary for the SceneOps Blender integration."""

from .adapter import LiveBlenderAdapter
from .agent_session import BlenderAgentSession
from .artifacts import artifact_sha256, read_glb_json
from .cached_adapter import (
    CachedBlenderAdapter,
    VerifiedCacheArtifact,
    VerifiedLiveOperationRecord,
    VerifiedLiveResultStore,
    cache_behavior_payload,
    cache_key_for,
)
from .contracts import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    BlenderResult,
    CapabilityReport,
    ChangePreview,
    ExecutionMode,
    IntegrationHealth,
    MutationAuthorization,
    StructuredLog,
)
from .identity import (
    BlenderIdentityRegistry,
    BlenderObjectIdentity,
    IdentityConflictError,
    extract_sceneops_ids,
)
from .path_policy import PathBoundaryError, ProjectPathPolicy
from .mock_adapter import DeterministicMockBlenderAdapter
from .support import ADAPTER_VERSION
from .transport import SubprocessBlenderTransport

__all__ = [
    "ADAPTER_VERSION",
    "BlenderAdapterError",
    "BlenderAgentSession",
    "BlenderCommand",
    "BlenderIdentityRegistry",
    "BlenderObjectIdentity",
    "BlenderOperation",
    "BlenderResult",
    "CachedBlenderAdapter",
    "CapabilityReport",
    "ChangePreview",
    "DeterministicMockBlenderAdapter",
    "ExecutionMode",
    "IdentityConflictError",
    "IntegrationHealth",
    "LiveBlenderAdapter",
    "MutationAuthorization",
    "PathBoundaryError",
    "ProjectPathPolicy",
    "StructuredLog",
    "SubprocessBlenderTransport",
    "VerifiedLiveOperationRecord",
    "VerifiedLiveResultStore",
    "VerifiedCacheArtifact",
    "artifact_sha256",
    "cache_behavior_payload",
    "cache_key_for",
    "extract_sceneops_ids",
    "read_glb_json",
]
