"""Boundary redaction for logs and downloadable diagnostics."""

import re
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import JsonValue

from .schemas import ArtifactLink, StructuredLogEvent


REDACTED = "<redacted>"
REDACTED_PATH = "<redacted-path>"

_SENSITIVE_KEY = re.compile(
    r"(?:api[-_]?key|access[-_]?token|refresh[-_]?token|token|secret|password|passwd|"
    r"authorization|cookie|credential|private[-_]?key|signature|session[-_]?key)",
    re.IGNORECASE,
)
_PATH_KEY = re.compile(r"(?:^|_)(?:path|root|cwd|directory|filename|file)(?:$|_)", re.IGNORECASE)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_ENCODED_BEARER = re.compile(r"\bBearer(?:%20|\+)[A-Za-z0-9._~%+/=-]+", re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r"\b([A-Za-z0-9_-]*(?:api[-_]?key|token|secret|password|passwd|authorization|cookie|"
    r"credential|private[-_]?key|signature|session[-_]?key)[A-Za-z0-9_-]*)"
    r"\s*([:=])\s*(\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+", re.IGNORECASE)
_POSIX_PATH = re.compile(r"(?<!\w)/(?:[^/\s<>\"']+(?:/[^/\s<>\"']*)*)")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s<>\"']+")


class Redactor:
    """Redacts secret-bearing keys, credentials, and unrestricted local paths."""

    def redact_text(self, value: str) -> str:
        held_urls: List[str] = []

        def hold_url(match: re.Match) -> str:
            held_urls.append(self._redact_url(match.group(0)))
            return "__SCENEOPS_SAFE_URL_%d__" % (len(held_urls) - 1)

        result = _URL.sub(hold_url, value)
        result = _BEARER.sub("Bearer " + REDACTED, result)
        result = _ENCODED_BEARER.sub("Bearer%20" + REDACTED, result)
        result = _ASSIGNMENT.sub(lambda match: "%s%s%s" % (match.group(1), match.group(2), REDACTED), result)
        result = _POSIX_PATH.sub(REDACTED_PATH, result)
        result = _WINDOWS_PATH.sub(REDACTED_PATH, result)
        for index, safe_url in enumerate(held_urls):
            result = result.replace("__SCENEOPS_SAFE_URL_%d__" % index, safe_url)
        return result

    def redact_json(self, value: JsonValue, key: str = "", _depth: int = 0) -> JsonValue:
        if _depth > 8:
            raise ValueError("redaction input exceeds maximum nesting depth")
        if _SENSITIVE_KEY.search(key):
            return REDACTED
        if _PATH_KEY.search(key) and isinstance(value, str):
            return REDACTED_PATH
        if isinstance(value, dict):
            if len(value) > 128:
                raise ValueError("redaction object exceeds maximum field count")
            return {
                item_key: self.redact_json(item, item_key, _depth + 1)
                for item_key, item in value.items()
            }
        if isinstance(value, list):
            if len(value) > 256:
                raise ValueError("redaction array exceeds maximum item count")
            return [self.redact_json(item, key, _depth + 1) for item in value]
        if isinstance(value, str):
            if len(value) > 10_000:
                raise ValueError("redaction string exceeds maximum length")
            return self.redact_text(value)
        return value

    def redact_log(self, event: StructuredLogEvent) -> StructuredLogEvent:
        links = [
            ArtifactLink(
                artifact_id=link.artifact_id,
                label=self.redact_text(link.label),
                media_type=link.media_type,
            )
            for link in event.artifact_links
        ]
        return event.model_copy(
            update={
                "message": self.redact_text(event.message),
                "fields": self.redact_json(event.fields),
                "artifact_links": links,
            }
        )

    @staticmethod
    def _redact_url(value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme.casefold() == "file":
            return "file:///" + REDACTED_PATH
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = "[%s]" % hostname
        try:
            if parts.port is not None:
                hostname = "%s:%d" % (hostname, parts.port)
        except ValueError:
            return "%s://%s" % (parts.scheme, REDACTED)
        query: List[Tuple[str, str]] = []
        for key, _item in parse_qsl(parts.query, keep_blank_values=True):
            query.append((key, REDACTED))
        path = "/" + REDACTED_PATH if parts.path and parts.path != "/" else parts.path
        fragment = REDACTED if parts.fragment else ""
        return urlunsplit((parts.scheme, hostname, path, urlencode(query), fragment))
