"""Typed source-of-truth model for ``modules/*/module.yaml``."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


MODULE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
FEATURE_FLAG_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
CONTRIBUTION_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"
EVENT_REFERENCE_PATTERN = (
    r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+@[1-9][0-9]*$"
)
PERMISSION_PATTERN = r"^[a-z][a-z0-9-]*(?::[a-z][a-z0-9_-]*)+$"
FRONTEND_ENTRYPOINT_PATTERN = (
    r"^\./(?!(?:.*?/)?\.\.(?:/|$))(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.tsx?$"
)
BACKEND_ENTRYPOINT_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"

ModuleIdValue = Annotated[str, StringConstraints(pattern=MODULE_ID_PATTERN)]
ContributionIdValue = Annotated[str, StringConstraints(pattern=CONTRIBUTION_ID_PATTERN)]
EventReferenceValue = Annotated[str, StringConstraints(pattern=EVENT_REFERENCE_PATTERN)]
PermissionValue = Annotated[str, StringConstraints(pattern=PERMISSION_PATTERN)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModuleStatus(str, Enum):
    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


class ModuleRequirements(StrictModel):
    modules: List[ModuleIdValue]
    integrations: List[ModuleIdValue]
    optional_integrations: List[ModuleIdValue]

    @model_validator(mode="after")
    def validate_lists(self) -> "ModuleRequirements":
        fields = {
            "modules": self.modules,
            "integrations": self.integrations,
            "optional_integrations": self.optional_integrations,
        }
        for name, values in fields.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} cannot contain duplicates")
        overlap = set(self.integrations) & set(self.optional_integrations)
        if overlap:
            raise ValueError(
                "integrations and optional_integrations overlap: "
                + ", ".join(sorted(overlap))
            )
        return self


class ModuleContributions(StrictModel):
    editors: List[ContributionIdValue]
    commands: List[ContributionIdValue]
    events: List[EventReferenceValue]
    jobs: List[ContributionIdValue]
    workflows: List[ContributionIdValue]
    policy_gates: List[ContributionIdValue]

    @model_validator(mode="after")
    def validate_contributions(self) -> "ModuleContributions":
        for name in ("editors", "commands", "jobs", "workflows", "policy_gates"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} cannot contain duplicates")
        if len(self.events) != len(set(self.events)):
            raise ValueError("events cannot contain duplicates")
        return self


class ModuleEntrypoints(StrictModel):
    frontend: Optional[str] = Field(
        default=None, json_schema_extra={"pattern": FRONTEND_ENTRYPOINT_PATTERN}
    )
    backend: Optional[str] = Field(default=None, pattern=BACKEND_ENTRYPOINT_PATTERN)

    @model_validator(mode="after")
    def require_surface(self) -> "ModuleEntrypoints":
        if self.frontend is None and self.backend is None:
            raise ValueError("at least one public entrypoint is required")
        if self.frontend is not None and not _fullmatch(
            FRONTEND_ENTRYPOINT_PATTERN, self.frontend
        ):
            raise ValueError("frontend entrypoint must be a safe module-local .ts/.tsx path")
        return self


class ModuleManifest(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    id: str = Field(pattern=MODULE_ID_PATTERN)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    status: ModuleStatus
    feature_flag: str = Field(pattern=FEATURE_FLAG_PATTERN)
    requires: ModuleRequirements
    contributes: ModuleContributions
    permissions: List[PermissionValue]
    entrypoints: ModuleEntrypoints

    @model_validator(mode="after")
    def validate_manifest(self) -> "ModuleManifest":
        if self.id in self.requires.modules:
            raise ValueError("module cannot require itself")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("permissions cannot contain duplicates")
        return self


def _fullmatch(pattern: str, value: str) -> bool:
    import re

    return re.fullmatch(pattern, value) is not None
