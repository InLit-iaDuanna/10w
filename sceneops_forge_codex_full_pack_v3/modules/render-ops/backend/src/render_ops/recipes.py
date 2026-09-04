"""Portable render recipe catalog."""

from pathlib import Path
from typing import Any, Dict, Optional

from .schemas import PortableRecipeCatalog, RenderRecipe


def recipe_catalog_path() -> Path:
    return Path(__file__).resolve().parents[3] / "workflows/recipes.v1.json"


def load_recipe_catalog(path: Optional[Path] = None) -> PortableRecipeCatalog:
    source = path or recipe_catalog_path()
    return PortableRecipeCatalog.model_validate_json(source.read_text(encoding="utf-8"))


def instantiate_recipe(
    recipe_id: str,
    *,
    workflow_reference: str,
    workflow_checksum_sha256: str,
    parameters: Dict[str, Any],
    catalog: Optional[PortableRecipeCatalog] = None,
) -> RenderRecipe:
    source = catalog or load_recipe_catalog()
    try:
        template = next(item for item in source.recipes if item.recipe_id == recipe_id)
    except StopIteration as exc:
        raise KeyError("unknown render recipe: " + recipe_id) from exc
    unknown = set(parameters) - set(template.portable_parameters)
    if unknown:
        raise ValueError("recipe contains undeclared portable parameters: " + ", ".join(sorted(unknown)))
    return RenderRecipe(
        recipe_id=template.recipe_id,
        version=template.version,
        kind=template.kind,
        required_passes=template.required_passes,
        optional_passes=template.optional_passes,
        workflow_reference=workflow_reference,
        workflow_checksum_sha256=workflow_checksum_sha256,
        parameters=parameters,
    )
