"""Safe YAML loading with Pydantic-backed schema diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Tuple

import yaml
from pydantic import ValidationError

from .diagnostics import Diagnostic, relative_display
from .manifest import ModuleManifest


@dataclass(frozen=True)
class ModuleSource:
    manifest: ModuleManifest
    directory: Path
    manifest_path: Path


def load_manifest(
    manifest_path: Path, repository_root: Path
) -> Tuple[Optional[ModuleSource], Tuple[Diagnostic, ...]]:
    display = relative_display(manifest_path, repository_root)
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return None, (
            Diagnostic("MANIFEST_YAML_INVALID", str(exc), display),
        )
    if not isinstance(raw, Mapping):
        return None, (
            Diagnostic("MANIFEST_ROOT_INVALID", "manifest root must be a mapping", display),
        )
    try:
        manifest = ModuleManifest.model_validate(raw)
    except ValidationError as exc:
        diagnostics: List[Diagnostic] = []
        module_id = raw.get("id") if isinstance(raw.get("id"), str) else ""
        for error in exc.errors(include_url=False):
            location = ".".join(str(item) for item in error["loc"]) or "<root>"
            diagnostics.append(
                Diagnostic(
                    "MANIFEST_SCHEMA_INVALID",
                    f"{location}: {error['msg']}",
                    display,
                    module_id=module_id,
                )
            )
        return None, tuple(diagnostics)
    return (
        ModuleSource(
            manifest=manifest,
            directory=manifest_path.parent.resolve(),
            manifest_path=manifest_path.resolve(),
        ),
        (),
    )
