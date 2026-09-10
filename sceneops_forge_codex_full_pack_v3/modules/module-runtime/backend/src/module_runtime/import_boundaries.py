"""Static cross-module import-boundary validation."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

from .diagnostics import Diagnostic, relative_display
from .loader import ModuleSource


_ESM_IMPORT = re.compile(
    r"\b(?:import|export)\s+(?:type\s+)?(?:[A-Za-z0-9_$*\s{},]+?\s+from\s+)?"
    r"(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_CALL_IMPORT = re.compile(
    r"\b(?:import|require)\s*\(\s*(?P<quote>['\"])(?P<source>[^'\"]+)(?P=quote)\s*\)"
)
_DYNAMIC_IMPORT = re.compile(r"(?<![\w$.])import\s*\(\s*(?![\s'\"])")


def _strip_javascript_comments(source: str) -> str:
    output: List[str] = []
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                output.extend("  ")
                index += 2
                state = "line_comment"
                continue
            if char == "/" and following == "*":
                output.extend("  ")
                index += 2
                state = "block_comment"
                continue
            if char in {"'", '"', "`"}:
                quote = char
                state = "string"
            output.append(char)
            index += 1
            continue
        if state == "line_comment":
            if char == "\n":
                output.append(char)
                state = "code"
            else:
                output.append(" ")
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and following == "/":
                output.extend("  ")
                index += 2
                state = "code"
            else:
                output.append("\n" if char == "\n" else " ")
                index += 1
            continue
        output.append(char)
        if char == "\\" and index + 1 < len(source):
            output.append(source[index + 1])
            index += 2
            continue
        if char == quote:
            state = "code"
        index += 1
    return "".join(output)


def _typescript_imports(source: str) -> Tuple[Set[str], bool]:
    cleaned = _strip_javascript_comments(source)
    imports = {match.group("source") for match in _ESM_IMPORT.finditer(cleaned)}
    imports.update(match.group("source") for match in _CALL_IMPORT.finditer(cleaned))
    return imports, _DYNAMIC_IMPORT.search(cleaned) is not None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _target_for_typescript_import(
    source_path: Path,
    specifier: str,
    modules: Mapping[str, ModuleSource],
) -> Tuple[Optional[str], Optional[Path], bool]:
    if specifier.startswith("@sceneops/"):
        module_id = specifier[len("@sceneops/") :].split("/", 1)[0]
        if module_id in modules:
            return module_id, None, "/" not in specifier[len("@sceneops/") :]
        return None, None, False
    if not specifier.startswith("."):
        return None, None, False
    resolved = (source_path.parent / specifier).resolve()
    for module_id, module in modules.items():
        if _is_within(resolved, module.directory):
            relative = resolved.relative_to(module.directory)
            normalized = relative.with_suffix("")
            is_public = normalized.as_posix() == "frontend/src/index"
            return module_id, resolved, is_public
    return None, resolved, False


def _scan_typescript(
    owner: ModuleSource,
    modules: Mapping[str, ModuleSource],
    repository_root: Path,
) -> Iterator[Diagnostic]:
    extensions = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    for path in sorted(owner.directory.rglob("*")):
        if not path.is_file() or path.suffix not in extensions or "node_modules" in path.parts:
            continue
        try:
            specifiers, has_dynamic_import = _typescript_imports(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            yield Diagnostic(
                "SOURCE_READ_FAILED",
                str(exc),
                relative_display(path, repository_root),
                module_id=owner.manifest.id,
            )
            continue
        if has_dynamic_import:
            yield Diagnostic(
                "NON_STATIC_IMPORT_FORBIDDEN",
                "dynamic import target must be a string literal so builds remain deterministic",
                relative_display(path, repository_root),
                module_id=owner.manifest.id,
            )
        for specifier in sorted(specifiers):
            target_id, _, is_public = _target_for_typescript_import(path, specifier, modules)
            if target_id is None or target_id == owner.manifest.id:
                continue
            if target_id not in owner.manifest.requires.modules:
                yield Diagnostic(
                    "UNDECLARED_MODULE_IMPORT",
                    f"import {specifier!r} requires dependency {target_id!r} in module.yaml",
                    relative_display(path, repository_root),
                    module_id=owner.manifest.id,
                )
            elif not is_public:
                yield Diagnostic(
                    "INTERNAL_MODULE_IMPORT",
                    f"import {specifier!r} bypasses {target_id}'s frontend/src/index.ts public entrypoint",
                    relative_display(path, repository_root),
                    module_id=owner.manifest.id,
                )


def _python_import_names(tree: ast.AST) -> Iterator[Tuple[str, bool]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, False
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module, False
        elif isinstance(node, ast.Call):
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "importlib"
                and function.attr == "import_module"
            ):
                yield "", True
            elif isinstance(function, ast.Name) and function.id == "__import__":
                yield "", True


def _scan_python(
    owner: ModuleSource,
    modules: Mapping[str, ModuleSource],
    repository_root: Path,
) -> Iterator[Diagnostic]:
    backend_packages = {
        module.manifest.entrypoints.backend: module_id
        for module_id, module in modules.items()
        if module.manifest.entrypoints.backend is not None
    }
    for path in sorted(owner.directory.rglob("*.py")):
        if "__pycache__" in path.parts or path.is_relative_to(owner.directory / "backend" / "build"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            yield Diagnostic(
                "PYTHON_SOURCE_INVALID",
                str(exc),
                relative_display(path, repository_root),
                module_id=owner.manifest.id,
            )
            continue
        for imported, dynamic in _python_import_names(tree):
            if dynamic:
                yield Diagnostic(
                    "NON_STATIC_IMPORT_FORBIDDEN",
                    "runtime Python imports are forbidden in feature modules",
                    relative_display(path, repository_root),
                    module_id=owner.manifest.id,
                )
                continue
            for package, target_id in backend_packages.items():
                if imported != package and not imported.startswith(package + "."):
                    continue
                if target_id == owner.manifest.id:
                    break
                if target_id not in owner.manifest.requires.modules:
                    yield Diagnostic(
                        "UNDECLARED_MODULE_IMPORT",
                        f"import {imported!r} requires dependency {target_id!r} in module.yaml",
                        relative_display(path, repository_root),
                        module_id=owner.manifest.id,
                    )
                elif imported != package:
                    yield Diagnostic(
                        "INTERNAL_MODULE_IMPORT",
                        f"import {imported!r} bypasses {package}'s package entrypoint",
                        relative_display(path, repository_root),
                        module_id=owner.manifest.id,
                    )
                break


def validate_import_boundaries(
    sources: Sequence[ModuleSource], repository_root: Path
) -> Tuple[Diagnostic, ...]:
    modules = {source.manifest.id: source for source in sources}
    diagnostics: List[Diagnostic] = []
    for source in sources:
        diagnostics.extend(_scan_typescript(source, modules, repository_root))
        diagnostics.extend(_scan_python(source, modules, repository_root))
    unique = {
        (item.code, item.message, item.path, item.severity, item.module_id): item
        for item in diagnostics
    }
    return tuple(sorted(unique.values()))
