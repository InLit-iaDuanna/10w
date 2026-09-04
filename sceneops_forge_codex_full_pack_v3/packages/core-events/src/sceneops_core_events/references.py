"""Parsing and validation for versioned event references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


EVENT_REFERENCE_PATTERN = re.compile(
    r"^(?P<event_type>[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+)@(?P<version>[1-9][0-9]*)$"
)


class EventReferenceError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class EventReference:
    event_type: str
    version: int

    @classmethod
    def parse(cls, value: str) -> "EventReference":
        match = EVENT_REFERENCE_PATTERN.fullmatch(value)
        if match is None:
            raise EventReferenceError(
                f"invalid event reference {value!r}; expected dotted.event.name@<positive-version>"
            )
        return cls(match.group("event_type"), int(match.group("version")))

    def __str__(self) -> str:
        return f"{self.event_type}@{self.version}"

    @property
    def schema_filename(self) -> str:
        return f"{self.event_type}.v{self.version}.schema.json"


def ensure_contiguous_versions(values: Iterable[str]) -> List[EventReference]:
    references = sorted(EventReference.parse(value) for value in values)
    grouped = {}
    for reference in references:
        grouped.setdefault(reference.event_type, []).append(reference.version)
    for event_type, versions in grouped.items():
        if len(versions) != len(set(versions)):
            raise EventReferenceError(f"duplicate event version for {event_type}")
        expected = list(range(1, max(versions) + 1))
        if versions != expected:
            raise EventReferenceError(
                f"event versions for {event_type} must be contiguous from 1; got {versions}"
            )
    return references
