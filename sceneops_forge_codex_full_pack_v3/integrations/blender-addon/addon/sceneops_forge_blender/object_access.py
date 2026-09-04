from __future__ import annotations

import math

import bpy

from .addon_helpers import material_records


def objects(command):
    requested = set(command.get("object_ids", []))
    values = list(bpy.context.scene.objects)
    if not requested:
        return values
    selected = [
        item
        for item in values
        if item.get("sceneops_id") in requested
        or item.get("sceneops_source_id") in requested
    ]
    found = {
        item.get("sceneops_id")
        for item in selected
        if item.get("sceneops_id") in requested
    }
    if found != requested:
        raise ValueError("one or more sceneops_id targets were not found")
    return selected


def object_record(item, include_materials=False):
    triangles = 0
    has_uv = False
    if item.type == "MESH":
        item.data.calc_loop_triangles()
        triangles = len(item.data.loop_triangles)
        has_uv = bool(item.data.uv_layers)
    record = {
        "name": item.name,
        "type": item.type,
        "sceneops_id": item.get("sceneops_id"),
        "location_m": list(item.location),
        "rotation_degrees": [math.degrees(value) for value in item.rotation_euler],
        "scale": list(item.scale),
        "triangle_count": triangles,
        "has_uv": has_uv,
    }
    if include_materials:
        record["materials"] = material_records(
            item.data.materials if item.type == "MESH" else []
        )
    return record
