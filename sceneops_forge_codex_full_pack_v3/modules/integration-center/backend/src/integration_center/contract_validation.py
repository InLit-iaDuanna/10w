"""Shared validation rules for public Integration Center contracts."""

import re
from typing import List

from pydantic import JsonValue


STABLE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$"


def require_unique_stable(value: List[str]) -> List[str]:
    if len(value) != len(set(value)):
        raise ValueError("stable ID lists may not contain duplicates")
    if any(re.fullmatch(STABLE_ID_PATTERN, item) is None for item in value):
        raise ValueError("stable ID lists contain an invalid identifier")
    return value


def bounded_json(value: JsonValue, depth: int = 0) -> int:
    if depth > 4:
        raise ValueError("capability constraints may not exceed four nested levels")
    if isinstance(value, str):
        if len(value) > 1000:
            raise ValueError("capability constraint strings may not exceed 1000 characters")
        return 1
    if isinstance(value, dict):
        if len(value) > 32:
            raise ValueError("capability constraint objects may not exceed 32 entries")
        return 1 + sum(bounded_json(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if len(value) > 64:
            raise ValueError("capability constraint arrays may not exceed 64 entries")
        return 1 + sum(bounded_json(item, depth + 1) for item in value)
    return 1
