from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List


def artifact_sha256(path: Path) -> str:
    """Artifact integrity checksum required by the public provenance contract."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_mock_glb(identities: List[str]) -> bytes:
    document = {
        "asset": {"version": "2.0", "generator": "SceneOps deterministic mock"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(identities)))}],
        "nodes": [
            {"name": "MockObject%d" % index, "extras": {"sceneops_id": identity}}
            for index, identity in enumerate(identities)
        ],
    }
    json_chunk = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total_length = 12 + 8 + len(json_chunk)
    return struct.pack("<4sII", b"glTF", 2, total_length) + struct.pack(
        "<I4s", len(json_chunk), b"JSON"
    ) + json_chunk


def read_glb_json(path: Path) -> Dict[str, object]:
    payload = path.read_bytes()
    if len(payload) < 20:
        raise ValueError("GLB is too short")
    magic, version, total_length = struct.unpack("<4sII", payload[:12])
    chunk_length, chunk_type = struct.unpack("<I4s", payload[12:20])
    if magic != b"glTF" or version != 2 or total_length != len(payload) or chunk_type != b"JSON":
        raise ValueError("invalid GLB header")
    return json.loads(payload[20 : 20 + chunk_length].decode("utf-8").rstrip(" \x00"))
