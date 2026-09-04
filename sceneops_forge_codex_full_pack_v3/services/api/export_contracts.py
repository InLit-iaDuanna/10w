"""Export the unified API schema without importing or executing lab demos.

Run from the application root:
    .venv/bin/python services/api/export_contracts.py

Only a temporary empty workspace database is constructed. No server, request,
CLI, fixture-import endpoint, job, test or external adapter is executed.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "services/api/contracts/openapi.json")
    args = parser.parse_args()
    original_directory = os.environ.get("SCENEOPS_DATA_DIR")
    try:
        with TemporaryDirectory(prefix="sceneops-openapi-") as directory:
            os.environ["SCENEOPS_DATA_DIR"] = directory
            from services.api.app import create_app
            schema = create_app().openapi()
    finally:
        if original_directory is None:
            os.environ.pop("SCENEOPS_DATA_DIR", None)
        else:
            os.environ["SCENEOPS_DATA_DIR"] = original_directory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
