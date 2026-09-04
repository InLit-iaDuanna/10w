"""Export the deterministic RenderManifest example."""

import json
from pathlib import Path
from typing import Optional, Sequence

from .fixtures import mock_manifest


def fixture_path() -> Path:
    return Path(__file__).resolve().parents[3] / "contracts/examples/render-manifest.mock.json"


def export_fixture(destination: Optional[Path] = None) -> Path:
    output = destination or fixture_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(mock_manifest().model_dump(mode="json"), indent=2, sort_keys=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    return output


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(argv or [])
    destination = Path(args[0]) if args else None
    print(export_fixture(destination))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
