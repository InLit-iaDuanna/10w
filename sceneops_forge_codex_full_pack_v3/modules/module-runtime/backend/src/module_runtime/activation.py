"""Feature-flag and integration-aware module availability resolution."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .manifest import ModuleManifest


class ModuleAvailability(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class ModuleRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str
    feature_flag: str
    availability: ModuleAvailability
    missing_required_integrations: List[str] = Field(default_factory=list)
    missing_optional_integrations: List[str] = Field(default_factory=list)
    blocking_dependencies: List[str] = Field(default_factory=list)
    message: str


class UnknownFeatureFlagError(ValueError):
    pass


def resolve_module_states(
    manifests: Sequence[ModuleManifest],
    feature_flags: Optional[Mapping[str, bool]] = None,
    available_integrations: Iterable[str] = (),
) -> Dict[str, ModuleRuntimeState]:
    flags = dict(feature_flags or {})
    known_flags = {manifest.feature_flag for manifest in manifests}
    unknown = sorted(set(flags) - known_flags)
    if unknown:
        raise UnknownFeatureFlagError("unknown feature flags: " + ", ".join(unknown))

    available = set(available_integrations)
    states: Dict[str, ModuleRuntimeState] = {}
    for manifest in manifests:
        missing_required = sorted(set(manifest.requires.integrations) - available)
        missing_optional = sorted(set(manifest.requires.optional_integrations) - available)
        blocking_dependencies = sorted(
            dependency
            for dependency in manifest.requires.modules
            if dependency not in states
            or states[dependency].availability != ModuleAvailability.ENABLED
        )
        enabled = flags.get(manifest.feature_flag, True)
        if not enabled:
            availability = ModuleAvailability.DISABLED
            message = "功能已由特性开关关闭。"
        elif blocking_dependencies:
            availability = ModuleAvailability.BLOCKED
            message = "依赖模块不可用：" + "、".join(blocking_dependencies)
        elif missing_required:
            availability = ModuleAvailability.BLOCKED
            message = "缺少必需集成：" + "、".join(missing_required)
        else:
            availability = ModuleAvailability.ENABLED
            message = (
                "已启用；可选集成不可用：" + "、".join(missing_optional)
                if missing_optional
                else "已启用。"
            )
        states[manifest.id] = ModuleRuntimeState(
            module_id=manifest.id,
            feature_flag=manifest.feature_flag,
            availability=availability,
            missing_required_integrations=missing_required,
            missing_optional_integrations=missing_optional,
            blocking_dependencies=blocking_dependencies,
            message=message,
        )
    return states
