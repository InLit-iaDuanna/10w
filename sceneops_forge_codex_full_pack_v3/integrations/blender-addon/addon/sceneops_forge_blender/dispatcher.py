from __future__ import annotations

import math
import uuid
from pathlib import Path

import bpy

from .addon_helpers import bounding_box_geometry
from .geometry_checks import check_geometry as _check_geometry
from .object_access import object_record as _object_record
from .object_access import objects as _objects
from .runtime_safety import (
    PERSISTENT_SCENE_MUTATIONS,
    completed_result,
    mutation_lock,
    record_completed_result,
    sanitize_scene,
    validate_paths,
)


ALLOWED_OPERATIONS = {
    "scan_scene",
    "assign_stable_ids",
    "inspect_object",
    "set_transform",
    "set_normals",
    "set_material_parameter",
    "set_light_parameter",
    "capture_context",
    "render_aov",
    "check_geometry",
    "generate_lod",
    "generate_collider",
    "save_snapshot",
    "rollback_snapshot",
    "export_asset",
}

READ_ONLY_OPERATIONS = {"scan_scene", "inspect_object", "capture_context", "check_geometry"}
def dispatch(command):
    operation = command.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError("operation is not allowlisted")
    if command.get("dry_run"):
        raise ValueError("dry-run commands cannot execute in Blender")
    if operation not in READ_ONLY_OPERATIONS:
        authorization = command.get("authorization") or {}
        if not authorization.get("change_set_id") or not authorization.get("approval_id"):
            raise ValueError("mutating Blender command lacks ChangeSet approval")
    validate_paths(command)
    source_path = command.get("source_path")
    if operation in PERSISTENT_SCENE_MUTATIONS:
        with mutation_lock(command):
            bpy.ops.wm.open_mainfile(filepath=source_path)
            sanitize_scene()
            prior = completed_result(command)
            if prior is not None:
                return prior
            result = globals()["_" + operation](command)
            bpy.ops.wm.save_as_mainfile(filepath=source_path)
            record_completed_result(command, result)
            return result
    if source_path:
        bpy.ops.wm.open_mainfile(filepath=source_path)
        sanitize_scene()
    return globals()["_" + operation](command)


def _scan_scene(command):
    include_hidden = bool(command.get("parameters", {}).get("include_hidden", False))
    objects = [item for item in bpy.context.scene.objects if include_hidden or not item.hide_get()]
    return {
        "scene": bpy.context.scene.name,
        "objects": [_object_record(item) for item in sorted(objects, key=lambda value: value.name)],
    }


def _assign_stable_ids(command):
    assignments = command.get("parameters", {}).get("identity_assignments", {})
    requested = set(command.get("object_ids", []))
    candidates = [
        item
        for item in bpy.context.scene.objects
        if item.name in assignments or item.get("sceneops_id") in requested
    ]
    if not candidates:
        candidates = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    seen = set()
    changed = []
    for item in sorted(candidates, key=lambda value: value.name):
        requested = assignments.get(item.name)
        current = item.get("sceneops_id")
        if requested:
            current = requested
        if not current or current in seen:
            current = "sop_" + uuid.uuid4().hex
        seen.add(current)
        if item.get("sceneops_id") != current:
            item["sceneops_id"] = current
            changed.append(current)
        item["sceneops_asset_member"] = True
    return {"assigned_sceneops_ids": sorted(seen), "changed_sceneops_ids": changed}


def _inspect_object(command):
    include_materials = command["parameters"]["include_materials"]
    return {
        "objects": [
            _object_record(item, include_materials=include_materials)
            for item in _objects(command)
        ]
    }


def _set_transform(command):
    parameters = command["parameters"]
    for item in _objects(command):
        if "location_m" in parameters:
            item.location = parameters["location_m"]
        if "rotation_degrees" in parameters:
            item.rotation_euler = [math.radians(value) for value in parameters["rotation_degrees"]]
        if "scale" in parameters:
            item.scale = parameters["scale"]
    return {"changed_object_ids": command.get("object_ids", [])}


def _set_normals(command):
    mode = command["parameters"]["mode"]
    for item in _objects(command):
        if item.type != "MESH":
            continue
        bpy.context.view_layer.objects.active = item
        item.select_set(True)
        if mode == "recalculate_outside":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")
        else:
            item.data.set_sharp_from_angle(
                angle=math.radians(command["parameters"].get("angle_degrees", 30))
            )
        item.select_set(False)
    return {"changed_object_ids": command.get("object_ids", [])}


def _set_material_parameter(command):
    parameters = command["parameters"]
    material = bpy.data.materials.get(parameters["material_name"])
    if material is None or not material.use_nodes:
        raise ValueError("material or Principled BSDF node was not found")
    node = next((item for item in material.node_tree.nodes if item.type == "BSDF_PRINCIPLED"), None)
    if node is None:
        raise ValueError("Principled BSDF node was not found")
    sockets = {"base_color": "Base Color", "metallic": "Metallic", "roughness": "Roughness", "alpha": "Alpha"}
    node.inputs[sockets[parameters["parameter"]]].default_value = parameters["value"]
    return {"material": material.name, "parameter": parameters["parameter"]}


def _set_light_parameter(command):
    parameters = command["parameters"]
    light = bpy.data.lights.get(parameters["light_name"])
    if light is None:
        raise ValueError("light was not found")
    parameter = parameters["parameter"]
    if parameter == "temperature":
        light.use_temperature = True
        light.temperature = parameters["value"]
    else:
        setattr(light, parameter, parameters["value"])
    return {"light": light.name, "parameter": parameter}


def _capture_context(command):
    scene = bpy.context.scene
    requested_camera = command.get("parameters", {}).get("camera_name")
    camera = bpy.data.objects.get(requested_camera) if requested_camera else scene.camera
    if requested_camera and (camera is None or camera.type != "CAMERA"):
        raise ValueError("requested camera was not found")
    return {
        "scene": scene.name,
        "camera": camera.name if camera else None,
        "camera_matrix_world": [list(row) for row in camera.matrix_world] if camera else None,
        "objects": [_object_record(item) for item in _objects(command)],
    }


def _render_aov(command):
    parameters = command["parameters"]
    scene = bpy.context.scene
    if parameters.get("camera_name"):
        camera = bpy.data.objects.get(parameters["camera_name"])
        if camera is None or camera.type != "CAMERA":
            raise ValueError("requested camera was not found")
        scene.camera = camera
    view_layer = bpy.context.view_layer
    view_layer.use_pass_z = "depth" in parameters["passes"]
    view_layer.use_pass_normal = "normal" in parameters["passes"]
    view_layer.use_pass_object_index = "object_id" in parameters["passes"]
    view_layer.use_pass_material_index = "material_id" in parameters["passes"]
    scene.render.resolution_x = parameters.get("width", 512)
    scene.render.resolution_y = parameters.get("height", 512)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = parameters["samples"]
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    scene.render.filepath = command["output_paths"][0]
    bpy.ops.render.render(write_still=True)
    return {"passes": parameters["passes"], "output_path": command["output_paths"][0]}


def _generate_lod(command):
    existing = [
        item.get("sceneops_id")
        for item in bpy.context.scene.objects
        if item.get("sceneops_operation_id") == command["request_id"]
    ]
    if existing:
        return {"created_sceneops_ids": sorted(existing)}
    created = []
    for source in _objects(command):
        if source.type != "MESH":
            continue
        for index, ratio in enumerate(command["parameters"]["ratios"], start=1):
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = "%s_LOD%d" % (source.name, index)
            duplicate["sceneops_id"] = "sop_" + uuid.uuid4().hex
            duplicate["sceneops_source_id"] = source.get("sceneops_id")
            duplicate["sceneops_operation_id"] = command["request_id"]
            duplicate["sceneops_asset_member"] = True
            bpy.context.collection.objects.link(duplicate)
            modifier = duplicate.modifiers.new(name="SceneOpsLOD", type="DECIMATE")
            modifier.ratio = ratio
            created.append(duplicate["sceneops_id"])
    return {"created_sceneops_ids": created}


def _generate_collider(command):
    existing = [
        item.get("sceneops_id")
        for item in bpy.context.scene.objects
        if item.get("sceneops_operation_id") == command["request_id"]
    ]
    if existing:
        return {
            "created_sceneops_ids": sorted(existing),
            "method": command["parameters"]["method"],
        }
    method = command["parameters"]["method"]
    created = []
    for source in _objects(command):
        if source.type != "MESH":
            continue
        if method == "bounding_box":
            vertices, faces = bounding_box_geometry(source.bound_box)
            mesh = bpy.data.meshes.new(source.name + "_COLLIDER_MESH")
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            duplicate = bpy.data.objects.new(source.name + "_COLLIDER", mesh)
            duplicate.matrix_world = source.matrix_world.copy()
        else:
            duplicate = source.copy()
            duplicate.data = source.data.copy()
        duplicate.name = source.name + "_COLLIDER"
        duplicate["sceneops_id"] = "sop_" + uuid.uuid4().hex
        duplicate["sceneops_source_id"] = source.get("sceneops_id")
        duplicate["sceneops_operation_id"] = command["request_id"]
        duplicate["sceneops_asset_member"] = True
        duplicate["sceneops_collider"] = method
        bpy.context.collection.objects.link(duplicate)
        if method == "convex_hull":
            bpy.ops.object.select_all(action="DESELECT")
            bpy.context.view_layer.objects.active = duplicate
            duplicate.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.convex_hull()
            bpy.ops.object.mode_set(mode="OBJECT")
            duplicate.select_set(False)
        created.append(duplicate["sceneops_id"])
    return {"created_sceneops_ids": created, "method": method}


def _save_snapshot(command):
    snapshot, working = command["output_paths"]
    for output in (snapshot, working):
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=output, copy=True)
    return {
        "snapshot_id": Path(snapshot).stem,
        "snapshot_path": snapshot,
        "working_copy_path": working,
    }


def _rollback_snapshot(command):
    working = command["output_paths"][0]
    Path(working).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=working, copy=True)
    return {
        "snapshot_id": command["parameters"]["snapshot_id"],
        "working_copy_path": working,
        "rolled_back": True,
    }


def _export_asset(command):
    parameters = command["parameters"]
    asset_objects = [item for item in _objects(command) if item.get("sceneops_asset_member")]
    identities = [item.get("sceneops_id") for item in asset_objects]
    if not identities or any(not value for value in identities) or len(identities) != len(set(identities)):
        raise ValueError("export requires unique sceneops_id values")
    outputs = []
    bpy.ops.object.select_all(action="DESELECT")
    for item in asset_objects:
        item.select_set(True)
    if asset_objects:
        bpy.context.view_layer.objects.active = asset_objects[0]
    for output in command["output_paths"]:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        suffix = Path(output).suffix.lower()
        if suffix == ".glb" and "glb" in parameters["formats"]:
            bpy.ops.export_scene.gltf(
                filepath=output,
                export_format="GLB",
                export_extras=True,
                use_selection=True,
            )
        elif suffix == ".fbx" and "fbx" in parameters["formats"]:
            bpy.ops.export_scene.fbx(
                filepath=output,
                use_selection=True,
                use_custom_props=True,
            )
        else:
            raise ValueError("output extension does not match allowlisted formats")
        outputs.append(output)
    return {
        "output_paths": outputs,
        "sceneops_ids": identities,
        "object_identities": [
            {
                "sceneops_id": item.get("sceneops_id"),
                "display_name": item.name,
                "source_object_locator": item.name,
            }
            for item in asset_objects
        ],
    }
