"""Explicit public conversion; preserves the complete approved concept brief."""
from pydantic import BaseModel
from concept_lab import AssetSpecDraft
from asset_library import AssetSpec, Vector3Meters

class ConceptAssetHandoff(BaseModel):
    draft: AssetSpecDraft
    spec: AssetSpec

def asset_spec_from_concept(draft: AssetSpecDraft, *, asset_id: str, category: str = "prop") -> ConceptAssetHandoff:
    spec = AssetSpec(
        asset_spec_id="aspec_" + draft.asset_spec_draft_id,
        project_id=draft.project_id, asset_id=asset_id, display_name=draft.subject,
        category=category, description=draft.proportions,
        intended_use=draft.gameplay_function,
        target_dimensions_m=Vector3Meters(x=draft.dimensions.width,
            y=draft.dimensions.depth, z=draft.dimensions.height),
        triangle_budget=draft.platform_budget.max_triangles, created_at=draft.created_at)
    return ConceptAssetHandoff(draft=draft, spec=spec)
