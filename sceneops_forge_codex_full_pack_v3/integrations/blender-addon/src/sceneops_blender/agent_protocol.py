"""Strict, dependency-free protocol shared with the Blender main-thread bridge."""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path

CAPABILITIES = {"create_asset": "blender.asset.create", "export_asset": "blender.asset.export", "bootstrap_door": "blender.asset.begin", "open_source": "blender.asset.begin", "edit_nodes": "blender.asset.edit", "save_source": "blender.asset.edit", "export_source": "blender.asset.publish"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("invalid stable identifier")
    return value


def validate_command(command, binding):
    operation = command.get("operation")
    common = {"operation", "request_id", "authorization", "asset_id"}
    allowed = {
        "inspect": {"operation"}, "stop": {"operation"},
        "request_status": {"operation", "request_id"}, "cancel_request": {"operation", "request_id"},
        "create_asset": common | {"sceneops_id", "dimensions_m"},
        "export_asset": common,
        "bootstrap_door": common | {"candidate_id", "node_ids", "recipe"},
        "open_source": common | {"candidate_id"},
        "save_source": common | {"candidate_id"},
        "edit_nodes": common | {"candidate_id", "edits"},
        "export_source": common | {"candidate_id", "formats"},
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
    if operation in {"inspect", "request_status", "cancel_request"}:
        if operation != "inspect":
            identifier(command["request_id"])
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
    if "candidate_id" in command:
        identifier(command["candidate_id"])
    if operation == "bootstrap_door":
        ids = command["node_ids"]
        if not isinstance(ids, dict) or set(ids) != {"frame", "leaf", "hinge"} or len(set(ids.values())) != 3:
            raise ValueError("door requires distinct frame, leaf, hinge IDs")
        for value in ids.values():
            identifier(value)
        recipe = command["recipe"]
        if not isinstance(recipe, dict) or not {"width_m", "height_m", "thickness_m", "material"} <= set(recipe) or not set(recipe) <= {"width_m", "height_m", "thickness_m", "material", "frame_width_m"}:
            raise ValueError("invalid door recipe")
        for key in ("width_m", "height_m", "thickness_m"):
            bounded_values([recipe[key]], 1, 0.001, 100)
        frame = recipe.get("frame_width_m", 0.08)
        bounded_values([frame], 1, 0.001, 100)
        if frame * 2 >= min(recipe["width_m"], recipe["height_m"]):
            raise ValueError("frame width consumes door opening")
        material = recipe["material"]
        if not isinstance(material, dict) or set(material) != {"color_hex", "roughness", "metalness"} or not re.fullmatch(r"#[0-9a-fA-F]{6}", material.get("color_hex", "")):
            raise ValueError("invalid recipe material")
        bounded_values([material["roughness"], material["metalness"]], 2, 0, 1)
    if operation == "edit_nodes":
        edits = command["edits"]
        if not isinstance(edits, list) or not 1 <= len(edits) <= 64:
            raise ValueError("edits must contain 1 to 64 nodes")
        for edit in edits:
            if not isinstance(edit, dict) or not {"node_id"} < set(edit) or not set(edit) <= {"node_id", "dimensions_m", "base_color"}:
                raise ValueError("invalid typed node edit")
            identifier(edit["node_id"])
            if "dimensions_m" in edit:
                bounded_values(edit["dimensions_m"], 3, 0.001, 100)
            if "base_color" in edit:
                bounded_values(edit["base_color"], 4, 0, 1)
    if operation == "export_source" and (not isinstance(command["formats"], list) or not command["formats"] or len(set(command["formats"])) != len(command["formats"]) or not set(command["formats"]) <= {"glb", "fbx"}):
        raise ValueError("supported export formats are glb and fbx")
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


def bounded_values(values, count, low, high):
    if not isinstance(values, (list, tuple)) or len(values) != count or any(type(x) not in (int, float) or not math.isfinite(x) or not low <= x <= high for x in values):
        raise ValueError("values outside typed numeric bounds")
