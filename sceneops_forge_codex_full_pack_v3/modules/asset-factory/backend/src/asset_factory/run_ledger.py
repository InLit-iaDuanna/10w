from __future__ import annotations

import json
from threading import Event, Lock
from typing import Dict, Optional, Protocol, Set, Tuple

from .errors import PipelineConflictError
from .schemas import PipelineRequest, PipelineRun


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class RequestLedgerPort(Protocol):
    def reserve(self, request: PipelineRequest) -> Optional[PipelineRun]: ...

    def complete(self, request: PipelineRequest, run: PipelineRun) -> PipelineRun: ...

    def abort(self, request: PipelineRequest) -> None: ...

    def token_for(self, pipeline_run_id: str) -> CancellationToken: ...

    def cancel(self, pipeline_run_id: str) -> None: ...


class InMemoryRequestLedger:
    """Atomic in-process reservation; durable storage replaces it at composition time."""

    def __init__(self) -> None:
        self._completed: Dict[str, Tuple[str, PipelineRun]] = {}
        self._inflight: Dict[str, Tuple[str, str]] = {}
        self._aborted: Set[str] = set()
        self._run_ids: Set[str] = set()
        self._tokens: Dict[str, CancellationToken] = {}
        self._lock = Lock()

    def reserve(self, request: PipelineRequest) -> Optional[PipelineRun]:
        signature = _request_signature(request)
        with self._lock:
            prior = self._completed.get(request.idempotency_key)
            if prior is not None:
                prior_signature, prior_run = prior
                if signature != prior_signature:
                    raise PipelineConflictError("IDEMPOTENCY_CONFLICT")
                return prior_run.model_copy(deep=True)
            if request.idempotency_key in self._aborted:
                raise PipelineConflictError("IDEMPOTENCY_ABORTED")
            inflight = self._inflight.get(request.idempotency_key)
            if inflight is not None:
                if inflight != (signature, request.pipeline_run_id):
                    raise PipelineConflictError("IDEMPOTENCY_CONFLICT")
                raise PipelineConflictError("IDEMPOTENCY_IN_PROGRESS")
            if request.pipeline_run_id in self._run_ids:
                raise PipelineConflictError("PIPELINE_RUN_ID_CONFLICT")
            self._inflight[request.idempotency_key] = (
                signature,
                request.pipeline_run_id,
            )
            self._run_ids.add(request.pipeline_run_id)
        return None

    def complete(self, request: PipelineRequest, run: PipelineRun) -> PipelineRun:
        signature = _request_signature(request)
        stored = run.model_copy(deep=True)
        with self._lock:
            self._inflight.pop(request.idempotency_key, None)
            self._completed[request.idempotency_key] = (signature, stored)
        return stored.model_copy(deep=True)

    def abort(self, request: PipelineRequest) -> None:
        with self._lock:
            self._inflight.pop(request.idempotency_key, None)
            self._aborted.add(request.idempotency_key)

    def token_for(self, pipeline_run_id: str) -> CancellationToken:
        with self._lock:
            if pipeline_run_id not in self._run_ids:
                raise KeyError(pipeline_run_id)
            return self._tokens.setdefault(pipeline_run_id, CancellationToken())

    def cancel(self, pipeline_run_id: str) -> None:
        self.token_for(pipeline_run_id).cancel()


def _request_signature(request: PipelineRequest) -> str:
    return json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
