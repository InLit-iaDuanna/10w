"""Native source commands, invoked only by the authenticated main-thread host."""
import json
from uuid import uuid4
from pathlib import Path
import bpy


def source_path(host, candidate):
    from agent_host import contained
    return contained(host.root, candidate + ".blend")


def members(asset_id):
    return [obj for obj in bpy.context.scene.objects if obj.get("asset_id") == asset_id]


def save(host, command):
    target = source_path(host, command["candidate_id"])
    if bpy.context.scene.get("sceneops_candidate_id") != command["candidate_id"]:
        raise ValueError("BLENDER_SOURCE_CONFLICT: another source is open")
    if bpy.context.scene.get("sceneops_exported"):
        raise ValueError("BLENDER_SOURCE_CONFLICT: exported candidate is immutable; copy to a new candidate")
    identify_scene(command["asset_id"])
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=False)
    (host.state / "active_source.json").write_text(json.dumps({"candidate_id": command["candidate_id"]}))
    return target


def bootstrap(host, command):
    if source_path(host, command["candidate_id"]).exists():
        raise ValueError("source candidate already exists")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    recipe = command["recipe"]
    width, height, depth = recipe["width_m"], recipe["height_m"], recipe["thickness_m"]
    frame = recipe.get("frame_width_m", 0.08)
    def identify(obj, role):
        obj.name = role
        obj["asset_id"] = command["asset_id"]
        obj["sceneops_id"] = command["node_ids"][role]
        obj["sceneops_role"] = role
        obj["sceneops_asset_member"] = True
        return obj
    pieces = []
    for dimensions, location in [((frame, depth, height), (-width / 2 + frame / 2, 0, height / 2)), ((frame, depth, height), (width / 2 - frame / 2, 0, height / 2)), ((width - 2 * frame, depth, frame), (0, 0, height - frame / 2))]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        pieces.append(obj)
    frame_root = bpy.data.objects.new("frame", None)
    bpy.context.collection.objects.link(frame_root)
    identify(frame_root, "frame")
    for index, obj in enumerate(pieces):
        obj.parent = frame_root
        obj["asset_id"] = command["asset_id"]
        obj["sceneops_id"] = command["node_ids"]["frame"] + "_part_" + str(index)
        obj["sceneops_role"] = "frame_part"
        obj["sceneops_asset_member"] = True
    hinge = bpy.data.objects.new("hinge", None)
    bpy.context.collection.objects.link(hinge)
    hinge.location = (-width / 2 + frame, 0, 0)
    identify(hinge, "hinge")
    bpy.ops.mesh.primitive_cube_add(size=1)
    leaf = identify(bpy.context.object, "leaf")
    leaf.parent = hinge
    leaf.location = ((width - 2 * frame) / 2, 0, (height - frame) / 2)
    leaf.dimensions = (width - 2 * frame, depth * 0.65, height - frame)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    material = recipe["material"]
    rgb = [int(material["color_hex"].lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)]
    for obj in members(command["asset_id"]):
        if obj.type == "MESH":
            set_material(obj, rgb + [1], material["roughness"], material["metalness"])
    bpy.context.scene["sceneops_candidate_id"] = command["candidate_id"]
    bpy.context.scene["sceneops_exported"] = False
    save(host, command)


def set_material(obj, color, roughness=None, metalness=None):
    material = obj.active_material.copy() if obj.active_material else bpy.data.materials.new(obj.name + " material")
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    if roughness is not None:
        bsdf.inputs["Roughness"].default_value = roughness
    if metalness is not None:
        bsdf.inputs["Metallic"].default_value = metalness
    obj.data.materials.clear()
    obj.data.materials.append(material)


def dispatch_source(host, command):
    operation = command["operation"]
    target = source_path(host, command["candidate_id"])
    if operation == "bootstrap_door":
        bootstrap(host, command)
    elif operation == "open_source":
        if not target.is_file():
            raise ValueError("BLENDER_SOURCE_MISSING: registered source does not exist")
        bpy.ops.wm.open_mainfile(filepath=str(target))
        if not members(command["asset_id"]):
            raise ValueError("registered source asset identity differs")
        prior_candidate = bpy.context.scene.get("sceneops_candidate_id")
        bpy.context.scene["sceneops_candidate_id"] = command["candidate_id"]
        if prior_candidate != command["candidate_id"]:
            bpy.context.scene["sceneops_exported"] = False
        for scene in bpy.data.scenes:
            scene.render.use_freestyle = False
            scene.use_nodes = False
        (host.state / "active_source.json").write_text(json.dumps({"candidate_id": command["candidate_id"]}))
    else:
        if bpy.context.scene.get("sceneops_candidate_id") != command["candidate_id"]:
            raise ValueError("BLENDER_SOURCE_CONFLICT: another source is open")
        if bpy.context.scene.get("sceneops_exported"):
            raise ValueError("BLENDER_SOURCE_CONFLICT: candidate already exported")
        if operation == "edit_nodes":
            selected = []
            for edit in command["edits"]:
                matches = [obj for obj in members(command["asset_id"]) if obj.get("sceneops_id") == edit["node_id"]]
                if len(matches) != 1 or not mesh_descendants(matches[0]):
                    raise ValueError("typed geometry/material edits require one asset mesh or mesh group")
                selected.append((matches[0], edit))
            for obj, edit in selected:
                if "dimensions_m" in edit:
                    if obj.type == "MESH":
                        obj.dimensions = edit["dimensions_m"]
                    else:
                        from mathutils import Vector
                        inverse = obj.matrix_world.inverted()
                        points = [inverse @ child.matrix_world @ Vector(corner) for child in mesh_descendants(obj) for corner in child.bound_box]
                        bounds = [max(point[i] for point in points) - min(point[i] for point in points) for i in range(3)]
                        if min(bounds) <= 0:
                            raise ValueError("cannot resize a zero-volume mesh group")
                        obj.scale = [edit["dimensions_m"][i] / bounds[i] for i in range(3)]
                if "base_color" in edit:
                    for mesh in mesh_descendants(obj):
                        set_material(mesh, edit["base_color"])
        save(host, command)
        if operation == "export_source":
            objects = members(command["asset_id"])
            ids = [obj.get("sceneops_id") for obj in objects]
            if not objects or None in ids or len(ids) != len(set(ids)):
                raise ValueError("source requires unique stable node identities")
            bpy.ops.object.select_all(action="DESELECT")
            for obj in objects:
                obj.select_set(True)
            for fmt in command["formats"]:
                output = target.with_suffix("." + fmt)
                from agent_host import contained
                output = contained(host.root, output.name)
                if fmt == "glb":
                    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", use_selection=True, export_extras=True, export_yup=True)
                else:
                    bpy.ops.export_scene.fbx(filepath=str(output), use_selection=True, use_custom_props=True)
            bpy.context.scene["sceneops_exported"] = True
            bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=False)
    result = {"blend_path": str(target), "candidate_id": command["candidate_id"]}
    if operation == "export_source":
        result.update({fmt + "_path": str(target.with_suffix("." + fmt)) for fmt in command["formats"]})
    return result


def mesh_descendants(obj):
    return [node for node in [obj, *obj.children_recursive] if node.type == "MESH"]


def identify_scene(asset_id):
    """Explicit candidate save adopts manually added nodes, preserving native geometry."""
    objects = list(bpy.context.scene.objects)
    if any(obj.get("asset_id") not in (None, asset_id) for obj in objects):
        raise ValueError("BLENDER_SOURCE_CONFLICT: scene contains another asset identity")
    ids = [obj.get("sceneops_id") for obj in objects if obj.get("sceneops_id")]
    if len(ids) != len(set(ids)):
        raise ValueError("BLENDER_SOURCE_CONFLICT: duplicate source node identities")
    for obj in objects:
        obj["asset_id"] = asset_id
        if not obj.get("sceneops_id"):
            obj["sceneops_id"] = "node_" + uuid4().hex
        obj["sceneops_asset_member"] = True
