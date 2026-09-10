"""Native source commands, invoked only by the authenticated main-thread host."""
import json
from uuid import uuid4
from pathlib import Path
import bpy


def source_path(host, candidate):
    from agent_host import contained
    return contained(host.root, candidate + ".blend")


def file_revision(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size,
            "inode": stat.st_ino, "device": stat.st_dev}


def remember_source(host, target):
    host.source_revision = file_revision(target)
    host.source_revision_path = str(target)


def source_state(host):
    candidate = bpy.context.scene.get("sceneops_candidate_id")
    target = source_path(host, candidate) if candidate else None
    known = target is not None and getattr(host, "source_revision_path", None) == str(target)
    current = file_revision(target) if target else None
    return {"memory_dirty": bool(bpy.data.is_dirty), "disk_revision": current,
            "loaded_revision": getattr(host, "source_revision", None) if known else None,
            "disk_changed": current != getattr(host, "source_revision", None) if known else bool(current)}


def synchronize_source(host, command):
    """Optimistic binary revision check; never merge two independently edited scenes."""
    target = source_path(host, command["candidate_id"])
    state = source_state(host)
    if not state["disk_changed"]:
        return
    if state["memory_dirty"]:
        raise ValueError("BLENDER_SOURCE_CONFLICT: disk and unsaved editor both changed; preserve both and resolve before export")
    if state["disk_revision"] is None:
        raise ValueError("BLENDER_SOURCE_CONFLICT: registered source was removed")
    revision = state["disk_revision"]
    bpy.ops.wm.open_mainfile(filepath=str(target))
    for scene in bpy.data.scenes:
        scene.render.use_freestyle = False
        scene.use_nodes = False
    if (bpy.context.scene.get("sceneops_candidate_id") != command["candidate_id"]
            or not members(command["asset_id"])
            or any(obj.get("asset_id") not in (None, command["asset_id"]) for obj in bpy.context.scene.objects)):
        raise ValueError("BLENDER_SOURCE_CONFLICT: saved source identity differs from registered candidate")
    if file_revision(target) != revision:
        raise ValueError("BLENDER_SOURCE_CONFLICT: saved source changed while reopening")
    remember_source(host, target)


def content_objects():
    """Bone custom shapes are editor helpers, not authored glTF scene members."""
    objects = list(bpy.context.scene.objects)
    shapes = {bone.custom_shape for obj in objects if obj.type == 'ARMATURE'
              for bone in obj.pose.bones if bone.custom_shape and not bone.custom_shape.get('sceneops_id')}
    return [obj for obj in objects if obj not in shapes]


def members(asset_id):
    return [obj for obj in bpy.context.scene.objects if obj.get("asset_id") == asset_id]


def save(host, command):
    target = source_path(host, command["candidate_id"])
    if bpy.context.scene.get("sceneops_candidate_id") != command["candidate_id"]:
        raise ValueError("BLENDER_SOURCE_CONFLICT: another source is open")
    if bpy.context.scene.get("sceneops_exported"):
        raise ValueError("BLENDER_SOURCE_CONFLICT: exported candidate is immutable; copy to a new candidate")
    synchronize_source(host, command)
    identify_scene(command["asset_id"])
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=False)
    remember_source(host, target)
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
    if operation == "derive_unity":
        return derive_unity(host, command)
    if operation == "import_source":
        import_source(host, command)
    elif operation == "bootstrap_door":
        bootstrap(host, command)
    elif operation == "open_source":
        if not target.is_file():
            raise ValueError("BLENDER_SOURCE_MISSING: registered source does not exist")
        bpy.ops.wm.open_mainfile(filepath=str(target))
        if not members(command["asset_id"]):
            raise ValueError("registered source asset identity differs")
        remember_source(host, target)
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
        synchronize_source(host, command)
        if bpy.context.scene.get("sceneops_exported"):
            raise ValueError("BLENDER_SOURCE_CONFLICT: saved candidate already exported")
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
            if file_revision(target) != host.source_revision:
                raise ValueError("BLENDER_SOURCE_CONFLICT: saved source changed during export")
            bpy.context.scene["sceneops_exported"] = True
            bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=False)
            remember_source(host, target)
    result = {"blend_path": str(target), "candidate_id": command["candidate_id"]}
    if operation == "export_source":
        result.update({fmt + "_path": str(target.with_suffix("." + fmt)) for fmt in command["formats"]})
    return result


def mesh_descendants(obj):
    return [node for node in [obj, *obj.children_recursive] if node.type == "MESH"]


def identify_scene(asset_id):
    """Explicit candidate save adopts manually added nodes, preserving native geometry."""
    objects = content_objects()
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


def derive_unity(host, command):
    """Export the staged immutable source; identity is read, never repaired."""
    from agent_host import contained
    from agent_protocol import identifier
    target = source_path(host, command["candidate_id"])
    if not target.is_file():
        raise ValueError("BLENDER_SOURCE_MISSING: registered source does not exist")
    revision = file_revision(target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    objects = members(command["asset_id"])
    if not objects or len(objects) != len(bpy.context.scene.objects):
        raise ValueError("Unity source must contain only the registered asset members")
    ids = [identifier(obj.get("sceneops_id")) for obj in objects]
    if len(ids) != len(set(ids)):
        raise ValueError("Unity source requires unique stable node identities")
    if any(obj.type not in {"MESH", "EMPTY"} for obj in objects):
        raise ValueError("Unity source supports mesh and empty nodes only")
    if any(obj.parent is not None and obj.parent not in objects for obj in objects):
        raise ValueError("Unity source hierarchy escapes registered asset members")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.update()
    output = contained(host.root, command["candidate_id"] + ".fbx")
    bpy.ops.export_scene.fbx(filepath=str(output), use_selection=True,
                             object_types={"MESH", "EMPTY"}, use_custom_props=True,
                             bake_anim=False, axis_forward="-Z", axis_up="Y")
    if file_revision(target) != revision:
        raise ValueError("BLENDER_SOURCE_CONFLICT: registered source changed during derivation")
    remember_source(host, target)
    return {"candidate_id": command["candidate_id"], "blend_path": str(target),
            "fbx_path": str(output), "fbx_relative_path": output.name}


class glTF2ImportUserExtension:
    """Bind animation extras to the actual Actions created by the glTF importer."""

    def gather_import_animation_after_hook(self, animation_index, track_name, gltf):
        extras = gltf.data.animations[animation_index].extras or {}
        identity = extras.get('sceneops_id')
        if identity:
            for _owner, action, _slot in gltf.needs_stash:
                action['sceneops_id'] = identity


def import_registered_gltf(source):
    # Register the bundled extension only for this controlled import. The hook
    # receives source-to-Action references; display names never resolve identity.
    addon = bpy.context.preferences.addons.new()
    addon.module = __name__
    try:
        bpy.ops.import_scene.gltf(filepath=str(source))
    finally:
        bpy.context.preferences.addons.remove(addon)


def import_source(host, command):
    """Import only a service-staged GLB; preserve authored node IDs and coordinates."""
    target = source_path(host, command['candidate_id'])
    source = target.with_suffix('.glb')
    if target.exists() or not source.is_file() or source.resolve() != source:
        raise ValueError('registered GLB candidate is missing or already imported')
    # This process owns an isolated candidate scene. Selection-based deletion
    # leaves hidden editor helpers from the previous candidate behind.
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Actions retain fake users after their owning rig is removed. Keeping them
    # would export the previous candidate's clips into the next asset.
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action, do_unlink=True)
    import_registered_gltf(source)
    objects = content_objects()
    ids = [obj.get('sceneops_id') for obj in objects]
    if not objects or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError('registered GLB requires unique stable node identities')
    for obj in objects:
        obj['asset_id'] = command['asset_id']
        obj['sceneops_asset_member'] = True
    bpy.context.scene['sceneops_candidate_id'] = command['candidate_id']
    bpy.context.scene['sceneops_exported'] = False
    save(host, command)
