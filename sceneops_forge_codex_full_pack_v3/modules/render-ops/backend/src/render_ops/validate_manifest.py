"""Validate a RenderManifest JSON document and print a compact truthful summary."""

import json
from pathlib import Path
from typing import Optional, Sequence

from .schemas import RenderManifest, summarize_manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(argv or [])
    if len(args) != 1:
        raise SystemExit("usage: python -m render_ops.validate_manifest <manifest.json>")
    payload = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    summary = summarize_manifest(RenderManifest.model_validate(payload))
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
