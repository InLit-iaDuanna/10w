"""Readable diagnostics emitted by module validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Tuple


class DiagnosticSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, order=True)
class Diagnostic:
    code: str
    message: str
    path: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    module_id: str = ""

    def render(self) -> str:
        location = self.path
        owner = f" [{self.module_id}]" if self.module_id else ""
        return f"{self.severity.value.upper()} {self.code}{owner} {location}: {self.message}"


class RepositoryValidationError(RuntimeError):
    def __init__(self, diagnostics: Iterable[Diagnostic]):
        ordered = tuple(sorted(diagnostics))
        self.diagnostics: Tuple[Diagnostic, ...] = ordered
        super().__init__("\n".join(item.render() for item in ordered))


def relative_display(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
