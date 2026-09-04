"""Public backend API for the SceneOps VFX/Shader module."""
def create_lab_router():
    from .lab_api import create_lab_router as factory
    return factory()

from .adapters import (
    AdapterCapabilities,
    AdapterCommand,
    AdapterResult,
    DeterministicMockUnityAdapter,
    DeterministicMockRenderAdapter,
    IntegrationHealth,
    RenderPreviewAdapter,
    UnityVfxAdapter,
)
from .fixtures import load_recipe_fixture, recipe_from_dict
from .jobs import PREVIEW_JOB, JobDefinition, publication_job
from .models import (
    ApprovalState,
    BudgetWarning,
    ChangeSet,
    EventActor,
    EventContext,
    EventBinding,
    ExecutionMode,
    OperationResult,
    ParameterKind,
    ParameterSpec,
    PreviewPlan,
    Provenance,
    PublicationRequest,
    QUALITY_BUDGETS,
    QualityBudget,
    QualityTier,
    VfxShaderRecipe,
)
from .service import (
    VfxShaderService,
    build_event,
    plan_preview,
    plan_preview_operation,
    plan_publication,
    validate_budget,
    validate_recipe_operation,
)

__all__ = [
    "AdapterCapabilities", "AdapterCommand", "AdapterResult", "ApprovalState",
    "BudgetWarning", "ChangeSet", "DeterministicMockRenderAdapter", "DeterministicMockUnityAdapter",
    "EventActor", "EventBinding", "EventContext", "ExecutionMode", "IntegrationHealth", "JobDefinition",
    "OperationResult", "ParameterKind", "ParameterSpec", "PREVIEW_JOB",
    "PreviewPlan", "Provenance", "PublicationRequest", "QUALITY_BUDGETS",
    "QualityBudget", "QualityTier", "RenderPreviewAdapter", "UnityVfxAdapter",
    "VfxShaderRecipe", "VfxShaderService", "build_event", "load_recipe_fixture",
    "plan_preview", "plan_preview_operation", "plan_publication", "publication_job",
    "recipe_from_dict", "validate_budget", "validate_recipe_operation",
]
