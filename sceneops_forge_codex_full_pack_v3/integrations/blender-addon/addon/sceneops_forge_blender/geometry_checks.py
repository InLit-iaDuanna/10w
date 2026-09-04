from __future__ import annotations

import bmesh
import bpy

from .object_access import objects


def check_geometry(command):
    parameters = command["parameters"]
    meshes = [item for item in objects(command) if item.type == "MESH"]
    requested = set(command.get("object_ids", []))
    primary_meshes = [
        item
        for item in meshes
        if not requested or item.get("sceneops_id") in requested
    ]
    triangle_count = 0
    has_uv = True
    material_count = 0
    texture_names = set()
    nonmanifold_edge_count = 0
    for item in primary_meshes:
        item.data.calc_loop_triangles()
        triangle_count += len(item.data.loop_triangles)
        has_uv = has_uv and bool(item.data.uv_layers)
        material_count += len(item.data.materials)
        editable_mesh = bmesh.new()
        try:
            editable_mesh.from_mesh(item.data)
            nonmanifold_edge_count += sum(
                1 for edge in editable_mesh.edges if not edge.is_manifold
            )
        finally:
            editable_mesh.free()
        for material in item.data.materials:
            if material and material.use_nodes:
                texture_names.update(
                    node.image.name
                    for node in material.node_tree.nodes
                    if node.type == "TEX_IMAGE" and node.image
                )
    geometry_passed = triangle_count <= parameters["triangle_budget"] and (
        parameters["allow_nonmanifold"] or nonmanifold_edge_count == 0
    )
    uv_passed = has_uv or not parameters["require_uv"]
    identity_values = [item.get("sceneops_id") for item in meshes]
    identity_passed = all(identity_values) and len(identity_values) == len(
        set(identity_values)
    )
    return {
        "metrics": {
            "dimensions_m": _combined_dimensions(primary_meshes),
            "triangle_count": triangle_count,
            "vertex_count": sum(len(item.data.vertices) for item in primary_meshes),
            "material_count": material_count,
            "texture_count": len(texture_names),
            "has_uv": has_uv,
            "is_rigged": any(item.find_armature() for item in primary_meshes),
            "animation_names": sorted(action.name for action in bpy.data.actions),
            "lod_count": len([item for item in meshes if "_LOD" in item.name]),
            "collider_kind": (
                "generated"
                if any(item.get("sceneops_collider") for item in meshes)
                else None
            ),
            "nonmanifold_edge_count": nonmanifold_edge_count,
        },
        "gates": [
            {
                "gate_id": "geometry",
                "status": "passed" if geometry_passed else "failed",
                "blocking": True,
                "measurements": {
                    "triangle_count": triangle_count,
                    "nonmanifold_edge_count": nonmanifold_edge_count,
                },
            },
            {
                "gate_id": "uv_material",
                "status": "passed" if uv_passed else "failed",
                "blocking": True,
            },
            {
                "gate_id": "identity",
                "status": "passed" if identity_passed else "failed",
                "blocking": True,
            },
        ],
    }


def _combined_dimensions(items):
    if not items:
        return {"x": 0, "y": 0, "z": 0}
    points = [item.matrix_world @ corner for item in items for corner in item.bound_box]
    return {
        axis: max(point[index] for point in points)
        - min(point[index] for point in points)
        for index, axis in enumerate(("x", "y", "z"))
    }
