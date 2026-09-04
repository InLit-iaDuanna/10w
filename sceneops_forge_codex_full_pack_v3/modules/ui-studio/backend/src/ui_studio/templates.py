"""Public, dependency-free loaders for bundled UI templates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import UiElement, UiFlow, UiScreen


_TEMPLATE_PATHS = {
    "warehouse-escape": Path(__file__).parents[3] / "contracts" / "examples" / "warehouse-escape-ui-flow.json",
}


def ui_flow_from_document(document: Mapping[str, Any]) -> UiFlow:
    """Build a flow from host-supplied data without opening an arbitrary path."""
    screens = tuple(
        UiScreen(
            screen["id"],
            screen["title"],
            screen["kind"],
            screen["localized_text"],
            tuple(screen.get("next_screen_ids", ())),
            tuple(
                UiElement(
                    element["id"], element["anchor"], element["offset_x"], element["offset_y"],
                    element["width"], element["height"],
                )
                for element in screen.get("elements", ())
            ),
        )
        for screen in document["screens"]
    )
    return UiFlow(document["id"], document["game_template"], document["entry_screen_id"], screens)


def load_ui_flow_template(template_id: str) -> UiFlow:
    """Load one allowlisted module fixture; runtime uploads stay a host concern."""
    try:
        path = _TEMPLATE_PATHS[template_id]
    except KeyError as error:
        raise ValueError(f"unknown bundled UI template: {template_id}") from error
    with path.open(encoding="utf-8") as source:
        return ui_flow_from_document(json.load(source))


def load_warehouse_escape_template() -> UiFlow:
    return load_ui_flow_template("warehouse-escape")
