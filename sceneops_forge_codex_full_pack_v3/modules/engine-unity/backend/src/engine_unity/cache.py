"""Truthful replay cache: only successful live results may enter it."""

from __future__ import annotations

from typing import Dict

from .contracts import CommandResult, CommandStatus, ExecutionMode
from .errors import ErrorCode, UnityIntegrationError


class LiveResultCache:
    def __init__(self) -> None:
        self._results: Dict[str, CommandResult] = {}

    def put(self, key: str, result: CommandResult) -> None:
        if result.mode is not ExecutionMode.LIVE or result.status is not CommandStatus.SUCCEEDED:
            raise ValueError("only successful live results can be cached")
        self._results[key] = result.model_copy(deep=True)

    def replay(self, key: str, request_id: str) -> CommandResult:
        try:
            original = self._results[key]
        except KeyError as exc:
            raise UnityIntegrationError(
                ErrorCode.CACHE_MISS,
                "No prior successful live Unity result exists for this cache key.",
                details={"cache_key": key},
            ) from exc
        return original.model_copy(
            update={
                "request_id": request_id,
                "mode": ExecutionMode.CACHED,
                "cached_from_request_id": original.request_id,
            },
            deep=True,
        )
