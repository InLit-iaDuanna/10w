"""Structural visual fixture comparison; pixel/screenshot comparison remains planned."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisualComparison:
    passed: bool
    differences: tuple[str, ...]
    mode: str = "mock"
    method: str = "structural-fixture-v1"


def compare_visual_fixture(expected: dict[str, Any], actual: dict[str, Any]) -> VisualComparison:
    """Compares declared profile and prompt geometry/content without pixel or hash claims."""
    keys = ("fixture_id", "mode", "profile", "screens")
    differences = tuple(key for key in keys if expected.get(key) != actual.get(key))
    return VisualComparison(not differences, differences)
