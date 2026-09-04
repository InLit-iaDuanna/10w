from __future__ import annotations

from threading import Lock
from typing import Dict, Protocol, Tuple

from asset_library import AssetVersion, PublicationRequest


class FinalizedCandidateStore(Protocol):
    def finalize(self, change_set_id: str, candidate: AssetVersion) -> None: ...

    def discard(self, change_set_id: str, candidate: AssetVersion) -> None: ...

    def resolve(self, request: PublicationRequest) -> AssetVersion: ...


class InMemoryFinalizedCandidateStore:
    """Explicit local adapter; production composition injects durable run storage."""

    def __init__(self) -> None:
        self._candidates: Dict[Tuple[str, str, str], AssetVersion] = {}
        self._lock = Lock()

    def finalize(self, change_set_id: str, candidate: AssetVersion) -> None:
        key = (candidate.asset_id, candidate.asset_version_id, change_set_id)
        stored = candidate.model_copy(deep=True)
        with self._lock:
            existing = self._candidates.get(key)
            if existing is not None and existing != stored:
                raise ValueError("finalized candidate key is immutable")
            self._candidates[key] = stored

    def resolve(self, request: PublicationRequest) -> AssetVersion:
        key = (request.asset_id, request.asset_version_id, request.change_set_id)
        with self._lock:
            candidate = self._candidates.get(key)
        if candidate is None:
            raise LookupError("finalized candidate was not found")
        return candidate.model_copy(deep=True)

    def discard(self, change_set_id: str, candidate: AssetVersion) -> None:
        key = (candidate.asset_id, candidate.asset_version_id, change_set_id)
        with self._lock:
            existing = self._candidates.get(key)
            if existing is not None and existing != candidate:
                raise ValueError("cannot discard a different finalized candidate")
            self._candidates.pop(key, None)
