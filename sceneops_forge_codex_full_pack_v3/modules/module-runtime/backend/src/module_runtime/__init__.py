"""Public backend entrypoint for the static SceneOps module runtime."""

from .activation import (
    ModuleAvailability,
    ModuleRuntimeState,
    UnknownFeatureFlagError,
    resolve_module_states,
)
from .catalog import generated_files, write_generated_files
from .diagnostics import Diagnostic, RepositoryValidationError
from .generated_manifest import GENERATED_MODULE_MANIFEST
from .loader import ModuleSource, load_manifest
from .manifest import (
    ModuleContributions,
    ModuleEntrypoints,
    ModuleManifest,
    ModuleRequirements,
    ModuleStatus,
)
from .repository import ModuleGraph, validate_repository
from .scaffold import ScaffoldError, scaffold_module


backend_module_contribution = {
    "manifest": GENERATED_MODULE_MANIFEST,
    "router": None,
    "jobs": ("module.catalog.build",),
    "event_handlers": (),
    "policy_gates": (),
}


__all__ = [
    "Diagnostic",
    "ModuleAvailability",
    "ModuleContributions",
    "ModuleEntrypoints",
    "ModuleGraph",
    "ModuleManifest",
    "ModuleRequirements",
    "ModuleRuntimeState",
    "ModuleSource",
    "ModuleStatus",
    "RepositoryValidationError",
    "ScaffoldError",
    "UnknownFeatureFlagError",
    "backend_module_contribution",
    "generated_files",
    "load_manifest",
    "resolve_module_states",
    "scaffold_module",
    "validate_repository",
    "write_generated_files",
]
