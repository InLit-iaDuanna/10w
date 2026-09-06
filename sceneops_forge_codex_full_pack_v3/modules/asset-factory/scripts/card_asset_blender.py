"""Blender entrypoint for allowlisted card-asset operations."""
from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path


def _arguments():
    marker = sys.argv.index("--")
    values = sys.argv[marker + 1:]
    if len(values) != 2:
        raise ValueError("card asset worker requires request and result paths")
    return Path(values[0]), Path(values[1])


def _clear(bpy):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def _hex_color(value):
    return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)) + (1.0,)


def _create(bpy, payload):
    _clear(bpy)
    created = []
    for index, part in enumerate(payload["parts"]):
        kind = part["kind"]
        if kind == "cube":
            bpy.ops.mesh.primitive_cube_add()
        elif kind == "sphere":
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2)
        elif kind == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(vertices=24)
        elif kind == "cone":
            bpy.ops.mesh.primitive_cone_add(vertices=24)
        else:
            raise ValueError("unsupported primitive")
        item = bpy.context.object
        item.name = part["name"]
        item.dimensions = part["dimensions_m"]
        item.location = part["location_m"]
        item.rotation_euler = [math.radians(value) for value in part["rotation_deg"]]
        item["sceneops_id"] = payload["object_ids"][index]
        item["sceneops_asset_id"] = payload["asset_id"]
        material = bpy.data.materials.new(part["name"] + " Material")
        material.diffuse_color = _hex_color(part["color"])
        material.use_nodes = True
        material.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = material.diffuse_color
        item.data.materials.append(material)
        created.append(item)
    bpy.context.view_layer.update()
    return created


def _import(bpy, payload):
    _clear(bpy)
    source = payload["input_path"]
    suffix = Path(source).suffix.casefold()
    if suffix == ".glb":
        bpy.ops.import_scene.gltf(filepath=source)
    elif suffix == ".fbx":
        try:
            bpy.ops.import_scene.fbx(filepath=source)
        except AttributeError:
            bpy.ops.wm.fbx_import(filepath=source)
    else:
        raise ValueError("only GLB and FBX imports are allowed")
    objects = [item for item in bpy.context.scene.objects if item.type in {"MESH", "ARMATURE", "EMPTY"}]
    meshes = [item for item in objects if item.type == "MESH"]
    if not meshes:
        raise ValueError("the imported file contains no mesh objects")
    for index, item in enumerate(objects):
        item["sceneops_id"] = payload["object_ids"][index]
        item["sceneops_asset_id"] = payload["asset_id"]
    bpy.context.view_layer.update()
    return objects


def _world_bounds(bpy):
    from mathutils import Vector
    meshes = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    if not meshes:
        raise ValueError("asset contains no mesh objects")
    points = [item.matrix_world @ Vector(corner) for item in meshes for corner in item.bound_box]
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return minimum, maximum


def _normalize(bpy, payload):
    source = payload["input_path"]
    bpy.ops.wm.open_mainfile(filepath=source, load_ui=False)
    minimum, maximum = _world_bounds(bpy)
    extent = max(maximum[axis] - minimum[axis] for axis in range(3))
    if extent <= 0:
        raise ValueError("asset bounds are empty")
    roots = [item for item in bpy.context.scene.objects if item.parent is None]
    pivot = bpy.data.objects.new("SceneOps Normalize", None)
    pivot["sceneops_id"] = payload["object_ids"][0]
    pivot["sceneops_asset_id"] = payload["asset_id"]
    bpy.context.scene.collection.objects.link(pivot)
    for item in roots:
        matrix = item.matrix_world.copy()
        item.parent = pivot
        item.matrix_world = matrix
    factor = payload["target_extent_m"] / extent
    pivot.scale = (factor, factor, factor)
    bpy.context.view_layer.update()
    minimum, maximum = _world_bounds(bpy)
    pivot.location.x += -(minimum[0] + maximum[0]) / 2
    pivot.location.y += -(minimum[1] + maximum[1]) / 2
    pivot.location.z += -minimum[2]
    bpy.context.view_layer.update()
    return [item for item in bpy.context.scene.objects if item.type in {"MESH", "ARMATURE", "EMPTY"}]


def _select_and_export(bpy, objects, payload):
    output = payload["output"]
    for path in output.values():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=output["blend"], check_existing=False)
    bpy.ops.object.select_all(action="DESELECT")
    for item in objects:
        if item.name in bpy.context.scene.objects:
            item.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = next((item for item in objects if item.type == "MESH"), objects[0])
    bpy.ops.export_scene.gltf(filepath=output["preview"], export_format="GLB", export_extras=True,
                              use_selection=True, export_yup=True)
    try:
        bpy.ops.export_scene.fbx(filepath=output["fbx"], use_selection=True, use_custom_props=True)
    except AttributeError:
        bpy.ops.wm.fbx_export(filepath=output["fbx"], selected_objects_only=True)


def _result(bpy, payload, objects):
    minimum, maximum = _world_bounds(bpy)
    meshes = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    return {
        "ok": True,
        "dimensions_m": [round(maximum[i] - minimum[i], 6) for i in range(3)],
        "vertex_count": sum(len(item.data.vertices) for item in meshes),
        "triangle_count": sum(max(0, len(face.vertices) - 2) for item in meshes for face in item.data.polygons),
        "object_ids": [str(item.get("sceneops_id")) for item in objects if item.get("sceneops_id")],
        "blender_version": bpy.app.version_string,
    }


def main():
    import bpy
    request_path, result_path = _arguments()
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    if payload["operation"] == "import":
        objects = _import(bpy, payload)
    elif payload["operation"] == "create":
        objects = _create(bpy, payload)
    elif payload["operation"] == "normalize":
        objects = _normalize(bpy, payload)
    else:
        raise ValueError("unsupported operation")
    _select_and_export(bpy, objects, payload)
    result_path.write_text(json.dumps(_result(bpy, payload, objects)), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        try:
            _, result_path = _arguments()
            result_path.write_text(json.dumps({"ok": False, "error": str(error), "trace": traceback.format_exc(limit=8)}), encoding="utf-8")
        finally:
            raise
