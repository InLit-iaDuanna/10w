"""Public backend surface for the SceneOps Forge Concept Lab module."""

from .adapters import ConceptGenerationAdapter, FixtureGenerationAdapter
from .contribution import module_contribution
from .errors import ConceptLabError
from .generation_schemas import (
    AdapterHealth,
    GenerationCapabilities,
    GenerationOutput,
    GenerationPlan,
    GenerationRequest,
)
from .repository import ConceptRepository, InMemoryConceptRepository
from .router import concept_lab_error_handler, create_router
from .schemas import (
    AssetSpecDraft,
    ConceptChangeSet,
    ConceptReference,
    ConceptSpec,
    ConceptVariant,
    ExecutionMode,
    StyleCheck,
)
from .service import ConceptLabService

__all__ = [
    "AdapterHealth",
    "AssetSpecDraft",
    "ConceptChangeSet",
    "ConceptGenerationAdapter",
    "ConceptLabError",
    "ConceptLabService",
    "ConceptReference",
    "ConceptRepository",
    "ConceptSpec",
    "ConceptVariant",
    "ExecutionMode",
    "FixtureGenerationAdapter",
    "GenerationCapabilities",
    "GenerationOutput",
    "GenerationPlan",
    "GenerationRequest",
    "InMemoryConceptRepository",
    "StyleCheck",
    "concept_lab_error_handler",
    "create_router",
    "module_contribution",
]
