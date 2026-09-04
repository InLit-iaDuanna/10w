"""Repository-wide module discovery and dependency validation."""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from sceneops_core_events import (
    EventReferenceError,
    EventSchemaDescriptor,
    EventSchemaError,
    ensure_contiguous_versions,
    validate_event_evolution,
)

from .diagnostics import Diagnostic, RepositoryValidationError, relative_display
from .import_boundaries import validate_import_boundaries
from .loader import ModuleSource, load_manifest


CORE_MODULE_IDS = {"core-kernel", "module-runtime"}


@dataclass(frozen=True)
class ModuleGraph:
    sources: Tuple[ModuleSource, ...]

    @property
    def manifests(self):
        return tuple(source.manifest for source in self.sources)

    @property
    def module_ids(self) -> Tuple[str, ...]:
        return tuple(source.manifest.id for source in self.sources)


def _entrypoint_diagnostics(
    source: ModuleSource, repository_root: Path
) -> Iterable[Diagnostic]:
    manifest = source.manifest
    frontend = manifest.entrypoints.frontend
    if frontend is not None:
        candidate = (source.directory / frontend).resolve()
        try:
            candidate.relative_to(source.directory)
        except ValueError:
            yield Diagnostic(
                "ENTRYPOINT_OUTSIDE_MODULE",
                f"frontend entrypoint escapes module directory: {frontend}",
                relative_display(source.manifest_path, repository_root),
                module_id=manifest.id,
            )
        else:
            if not candidate.is_file():
                yield Diagnostic(
                    "ENTRYPOINT_MISSING",
                    f"frontend entrypoint does not exist: {frontend}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
    backend = manifest.entrypoints.backend
    if backend is not None:
        candidate = source.directory / "backend" / "src" / Path(*backend.split(".")) / "__init__.py"
        if not candidate.is_file():
            yield Diagnostic(
                "ENTRYPOINT_MISSING",
                f"backend package entrypoint does not exist: {backend}",
                relative_display(source.manifest_path, repository_root),
                module_id=manifest.id,
            )


def _event_schema_diagnostics(
    sources: Sequence[ModuleSource], repository_root: Path
) -> Iterable[Diagnostic]:
    owners: Dict[str, str] = {}
    descriptors: Dict[str, List[EventSchemaDescriptor]] = {}
    exact_references: Set[str] = set()
    for source in sources:
        manifest = source.manifest
        try:
            references = ensure_contiguous_versions(manifest.contributes.events)
        except EventReferenceError as exc:
            yield Diagnostic(
                "EVENT_VERSION_INVALID",
                str(exc),
                relative_display(source.manifest_path, repository_root),
                module_id=manifest.id,
            )
            references = []
        for reference in references:
            rendered_reference = str(reference)
            if rendered_reference in exact_references:
                yield Diagnostic(
                    "DUPLICATE_EVENT_ID",
                    f"event contribution is already registered: {rendered_reference}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
            exact_references.add(rendered_reference)
            owner = owners.setdefault(reference.event_type, manifest.id)
            if owner != manifest.id:
                yield Diagnostic(
                    "EVENT_OWNER_CONFLICT",
                    f"event {reference.event_type} versions are split between {owner} and {manifest.id}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
            schema_path = source.directory / "contracts" / "events" / reference.schema_filename
            if not schema_path.is_file():
                yield Diagnostic(
                    "EVENT_SCHEMA_MISSING",
                    f"missing payload schema for {rendered_reference}: {reference.schema_filename}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
                continue
            try:
                raw = json.loads(schema_path.read_text(encoding="utf-8"))
                if not isinstance(raw, Mapping):
                    raise EventSchemaError(
                        "EVENT_SCHEMA_ROOT_INVALID", "event schema root must be an object"
                    )
                descriptor = EventSchemaDescriptor.from_mapping(raw)
                if descriptor.reference != reference:
                    raise EventSchemaError(
                        "EVENT_SCHEMA_REFERENCE_MISMATCH",
                        f"schema declares {descriptor.reference}, expected {reference}",
                    )
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                yield Diagnostic(
                    "EVENT_SCHEMA_INVALID_JSON",
                    str(exc),
                    relative_display(schema_path, repository_root),
                    module_id=manifest.id,
                )
                continue
            except (EventReferenceError, EventSchemaError) as exc:
                yield Diagnostic(
                    getattr(exc, "code", "EVENT_SCHEMA_INVALID"),
                    str(exc),
                    relative_display(schema_path, repository_root),
                    module_id=manifest.id,
                )
                continue
            descriptors.setdefault(reference.event_type, []).append(descriptor)

    for event_type, versions in descriptors.items():
        ordered = sorted(versions, key=lambda item: item.reference.version)
        for previous, candidate in zip(ordered, ordered[1:]):
            try:
                validate_event_evolution(previous, candidate)
            except EventSchemaError as exc:
                yield Diagnostic(
                    exc.code,
                    str(exc),
                    f"event:{event_type}",
                    module_id=owners[event_type],
                )


def _find_cycle(dependencies: Mapping[str, Set[str]]) -> Tuple[str, ...]:
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def visit(module_id: str) -> Optional[Tuple[str, ...]]:
        if module_id in visiting:
            start = stack.index(module_id)
            return tuple(stack[start:] + [module_id])
        if module_id in visited:
            return None
        visiting.add(module_id)
        stack.append(module_id)
        for dependency in sorted(dependencies[module_id]):
            result = visit(dependency)
            if result is not None:
                return result
        stack.pop()
        visiting.remove(module_id)
        visited.add(module_id)
        return None

    for module_id in sorted(dependencies):
        result = visit(module_id)
        if result is not None:
            return result
    return ()


def _topological_order(sources: Sequence[ModuleSource]) -> Tuple[ModuleSource, ...]:
    by_id = {source.manifest.id: source for source in sources}
    dependencies = {
        module_id: set(source.manifest.requires.modules) & set(by_id)
        for module_id, source in by_id.items()
    }
    indegree = {module_id: len(values) for module_id, values in dependencies.items()}
    dependents: Dict[str, Set[str]] = {module_id: set() for module_id in by_id}
    for module_id, values in dependencies.items():
        for dependency in values:
            dependents[dependency].add(module_id)
    ready = [module_id for module_id, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    ordered: List[ModuleSource] = []
    while ready:
        module_id = heapq.heappop(ready)
        ordered.append(by_id[module_id])
        for dependent in sorted(dependents[module_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(ordered) != len(sources):
        cycle = _find_cycle(dependencies)
        raise RepositoryValidationError(
            [
                Diagnostic(
                    "MODULE_DEPENDENCY_CYCLE",
                    " -> ".join(cycle),
                    "modules",
                    module_id=cycle[0] if cycle else "",
                )
            ]
        )
    return tuple(ordered)


def validate_repository(
    repository_root: Path, *, check_imports: bool = True
) -> ModuleGraph:
    repository_root = repository_root.resolve()
    modules_root = repository_root / "modules"
    diagnostics: List[Diagnostic] = []
    sources: List[ModuleSource] = []
    if not modules_root.is_dir():
        raise RepositoryValidationError(
            [Diagnostic("MODULES_DIRECTORY_MISSING", "modules directory does not exist", "modules")]
        )
    for directory in sorted(path for path in modules_root.iterdir() if path.is_dir()):
        manifest_path = directory / "module.yaml"
        if not manifest_path.is_file():
            diagnostics.append(
                Diagnostic(
                    "MODULE_MANIFEST_MISSING",
                    "module directory requires module.yaml",
                    relative_display(directory, repository_root),
                    module_id=directory.name,
                )
            )
            continue
        source, load_diagnostics = load_manifest(manifest_path, repository_root)
        diagnostics.extend(load_diagnostics)
        if source is not None:
            sources.append(source)

    by_id: Dict[str, ModuleSource] = {}
    feature_flags: Dict[str, str] = {}
    contribution_owners: Dict[Tuple[str, str], str] = {}
    contribution_fields = ("editors", "commands", "jobs", "workflows", "policy_gates")
    for source in sources:
        manifest = source.manifest
        if source.directory.name != manifest.id:
            diagnostics.append(
                Diagnostic(
                    "MODULE_DIRECTORY_MISMATCH",
                    f"directory {source.directory.name!r} must match manifest id {manifest.id!r}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
            )
        previous = by_id.setdefault(manifest.id, source)
        if previous is not source:
            diagnostics.append(
                Diagnostic(
                    "DUPLICATE_MODULE_ID",
                    f"module id {manifest.id!r} is also declared by {previous.directory.name}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
            )
        flag_owner = feature_flags.setdefault(manifest.feature_flag, manifest.id)
        if flag_owner != manifest.id:
            diagnostics.append(
                Diagnostic(
                    "DUPLICATE_FEATURE_FLAG",
                    f"feature flag {manifest.feature_flag!r} is already owned by {flag_owner}",
                    relative_display(source.manifest_path, repository_root),
                    module_id=manifest.id,
                )
            )
        diagnostics.extend(_entrypoint_diagnostics(source, repository_root))
        for field in contribution_fields:
            for contribution_id in getattr(manifest.contributes, field):
                key = (field, contribution_id)
                owner = contribution_owners.setdefault(key, manifest.id)
                if owner != manifest.id:
                    diagnostics.append(
                        Diagnostic(
                            f"DUPLICATE_{field[:-1].upper()}_ID",
                            f"{field[:-1]} id {contribution_id!r} is already owned by {owner}",
                            relative_display(source.manifest_path, repository_root),
                            module_id=manifest.id,
                        )
                    )

    known_ids = set(by_id)
    for source in sources:
        manifest = source.manifest
        for dependency in manifest.requires.modules:
            if dependency not in known_ids:
                diagnostics.append(
                    Diagnostic(
                        "MODULE_DEPENDENCY_MISSING",
                        f"required module {dependency!r} was not discovered",
                        relative_display(source.manifest_path, repository_root),
                        module_id=manifest.id,
                    )
                )
        if manifest.id in CORE_MODULE_IDS:
            forbidden = sorted(set(manifest.requires.modules) - CORE_MODULE_IDS)
            if forbidden:
                diagnostics.append(
                    Diagnostic(
                        "CORE_DEPENDENCY_DIRECTION_INVALID",
                        "core module cannot depend on feature modules: " + ", ".join(forbidden),
                        relative_display(source.manifest_path, repository_root),
                        module_id=manifest.id,
                    )
                )

    diagnostics.extend(_event_schema_diagnostics(sources, repository_root))
    if check_imports:
        diagnostics.extend(validate_import_boundaries(sources, repository_root))
    if diagnostics:
        raise RepositoryValidationError(diagnostics)

    return ModuleGraph(_topological_order(sources))
