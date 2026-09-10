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

from .lookdev_models import LookdevError, LookdevDocument, LookdevApplication
from .lookdev_service import LookdevService, NodeLookdevValidator
from .lookdev_router import create_lookdev_router
from .lookdev_application import LookdevAssetApplication
__all__ += ['LookdevError', 'LookdevDocument', 'LookdevApplication', 'LookdevService',
            'NodeLookdevValidator', 'create_lookdev_router', 'LookdevAssetApplication']

from .lookdev_models import SaveLookdevRequest, LookdevProposalRequest, ApplyLookdevRequest, LookdevTarget
__all__ += ['SaveLookdevRequest', 'LookdevProposalRequest', 'ApplyLookdevRequest', 'LookdevTarget']
from .lookdev_models import FinishLookdevTurnRequest, LookdevTurn
__all__ += ['FinishLookdevTurnRequest', 'LookdevTurn']
from .lookdev_runtime import prepare_lookdev_runtime

from .lookdev_models import ExportLookdevRequest, LookdevExport
__all__ += ['ExportLookdevRequest', 'LookdevExport']
from .lookdev_runtime import requires_game_runtime
