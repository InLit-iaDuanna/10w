"""Deterministic fixture-backed Unity runner."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from typing import Any, Dict, Optional

from .contracts import CommandRequest
from .errors import ErrorCode, UnityIntegrationError


class FixtureUnityRunner:
    def __init__(self, fixture_file: Path) -> None:
        self.fixture_file = fixture_file
        self._fixture = json.loads(fixture_file.read_text(encoding="utf-8"))

    @property
    def unity_version(self) -> str:
        return str(self._fixture["unityVersion"])

    def execute(
        self,
        request: CommandRequest,
        project_root: Path,
        cancellation: Optional[Event] = None,
    ) -> Dict[str, Any]:
        if cancellation and cancellation.is_set():
            raise UnityIntegrationError(
                ErrorCode.CANCELLED,
                "Mock Unity command was cancelled before execution.",
            )
        try:
            result = self._fixture["commands"][request.command.value]
        except KeyError as exc:
            raise UnityIntegrationError(
                ErrorCode.RESULT_MISSING,
                "Deterministic mock fixture has no result for this command.",
                details={"command": request.command.value},
            ) from exc
        return json.loads(json.dumps(result, sort_keys=True))
