"""Canonical SHA-256 helpers for the release integrity boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def canonical_sha256(payload: Dict[str, Any]) -> str:
    """Hash a JSON-compatible payload with stable ordering and encoding."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    """Hash artifact bytes without loading an entire build into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
