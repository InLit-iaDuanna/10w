"""Unity editor and project version compatibility."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

from .errors import ErrorCode, UnityIntegrationError


MINIMUM_VERSION = (2022, 3)
MAXIMUM_MAJOR = 2022
PINNED_UNITY_VERSION = "2022.3.62f3c1"
_VERSION_PATTERN = re.compile(r"(?P<major>\d{4})\.(?P<minor>\d+)")


def parse_unity_version(value: str) -> Tuple[int, int]:
    match = _VERSION_PATTERN.search(value)
    if not match:
        raise UnityIntegrationError(
            ErrorCode.VERSION_INCOMPATIBLE,
            "Unity version could not be parsed.",
            details={"version": value},
        )
    return int(match.group("major")), int(match.group("minor"))


def validate_unity_version(value: str) -> None:
    parsed = parse_unity_version(value)
    if parsed < MINIMUM_VERSION or parsed[0] > MAXIMUM_MAJOR or value.strip() != PINNED_UNITY_VERSION:
        raise UnityIntegrationError(
            ErrorCode.VERSION_INCOMPATIBLE,
            "Unity editor version does not match the pinned integration version.",
            details={"version": value, "supported": PINNED_UNITY_VERSION},
        )


def project_unity_version(project_root: Path) -> str:
    version_file = project_root / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.is_file():
        raise UnityIntegrationError(
            ErrorCode.PROJECT_INVALID,
            "ProjectSettings/ProjectVersion.txt is missing.",
            details={"project_root": str(project_root)},
        )
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    raise UnityIntegrationError(
        ErrorCode.PROJECT_INVALID,
        "Unity project version is not declared.",
        details={"file": str(version_file)},
    )
