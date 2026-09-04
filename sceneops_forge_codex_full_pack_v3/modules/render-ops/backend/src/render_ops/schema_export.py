"""Generate the versioned RenderManifest JSON Schema."""

import json
from pathlib import Path
from typing import Optional, Sequence

from .schemas import RenderManifest


def schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "contracts/manifests/render-manifest.v1.schema.json"


def export_schema(destination: Optional[Path] = None) -> Path:
    output = destination or schema_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(RenderManifest.model_json_schema(), indent=2, sort_keys=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    return output


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(argv or [])
    destination = Path(args[0]) if args else None
    print(export_schema(destination))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
