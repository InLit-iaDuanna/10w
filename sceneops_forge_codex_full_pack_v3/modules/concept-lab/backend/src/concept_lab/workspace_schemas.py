from __future__ import annotations

from typing import List

from .generation_schemas import GenerationRun
from .schemas import (
    AssetSpecDraft,
    ConceptChangeSet,
    ConceptDecision,
    ConceptReference,
    ConceptSpec,
    ConceptVariant,
    StrictModel,
    StyleCheck,
    VariantComment,
)


class ConceptReviewWorkspace(StrictModel):
    concept: ConceptSpec
    references: List[ConceptReference]
    variants: List[ConceptVariant]
    style_checks: List[StyleCheck]
    comments: List[VariantComment]
    decisions: List[ConceptDecision]
    change_sets: List[ConceptChangeSet]
    generation_runs: List[GenerationRun]
    asset_spec_drafts: List[AssetSpecDraft]
