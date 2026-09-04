from __future__ import annotations

from pathlib import Path
from typing import Iterable


class PathBoundaryError(ValueError):
    pass


class ProjectPathPolicy:
    def __init__(self, project_root: Path) -> None:
        resolved = project_root.resolve(strict=True)
        if not resolved.is_dir():
            raise PathBoundaryError("project root must be an existing directory")
        self.project_root = resolved

    def resolve(self, value: str, *, must_exist: bool = False) -> Path:
        candidate = Path(value)
        if candidate.is_absolute():
            resolved = candidate.resolve(strict=must_exist)
        else:
            resolved = (self.project_root / candidate).resolve(strict=must_exist)
        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise PathBoundaryError("path escapes configured project root") from error
        return resolved

    def validate_all(self, values: Iterable[str], *, must_exist: bool = False) -> None:
        for value in values:
            self.resolve(value, must_exist=must_exist)

    def require_asset_factory_working_copy(
        self, value: str, *, must_exist: bool = False
    ) -> Path:
        resolved = self.resolve(value, must_exist=must_exist)
        relative = resolved.relative_to(self.project_root)
        if len(relative.parts) != 4 or relative.parts[:2] != (".sceneops", "asset-factory"):
            raise PathBoundaryError("working copy must use .sceneops/asset-factory/<run>/working.blend")
        if relative.name != "working.blend":
            raise PathBoundaryError("working copy filename must be working.blend")
        return resolved

    def require_asset_factory_snapshot(self, value: str) -> Path:
        resolved = self.resolve(value)
        relative = resolved.relative_to(self.project_root)
        if len(relative.parts) != 4 or relative.parts[:2] != (".sceneops", "asset-factory"):
            raise PathBoundaryError("snapshot must use .sceneops/asset-factory/<run>/rollback.blend")
        if relative.name != "rollback.blend":
            raise PathBoundaryError("snapshot filename must be rollback.blend")
        return resolved
