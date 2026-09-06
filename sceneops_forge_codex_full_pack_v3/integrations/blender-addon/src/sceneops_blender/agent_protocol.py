"""Strict, dependency-free protocol shared with the Blender main-thread bridge."""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path

CAPABILITIES = {"create_asset": "blender.asset.create", "export_asset": "blender.asset.export"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("invalid stable identifier")
    return value


def validate_command(command, binding):
    operation = command.get("operation")
    common = {"operation", "request_id", "authorization", "asset_id"}
    allowed = {
        "inspect": {"operation"}, "stop": {"operation"},
        "create_asset": common | {"sceneops_id", "dimensions_m"},
        "export_asset": common,
    }
    keys = set(command)
    if operation == "create_asset" and "name" in command:
        keys.remove("name")
        if not isinstance(command["name"], str) or not 1 <= len(command["name"]) <= 80 or any(ord(c) < 32 for c in command["name"]):
            raise ValueError("asset display name must contain 1 to 80 printable characters")
    if operation not in allowed or keys != allowed[operation]:
        raise ValueError("operation or parameter keys are not allowlisted")
    if operation == "stop":
        return
    validate_binding(binding)
    if operation == "inspect":
        if "blender.scene.inspect" not in binding["allowed_capabilities"]:
            raise ValueError("scene reading is outside the session grant")
        return
    identifier(command["request_id"])
    identifier(command["asset_id"])
    auth = command["authorization"]
    if not isinstance(auth, dict):
        raise ValueError("task authorization is required")
    for key in ("task_id", "grant_id", "project_id", "action_id", "change_set_id", "approval_id"):
        identifier(auth.get(key))
    for key in ("task_id", "grant_id", "project_id", "workspace_root", "expires_at", "allowed_capabilities"):
        if auth[key] != binding.get(key):
            raise ValueError("authorization does not match this task session")
    if auth.get("capability_id") != CAPABILITIES[operation]:
        raise ValueError("authorization does not cover requested capability")
    if CAPABILITIES[operation] not in binding.get("allowed_capabilities", []):
        raise ValueError("capability is outside the session grant")
    expiry = datetime.fromisoformat(binding["expires_at"].replace("Z", "+00:00"))
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise ValueError("task authorization expired")
    if operation == "create_asset":
        identifier(command["sceneops_id"])
        dimensions = command["dimensions_m"]
        if not isinstance(dimensions, (list, tuple)) or len(dimensions) != 3:
            raise ValueError("dimensions_m requires three meters values")
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0.001 <= x <= 100 for x in dimensions):
            raise ValueError("dimensions must be finite and between 0.001 and 100 meters")


def validate_binding(binding):
    for key in ("task_id", "grant_id", "project_id"):
        identifier(binding.get(key))
    capabilities = binding.get("allowed_capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
        raise ValueError("invalid Blender grant capabilities")
    expiry = datetime.fromisoformat(binding["expires_at"].replace("Z", "+00:00"))
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise ValueError("task authorization expired")
    if not Path(binding["workspace_root"]).is_absolute():
        raise ValueError("grant workspace root must be absolute")
    return {key: binding[key] for key in ("task_id", "grant_id", "project_id", "workspace_root", "allowed_capabilities", "expires_at")}
