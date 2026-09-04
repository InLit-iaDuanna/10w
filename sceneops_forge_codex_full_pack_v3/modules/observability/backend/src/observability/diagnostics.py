"""Deterministic, redacted diagnostic bundle assembly."""

import io
import json
import zipfile
from datetime import datetime, timezone
from itertools import islice
from typing import Callable, Dict, Iterable, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .redaction import Redactor
from .schemas import STABLE_ID_PATTERN, ExecutionMode, StructuredLogEvent


class DiagnosticBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(pattern=STABLE_ID_PATTERN)
    correlation_id: Optional[str] = Field(default=None, pattern=STABLE_ID_PATTERN)


class DiagnosticBundleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    filename: str
    content_type: str = "application/zip"
    content: bytes
    mode: ExecutionMode
    log_count: int = Field(ge=0)


class DiagnosticBundleService:
    def __init__(
        self,
        redactor: Optional[Redactor] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._redactor = redactor or Redactor()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(
        self,
        request: DiagnosticBundleRequest,
        logs: Iterable[StructuredLogEvent],
        health_snapshots: Iterable[Dict[str, JsonValue]] = (),
        total_available: Optional[int] = None,
    ) -> DiagnosticBundleResult:
        scoped_logs = []
        discovered = 0
        for index, log in enumerate(logs):
            if index >= 10_000:
                raise ValueError("diagnostic input may not exceed 10000 log records")
            if not self._include(log, request):
                continue
            discovered += 1
            if len(scoped_logs) < 2000:
                scoped_logs.append(log)
        health_items = list(islice(health_snapshots, 101))
        if len(health_items) > 100:
            raise ValueError("diagnostic health snapshots may not exceed 100 entries")
        safe_logs = [self._redactor.redact_log(log).model_dump(mode="json") for log in scoped_logs]
        safe_health = self._redactor.redact_json(health_items)
        generated_at = self._utc_now()
        mode = self._derive_mode(scoped_logs)
        available = discovered if total_available is None else total_available
        manifest = {
            "schema_version": 1,
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "project_id": request.project_id,
            "correlation_id": request.correlation_id,
            "execution_mode": mode.value,
            "log_count": len(safe_logs),
            "logs_truncated": available > len(safe_logs),
            "redaction": {
                "applied": True,
                "policy_version": 1,
                "recognized_secrets_removed": True,
                "unrestricted_local_paths_removed": True,
            },
        }
        files = {
            "health.json": self._json_bytes(safe_health),
            "logs.jsonl": self._json_lines(safe_logs),
            "manifest.json": self._json_bytes(manifest),
        }
        content = self._zip(files)
        stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        return DiagnosticBundleResult(
            filename="sceneops-diagnostics-%s.zip" % stamp,
            content=content,
            mode=mode,
            log_count=len(safe_logs),
        )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("diagnostic clock must return UTC")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _derive_mode(logs: Iterable[StructuredLogEvent]) -> ExecutionMode:
        modes = {log.mode for log in logs}
        for mode in (
            ExecutionMode.BLOCKED,
            ExecutionMode.PLANNED,
            ExecutionMode.MOCK,
            ExecutionMode.CACHED,
            ExecutionMode.LIVE,
        ):
            if mode in modes:
                return mode
        return ExecutionMode.BLOCKED

    @staticmethod
    def _include(event: StructuredLogEvent, request: DiagnosticBundleRequest) -> bool:
        if event.context.project_id != request.project_id:
            return False
        if request.correlation_id and event.context.correlation_id != request.correlation_id:
            return False
        return True

    @staticmethod
    def _json_bytes(value: JsonValue) -> bytes:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def _json_lines(values: Iterable[JsonValue]) -> bytes:
        lines = [json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for value in values]
        return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")

    @staticmethod
    def _zip(files: Dict[str, bytes]) -> bytes:
        target = io.BytesIO()
        with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(files):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, files[name])
        return target.getvalue()
