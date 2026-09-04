from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from .models import CompileTemplateRequest, GameplayGraph, StrictModel


_PLACEHOLDER = re.compile(r"\$\{([a-zA-Z0-9_.-]+)\}")


class InteractionTemplate(StrictModel):
    schema_version: int = 1
    template_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str = Field(min_length=1)
    required_bindings: List[str] = Field(min_length=1)
    graph: Dict[str, Any]


class InteractionTemplateCatalog(StrictModel):
    schema_version: int = 1
    templates: List[InteractionTemplate]

    @classmethod
    def load(cls, path: Path) -> "InteractionTemplateCatalog":
        with path.open("r", encoding="utf-8") as source:
            return cls.model_validate(json.load(source))

    def compile(self, request: CompileTemplateRequest) -> GameplayGraph:
        templates = {
            template.template_id: template for template in self.templates
        }
        if request.template_id not in templates:
            raise KeyError(f"Unknown interaction template '{request.template_id}'.")
        template = templates[request.template_id]
        missing = sorted(set(template.required_bindings) - set(request.bindings))
        if missing:
            raise ValueError("Missing template bindings: " + ", ".join(missing))
        bindings = dict(request.bindings)
        bindings.update(
            {
                "project_id": request.project_id,
                "feature_spec_id": request.feature_spec_id,
                "mode": request.mode.value,
            }
        )
        compiled = _substitute(template.graph, bindings)
        unresolved = _find_placeholders(compiled)
        if unresolved:
            raise ValueError(
                "Unresolved template bindings: " + ", ".join(sorted(unresolved))
            )
        return GameplayGraph.model_validate(compiled)


def default_template_catalog_path() -> Path:
    return Path(__file__).resolve().parents[3] / "workflows" / "interaction-templates.v1.json"


def load_default_template_catalog() -> InteractionTemplateCatalog:
    return InteractionTemplateCatalog.load(default_template_catalog_path())


def _substitute(value: Any, bindings: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _substitute(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, bindings) for item in value]
    if not isinstance(value, str):
        return value
    exact = _PLACEHOLDER.fullmatch(value)
    if exact:
        return bindings.get(exact.group(1), value)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(bindings[key]) if key in bindings else match.group(0)

    return _PLACEHOLDER.sub(replace, value)


def _find_placeholders(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_find_placeholders(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_find_placeholders(item) for item in value), set())
    if isinstance(value, str):
        return set(_PLACEHOLDER.findall(value))
    return set()
