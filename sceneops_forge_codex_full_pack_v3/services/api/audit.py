"""Process-wide audit logging for the local SceneOps runtime.

The audit stream is deliberately separate from the bounded observability
projection. It is an append-only JSONL record of the local API and model
boundary while the activation marker exists. Payloads are redacted before
they leave the process, but prompt and response text is otherwise preserved.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from observability import REDACTED, REDACTED_PATH, Redactor


_SENSITIVE_KEY = re.compile(
    r"(?:api[-_]?key|access[-_]?token|refresh[-_]?token|token|secret|password|passwd|"
    r"authorization|cookie|credential|private[-_]?key|signature|session[-_]?key)",
    re.IGNORECASE,
)
_PATH_KEY = re.compile(r"(?:^|_)(?:path|root|cwd|directory|filename|file)(?:$|_)", re.IGNORECASE)
_SAFE_TEXT_KEYS = {
    "event",
    "route",
    "method",
    "provider",
    "model",
    "purpose",
    "source",
    "logger",
    "level",
    "status",
    "status_code",
    "content_type",
    "request_id",
    "correlation_id",
    "project_id",
    "run_id",
    "task_id",
    "job_id",
    "call_id",
    "phase",
    "event_type",
    "code",
}
_HANDLER_ATTRIBUTE = "_sceneops_audit_handler"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any, redactor: Redactor, *, key: str = "", depth: int = 0) -> Any:
    """Redact arbitrary audit payloads without imposing prompt-size limits."""
    if depth > 16:
        return "<nested-value-omitted>"
    if _SENSITIVE_KEY.search(key):
        return REDACTED
    if _PATH_KEY.search(key) and isinstance(value, str):
        return REDACTED_PATH
    if isinstance(value, dict):
        return {
            str(item_key): _json_safe(item, redactor, key=str(item_key), depth=depth + 1)
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, redactor, key=key, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if key in _SAFE_TEXT_KEYS:
            return value
        return redactor.redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return {"type": "bytes", "size": len(value)}
    return redactor.redact_text(repr(value))


class AuditFileHandler(logging.Handler):
    """Thread-safe JSONL handler controlled by an on-disk activation marker."""

    def __init__(self, log_path: Path, marker_path: Path) -> None:
        super().__init__(level=logging.INFO)
        self.log_path = log_path
        self.marker_path = marker_path
        self._redactor = Redactor()
        self._lock = threading.RLock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.log_path.open("a", encoding="utf-8", buffering=1)
        try:
            os.chmod(self.log_path, 0o600)
        except OSError:
            pass

    @property
    def active(self) -> bool:
        return self.marker_path.is_file()

    def emit(self, record: logging.LogRecord) -> None:
        if not self.active:
            return
        event = getattr(record, "sceneops_audit", None)
        if not isinstance(event, dict):
            event = {"event": "backend.log", "fields": {"message": record.getMessage()}}
        event_name = event.get("event")
        event_name = event_name if isinstance(event_name, str) and event_name else "backend.log"
        fields = event.get("fields", {})
        if not isinstance(fields, dict):
            fields = {"value": fields}
        entry = {
            "timestamp": _utc_now(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": event_name,
            "message": self._redactor.redact_text(record.getMessage()),
            "fields": _json_safe(fields, self._redactor),
        }
        try:
            with self._lock:
                self._stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
                self._stream.flush()
        except (OSError, TypeError, ValueError):
            # Audit failures must not take down the local application.
            return

    def close(self) -> None:
        with self._lock:
            try:
                self._stream.close()
            finally:
                super().close()


class AuditRuntime:
    """Owns the activation marker and the process-wide audit handler."""

    def __init__(self, data_dir: Path, handler: AuditFileHandler | None) -> None:
        self.data_dir = data_dir
        self.log_path = data_dir / "logs" / "sceneops-audit.jsonl"
        self.marker_path = data_dir / "audit_logging.enabled"
        self.handler = handler

    @property
    def active(self) -> bool:
        return self.handler is not None and self.handler.active


def configure_audit_logging(data_dir: Path) -> AuditRuntime:
    """Install the file sink once for the current API process."""
    marker_path = data_dir / "audit_logging.enabled"
    log_path = data_dir / "logs" / "sceneops-audit.jsonl"
    enabled = marker_path.is_file() or os.environ.get("SCENEOPS_AUDIT_LOGGING") == "1"
    if not enabled:
        return AuditRuntime(data_dir, None)

    root = logging.getLogger()
    existing = getattr(root, _HANDLER_ATTRIBUTE, None)
    if isinstance(existing, AuditFileHandler):
        return AuditRuntime(data_dir, existing)

    handler = AuditFileHandler(log_path, marker_path)
    setattr(root, _HANDLER_ATTRIBUTE, handler)
    root.setLevel(min(root.level or logging.INFO, logging.INFO))
    root.addHandler(handler)

    # Uvicorn keeps access/error loggers separate from the root logger.
    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if handler not in logger.handlers:
            logger.addHandler(handler)
    return AuditRuntime(data_dir, handler)


def audit_event(event: str, **fields: Any) -> str:
    """Append one structured record when audit logging is active."""
    event_id = str(uuid4())
    logging.getLogger("sceneops.audit").info(
        event,
        extra={"sceneops_audit": {"event": event, "fields": {"event_id": event_id, **fields}}},
    )
    return event_id


def audit_payload(value: Any) -> Any:
    """Return a redacted payload for callers that need a safe in-memory copy."""
    return _json_safe(value, Redactor())
