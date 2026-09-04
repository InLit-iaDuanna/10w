"""Observable ingress/query gateway with idempotent reconnect semantics."""

import hashlib
import hmac
import json
import secrets
import threading
from collections import OrderedDict
from typing import Dict, Iterable, List, Optional, Protocol, Set, Tuple

from .redaction import Redactor
from .schemas import (
    EventBatch,
    GatewayEvent,
    LogLevel,
    LogPage,
    LogQuery,
    ProgressEvent,
    StructuredLogEvent,
)


DEFAULT_SEARCHABLE_FIELDS = {
    "artifact_id",
    "attempt",
    "code",
    "duration_ms",
    "integration_id",
    "operation",
    "queue_depth",
    "status",
}

_LEVEL_ORDER = {
    LogLevel.TRACE: 0,
    LogLevel.DEBUG: 1,
    LogLevel.INFO: 2,
    LogLevel.WARNING: 3,
    LogLevel.ERROR: 4,
    LogLevel.CRITICAL: 5,
}


class DuplicateEventConflict(ValueError):
    pass


class CursorExpiredError(ValueError):
    pass


class SearchFieldNotAllowed(ValueError):
    pass


class ObservabilityQueryPort(Protocol):
    def query_logs(self, query: LogQuery) -> LogPage:
        ...

    def events_after(self, project_id: str, cursor: Optional[str], limit: int = 500) -> EventBatch:
        ...


class ObservabilityGateway(ObservabilityQueryPort):
    """Thread-safe local projection; durable transport is supplied by composition."""

    def __init__(
        self,
        max_records: int = 10_000,
        searchable_fields: Optional[Iterable[str]] = None,
        redactor: Optional[Redactor] = None,
    ) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self._max_records = max_records
        self._searchable_fields: Set[str] = set(searchable_fields or DEFAULT_SEARCHABLE_FIELDS)
        self._redactor = redactor or Redactor()
        self._events: List[GatewayEvent] = []
        self._by_id: Dict[str, Tuple[GatewayEvent, bytes]] = {}
        self._pruned_through: "OrderedDict[str, int]" = OrderedDict()
        self._cursor_limit = max(128, max_records * 2)
        self._cursors: "OrderedDict[str, Tuple[str, int]]" = OrderedDict()
        self._expired_cursors: "OrderedDict[str, str]" = OrderedDict()
        self._fingerprint_key = secrets.token_bytes(32)
        self._next_sequence = 1
        self._lock = threading.RLock()

    def publish_log(self, event: StructuredLogEvent) -> StructuredLogEvent:
        self._validate_fields(event.fields.keys())
        fingerprint = self._fingerprint(event)
        safe_event = self._redactor.redact_log(event)
        return self._append(safe_event, fingerprint)  # type: ignore[return-value]

    def publish_progress(self, event: ProgressEvent) -> ProgressEvent:
        self._validate_fields(event.fields.keys())
        fingerprint = self._fingerprint(event)
        safe_event = event.model_copy(
            update={
                "message": self._redactor.redact_text(event.message),
                "fields": self._redactor.redact_json(event.fields),
            }
        )
        return self._append(safe_event, fingerprint)  # type: ignore[return-value]

    def events_after(self, project_id: str, cursor: Optional[str], limit: int = 500) -> EventBatch:
        if limit < 1 or limit > 2000:
            raise ValueError("limit must be between 1 and 2000")
        with self._lock:
            project_events = [event for event in self._events if event.context.project_id == project_id]
            if cursor is None:
                sequence = ((project_events[0].sequence or 1) - 1) if project_events else self._next_sequence - 1
            else:
                sequence = self._decode_cursor(project_id, cursor)
                if sequence < self._pruned_through.get(project_id, 0):
                    raise CursorExpiredError("cursor has been pruned; requery the current projection")
            oldest = project_events[0].sequence if project_events else None
            if oldest is not None and sequence < oldest - 1:
                raise CursorExpiredError("cursor has been pruned; requery the current projection")
            events = [event for event in project_events if (event.sequence or 0) > sequence][:limit]
            next_sequence = events[-1].sequence if events else sequence
            return EventBatch(
                events=events,
                next_cursor=self._encode_cursor(project_id, next_sequence or 0),
            )

    def query_logs(self, query: LogQuery) -> LogPage:
        self._validate_fields(query.field_equals.keys())
        with self._lock:
            logs = [event for event in self._events if isinstance(event, StructuredLogEvent)]
            matches = [event for event in logs if self._matches(event, query)]
            return LogPage(items=matches[: query.limit], total=len(matches))

    def _append(self, event: GatewayEvent, fingerprint: bytes) -> GatewayEvent:
        if event.sequence is not None:
            raise ValueError("producers may not assign observability sequence numbers")
        with self._lock:
            existing = self._by_id.get(event.event_id)
            if existing is not None:
                stored, stored_fingerprint = existing
                if not hmac.compare_digest(stored_fingerprint, fingerprint):
                    raise DuplicateEventConflict("event_id was reused with a different payload")
                return stored
            stored = event.model_copy(update={"sequence": self._next_sequence})
            self._next_sequence += 1
            self._events.append(stored)
            self._by_id[stored.event_id] = (stored, fingerprint)
            if len(self._events) > self._max_records:
                removed = self._events[: -self._max_records]
                self._events = self._events[-self._max_records :]
                for expired in removed:
                    self._by_id.pop(expired.event_id, None)
                    project_id = expired.context.project_id
                    self._pruned_through[project_id] = max(
                        self._pruned_through.get(project_id, 0),
                        expired.sequence or 0,
                    )
                    self._pruned_through.move_to_end(project_id)
                    while len(self._pruned_through) > self._cursor_limit:
                        self._pruned_through.popitem(last=False)
            return stored

    def _matches(self, event: StructuredLogEvent, query: LogQuery) -> bool:
        context = event.context
        exact = (
            (query.project_id, context.project_id),
            (query.run_id, context.run_id),
            (query.job_id, context.job_id),
            (query.correlation_id, context.correlation_id),
            (query.source_module, event.source_module),
            (query.source_tool, event.source_tool),
        )
        if any(expected is not None and expected != actual for expected, actual in exact):
            return False
        if query.minimum_level is not None and _LEVEL_ORDER[event.level] < _LEVEL_ORDER[query.minimum_level]:
            return False
        if any(event.fields.get(key) != value for key, value in query.field_equals.items()):
            return False
        if query.text:
            haystack = "%s %s" % (event.message, json.dumps(event.fields, ensure_ascii=False, sort_keys=True))
            if query.text.casefold() not in haystack.casefold():
                return False
        return True

    def _validate_fields(self, keys: Iterable[str]) -> None:
        unsupported = sorted(set(keys) - self._searchable_fields)
        if unsupported:
            raise SearchFieldNotAllowed("structured fields contain names outside the configured allowlist")

    def _fingerprint(self, event: GatewayEvent) -> bytes:
        payload = json.dumps(
            event.model_dump(mode="json", exclude={"sequence"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._fingerprint_key, payload, hashlib.sha256).digest()

    def _encode_cursor(self, project_id: str, sequence: int) -> str:
        cursor = "obs_" + secrets.token_urlsafe(24)
        self._cursors[cursor] = (project_id, sequence)
        self._cursors.move_to_end(cursor)
        while len(self._cursors) > self._cursor_limit:
            expired, (expired_project_id, _sequence) = self._cursors.popitem(last=False)
            self._expired_cursors[expired] = expired_project_id
            while len(self._expired_cursors) > self._cursor_limit:
                self._expired_cursors.popitem(last=False)
        return cursor

    def _decode_cursor(self, project_id: str, cursor: str) -> int:
        state = self._cursors.get(cursor)
        if state is None:
            expired_project_id = self._expired_cursors.get(cursor)
            if expired_project_id is not None and expired_project_id != project_id:
                raise ValueError("cursor is not valid for this project")
            if expired_project_id is not None:
                raise CursorExpiredError("cursor is no longer retained; requery the current projection")
            raise ValueError("cursor is invalid or no longer retained")
        cursor_project_id, sequence = state
        if cursor_project_id != project_id:
            raise ValueError("cursor is not valid for this project")
        self._cursors.move_to_end(cursor)
        return sequence
