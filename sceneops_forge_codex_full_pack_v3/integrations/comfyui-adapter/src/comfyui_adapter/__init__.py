"""Public API for the SceneOps ComfyUI integration."""

from .adapter import ADAPTER_VERSION, CancellationToken, ComfyUIAdapter
from .errors import ComfyAdapterError, TransportFailure
from .mock import DeterministicMockComfyAdapter
from .ledger import (
    EnqueueClaim,
    EnqueueLedger,
    EnqueueLedgerConflict,
    InMemoryEnqueueLedger,
    SQLiteEnqueueLedger,
)
from .models import (
    ComfyCapabilities,
    ComfyEnqueueCommand,
    EnqueueResult,
    HealthState,
    IntegrationHealth,
    MockEnqueueResult,
    MockOutput,
    MockProgressEvent,
    OutputDescriptor,
    ProgressEvent,
    PromptState,
    RetrievedOutput,
    RetryPolicy,
    TrustedWorkflow,
    WorkflowBinding,
)
from .transport import HttpResponse, JsonTransport, UrllibJsonTransport
from .security import validate_output_descriptor, validate_prompt_id
from .workflows import (
    ArtifactInputResolver,
    DEFAULT_ALLOWED_NODE_CLASSES,
    TrustedWorkflowRegistry,
    compute_workflow_checksum_sha256,
    validate_staged_input,
)

__all__ = [
    "ADAPTER_VERSION",
    "ArtifactInputResolver",
    "CancellationToken",
    "ComfyAdapterError",
    "ComfyCapabilities",
    "ComfyEnqueueCommand",
    "ComfyUIAdapter",
    "DeterministicMockComfyAdapter",
    "EnqueueResult",
    "EnqueueClaim",
    "EnqueueLedger",
    "EnqueueLedgerConflict",
    "HealthState",
    "HttpResponse",
    "IntegrationHealth",
    "InMemoryEnqueueLedger",
    "JsonTransport",
    "MockEnqueueResult",
    "MockOutput",
    "MockProgressEvent",
    "OutputDescriptor",
    "ProgressEvent",
    "PromptState",
    "RetrievedOutput",
    "RetryPolicy",
    "SQLiteEnqueueLedger",
    "TransportFailure",
    "TrustedWorkflow",
    "TrustedWorkflowRegistry",
    "DEFAULT_ALLOWED_NODE_CLASSES",
    "UrllibJsonTransport",
    "WorkflowBinding",
    "validate_staged_input",
    "compute_workflow_checksum_sha256",
    "validate_output_descriptor",
    "validate_prompt_id",
]
