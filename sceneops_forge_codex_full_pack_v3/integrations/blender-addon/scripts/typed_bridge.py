"""Bundled Blender entrypoint. It accepts one validated JSON command argument."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


RESULT_PREFIX = "SCENEOPS_RESULT="


def main():
    separator = sys.argv.index("--")
    arguments = sys.argv[separator + 1 :]
    if len(arguments) != 1:
        raise ValueError("typed bridge requires exactly one JSON request")
    command = json.loads(arguments[0])
    if not isinstance(command, dict):
        raise ValueError("typed bridge request must be an object")
    addon_root = Path(__file__).resolve().parents[1] / "addon"
    sys.path.insert(0, str(addon_root))
    from sceneops_forge_blender.dispatcher import dispatch

    data = dispatch(command)
    result = {
        "succeeded": True,
        "data": data,
        "logs": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "level": "info",
                "code": "BLENDER_OPERATION_COMPLETED",
                "message": "Typed Blender operation completed.",
                "request_id": command["request_id"],
            }
        ],
    }
    print(RESULT_PREFIX + json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        failure = {
            "succeeded": False,
            "data": {},
            "logs": [],
            "retryable": False,
            "error_code": "BLENDER_COMMAND_FAILED",
            "error_message": str(error),
        }
        print(RESULT_PREFIX + json.dumps(failure, sort_keys=True, separators=(",", ":")))
