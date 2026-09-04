"""Load deterministic JSON examples into typed domain values."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    ApprovalState,
    EventBinding,
    ExecutionMode,
    ParameterKind,
    ParameterSpec,
    Provenance,
    QualityTier,
    VfxShaderRecipe,
)


MODULE_ROOT = Path(__file__).resolve().parents[3]


def load_recipe_fixture(name: str) -> VfxShaderRecipe:
    allowed = {"hero_home_highlight", "warehouse_escape"}
    if name not in allowed:
        raise ValueError(f"unknown fixture: {name}")
    payload = json.loads((MODULE_ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
    return recipe_from_dict(payload)


def recipe_from_dict(payload: dict[str, Any]) -> VfxShaderRecipe:
    specs = tuple(
        ParameterSpec(
            key=item["key"],
            kind=ParameterKind(item["kind"]),
            label_zh=item["label_zh"],
            default=item["default"],
            minimum=item.get("minimum"),
            maximum=item.get("maximum"),
            step=item.get("step"),
        )
        for item in payload["parameter_specs"]
    )
    bindings = tuple(EventBinding(**item) for item in payload["bindings"])
    provenance_data = dict(payload["provenance"])
    provenance_data["related_sceneops_ids"] = tuple(provenance_data["related_sceneops_ids"])
    provenance_data["execution_mode"] = ExecutionMode(provenance_data["execution_mode"])
    provenance_data["approval_state"] = ApprovalState(provenance_data["approval_state"])
    provenance = Provenance(**provenance_data)
    return VfxShaderRecipe(
        recipe_id=payload["recipe_id"],
        version=payload["version"],
        template_id=payload["template_id"],
        title_zh=payload["title_zh"],
        shader_family=payload["shader_family"],
        quality_tier=QualityTier(payload["quality_tier"]),
        parameter_specs=specs,
        parameters=payload["parameters"],
        particle_count=payload["particle_count"],
        estimated_overdraw_layers=payload["estimated_overdraw_layers"],
        estimated_screen_coverage_percent=payload["estimated_screen_coverage_percent"],
        bindings=bindings,
        provenance=provenance,
        optional=payload["optional"],
    )
