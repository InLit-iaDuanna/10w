"""Public backend API for SceneOps Forge Logic Studio."""

from .changesets import (
    AdapterUnavailableError,
    ApprovalRequiredError,
    CodeChangeCoordinator,
    CodeChangeProposalError,
)
from .jobs import JOB_DEFINITIONS
from .models import (
    CodeChangeProposal,
    CodeChangeSet,
    CompileTemplateRequest,
    GameplayGraph,
    GameplayGraphDiff,
    GeneratedTestPlan,
    GraphValidationReport,
)
from .router import router
from .runtime import GameplayGraphRuntime, TransitionUnavailable
from .serialization import (
    deserialize_gameplay_graph,
    diff_gameplay_graphs,
    serialize_gameplay_graph,
)
from .service import LogicStudioService
from .templates import InteractionTemplateCatalog, load_default_template_catalog
from .test_generation import generate_test_plan
from .unity_adapter import (
    AdapterExecutionContext,
    DeterministicMockUnityCodeChangeAdapter,
    UnityCodeChangeAdapter,
)
from .validation import validate_gameplay_graph

__all__ = [
    "AdapterExecutionContext",
    "AdapterUnavailableError",
    "ApprovalRequiredError",
    "CodeChangeCoordinator",
    "CodeChangeProposal",
    "CodeChangeProposalError",
    "CodeChangeSet",
    "CompileTemplateRequest",
    "DeterministicMockUnityCodeChangeAdapter",
    "GameplayGraph",
    "GameplayGraphDiff",
    "GameplayGraphRuntime",
    "GeneratedTestPlan",
    "GraphValidationReport",
    "InteractionTemplateCatalog",
    "JOB_DEFINITIONS",
    "LogicStudioService",
    "TransitionUnavailable",
    "UnityCodeChangeAdapter",
    "deserialize_gameplay_graph",
    "diff_gameplay_graphs",
    "generate_test_plan",
    "load_default_template_catalog",
    "router",
    "serialize_gameplay_graph",
    "validate_gameplay_graph",
]
