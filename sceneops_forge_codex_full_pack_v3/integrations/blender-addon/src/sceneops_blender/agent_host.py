"""Blender-only command host. bpy operations run exclusively on its main timer."""
from __future__ import annotations

import hmac
import json
import os
import queue
import socketserver
import sqlite3
import threading
from pathlib import Path

import bpy

from agent_protocol import validate_command
from sceneops_forge_blender.dispatcher import dispatch as dispatch_typed


def contained(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact path escapes workspace")
    return path


class AgentHost:
    def __init__(self, config):
        self.config = config
        self.root = Path(config["content_root"]).resolve()
        self.state = Path(config["state_root"]).resolve()
        self.requests = queue.Queue(maxsize=32)
        self.stopping = False
        self.request_states = {}
        self.request_lock = threading.Lock()
        self.journal = sqlite3.connect(self.state / "requests.sqlite3")
        self.journal.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, command TEXT NOT NULL, result TEXT)")
        self.probe = self._probe_isolation()
        scene = contained(self.root, "scene.blend")
        active = self.state / "active_source.json"
        if active.exists():
            from agent_protocol import identifier
            scene = contained(self.root, identifier(json.loads(active.read_text())["candidate_id"]) + ".blend")
        if scene.exists():
            bpy.ops.wm.open_mainfile(filepath=str(scene))
            from agent_source import remember_source
            remember_source(self, scene)
        else:
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete(use_global=False)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.context.preferences.filepaths.temporary_directory = str(self.state / "tmp")
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1
        for scene in bpy.data.scenes:
            scene.render.use_freestyle = False
            scene.use_nodes = False

    def _probe_isolation(self):
        outside = Path(self.config["outside_probe"])
        try:
            with outside.open("x") as stream:
                stream.write("sandbox must reject this write")
        except PermissionError:
            return {"mechanism": "macos-sandbox-exec", "outside_write_denied": True,
                    "probe_path": str(outside)}
        raise RuntimeError("BLENDER_SANDBOX_FAILED: outside-workspace write was not denied")

    def inspect(self):
        bpy.context.view_layer.update()
        from agent_source import content_objects
        scene_objects = content_objects()
        objects = [{"asset_id": obj.get("asset_id"), "sceneops_id": obj.get("sceneops_id"),
                    "name": obj.name, "type": obj.type, "sceneops_role": obj.get("sceneops_role"),
                    "parent_id": obj.parent.get("sceneops_id") if obj.parent else None,
                    "base_color": list(obj.active_material.diffuse_color) if obj.type == "MESH" and obj.active_material else None, "dimensions_m": list(obj.dimensions),
                    "coordinate_space": "blender_z_up", "location_m": list(obj.location)}
                   for obj in scene_objects]
        vertex_count = triangle_count = 0
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in scene_objects:
            if obj.type == "MESH":
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                try:
                    mesh.calc_loop_triangles()
                    vertex_count += len(mesh.vertices)
                    triangle_count += len(mesh.loop_triangles)
                finally:
                    evaluated.to_mesh_clear()
        from mathutils import Vector
        points = [obj.matrix_world @ Vector(corner) for obj in scene_objects if obj.type == "MESH" for corner in obj.bound_box]
        dimensions_y_up = ([max(p[i] for p in points) - min(p[i] for p in points) for i in (0, 2, 1)] if points else [0, 0, 0])
        artifacts = [str(path) for path in sorted(self.root.glob("*")) if path.suffix in (".blend", ".fbx", ".glb", ".json") and path.is_file()]
        from agent_source import source_state
        return {"source_state": source_state(self), "mode": "live", "session_id": self.config["session_id"], "status": "connected",
                "workspace_root": self.config["workspace_root"], "content_root": str(self.root), "tool_version": bpy.app.version_string,
                "pid": os.getpid(), "objects": objects, "artifacts": artifacts,
                "dimensions_m": dimensions_y_up, "coordinate_space": "gltf_y_up",
                "vertex_count": vertex_count, "triangle_count": triangle_count,
                "node_count": len(objects), "mesh_count": sum(obj.type == "MESH" for obj in scene_objects),
                "capabilities": sorted(set(self.config["binding"]["allowed_capabilities"]) & {"blender.scene.inspect", "blender.asset.create", "blender.asset.export", "blender.asset.begin", "blender.asset.edit", "blender.asset.publish", "blender.asset.derive_unity"}),
                "isolation": self.probe, "scene_path": bpy.data.filepath,
                "current_candidate_id": bpy.context.scene.get("sceneops_candidate_id")}

    def dispatch(self, command):
        validate_command(command, self.config["binding"])
        operation = command["operation"]
        if operation == "inspect":
            return self.inspect()
        if operation == "request_status":
            original = self.journal.execute("SELECT command,result FROM requests WHERE request_id=?", (command["request_id"],)).fetchone()
            if original and not original[1] and self.request_states.get(command['request_id']) not in ('running','queued'):
                request = json.loads(original[0])
                if request['operation'] == 'import_source':
                    from agent_source import source_path
                    target = source_path(self,request['candidate_id'])
                    if not target.exists() and target.with_suffix('.glb').is_file():
                        return {'mode':'live','session_id':self.config['session_id'],'request_id':command['request_id'],
                                'status':'import_not_saved','result':{'candidate_id':request['candidate_id'],
                                'workspace_root':self.config['workspace_root'],'candidate_saved':False}}
            row = self.journal.execute("SELECT result FROM requests WHERE request_id=?", (command["request_id"],)).fetchone()
            return {"mode": "live", "session_id": self.config["session_id"], "request_id": command["request_id"], "status": ("completed" if row[0] else "result_unknown") if row else self.request_states.get(command["request_id"], "not_found"), "result": json.loads(row[0]) if row and row[0] else None}
        if operation == "stop":
            self.stopping = True
            return {"mode": "live", "session_id": self.config["session_id"], "status": "stopped"}
        serialized = json.dumps(command, sort_keys=True, separators=(",", ":"))
        prior = self.journal.execute("SELECT command, result FROM requests WHERE request_id=?", (command["request_id"],)).fetchone()
        if prior:
            if prior[0] != serialized:
                raise ValueError("request_id already belongs to different command inputs")
            if prior[1]:
                result = json.loads(prior[1])
                result.update(session_id=self.config["session_id"], mode="cached", deduplicated=True)
                return result
            raise RuntimeError("BLENDER_RESULT_UNKNOWN: prior request has no completed result; inspect before recovery")
        else:
            with self.journal:
                self.journal.execute("INSERT INTO requests(request_id, command) VALUES (?, ?)", (command["request_id"], serialized))
        extra = {}
        if operation == "create_asset":
            self.create_asset(command)
        elif operation == "export_asset":
            self.export_asset(command)
        else:
            from agent_source import dispatch_source
            extra = dispatch_source(self, command)
        result = self.inspect()
        result.update(extra)
        result.update(request_id=command["request_id"], asset_id=command["asset_id"], deduplicated=False)
        if operation == "export_asset":
            result.update(fbx_path=str(contained(self.root, command["asset_id"] + ".fbx")),
                          manifest_path=str(contained(self.root, command["asset_id"] + ".identity.json")))
        with self.journal:
            self.journal.execute("UPDATE requests SET result=? WHERE request_id=?", (json.dumps(result), command["request_id"]))
        return result

    def create_asset(self, command):
        matches = [obj for obj in bpy.context.scene.objects if obj.get("asset_id") == command["asset_id"] or obj.get("sceneops_id") == command["sceneops_id"]]
        if matches:
            if len(matches) != 1 or matches[0].get("sceneops_create_request") != command["request_id"]:
                raise ValueError("asset or object identity already exists; overwrite requires new approval")
            obj = matches[0]
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
            obj = bpy.context.object
            obj.name = command.get("name", command["asset_id"])
            obj["asset_id"] = command["asset_id"]
            obj["sceneops_id"] = command["sceneops_id"]
            obj["sceneops_create_request"] = command["request_id"]
            obj["sceneops_asset_member"] = True
        obj.dimensions = command["dimensions_m"]
        bpy.context.view_layer.update()
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(contained(self.root, "scene.blend")))

    def export_asset(self, command):
        objects = [obj for obj in bpy.context.scene.objects if obj.get("asset_id") == command["asset_id"]]
        if len(objects) != 1 or not objects[0].get("sceneops_id"):
            raise ValueError("export requires exactly one stable-identity asset")
        obj = objects[0]
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        target = contained(self.root, command["asset_id"] + ".fbx")
        dispatch_typed({"operation": "export_asset", "project_root": str(self.root),
                        "request_id": command["request_id"], "object_ids": [obj["sceneops_id"]],
                        "output_paths": [str(target)], "parameters": {"formats": ["fbx"]},
                        "authorization": command["authorization"], "dry_run": False})
        manifest = {"schema_version": 1, "asset_id": command["asset_id"], "format": "fbx",
                    "project_id": self.config["binding"]["project_id"], "source_asset_id": command["asset_id"],
                    "source_asset_version_id": "astv_" + command["asset_id"].removeprefix("ast_") + "_v1",
                    "source_file": str(target),
                    "objects": [{"source_object_id": obj["sceneops_id"], "sceneops_id": obj["sceneops_id"], "display_name": obj.name}],
                    "units": "meters", "coordinate_space": "blender_z_up", "mode": "live",
                    "object_identities": [{"sceneops_id": obj["sceneops_id"], "display_name": obj.name,
                                           "source_object_locator": obj.name}],
                    "dimensions_m": list(obj.dimensions), "tool_version": bpy.app.version_string}
        contained(self.root, command["asset_id"] + ".identity.json").write_text(json.dumps(manifest))

    def tick(self):
        try:
            command, response = self.requests.get_nowait()
        except queue.Empty:
            return 0.05
        try:
            request_id = command.get("request_id")
            with self.request_lock:
                if self.request_states.get(request_id) == "cancelled":
                    raise RuntimeError("BLENDER_REQUEST_CANCELLED: cancelled before execution")
                if request_id and command["operation"] != "request_status":
                    self.request_states[request_id] = "running"
            response.put({"ok": True, "result": self.dispatch(command)})
            if request_id and command["operation"] != "request_status":
                with self.request_lock:
                    self.request_states[request_id] = "completed"
        except Exception as error:
            if command.get("request_id") and command["operation"] != "request_status":
                with self.request_lock:
                    self.request_states[command["request_id"]] = "failed"
            response.put({"ok": False, "error": str(error)})
        if self.stopping:
            bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
            return None
        return 0.05


def serve(metadata):
    host = AgentHost(json.loads(metadata.read_text()))

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(5)
            try:
                raw = self.rfile.readline(65537)
                if len(raw) > 65536:
                    raise ValueError("command exceeds 64 KiB")
                payload = json.loads(raw)
                if set(payload) != {"token", "command"} or not isinstance(payload["token"], str) or not hmac.compare_digest(payload["token"], host.config["token"]):
                    raise ValueError("session authentication failed")
                validate_command(payload["command"], host.config["binding"])
                command = payload["command"]
                request_id = command.get("request_id")
                with host.request_lock:
                    if command["operation"] == "cancel_request":
                        state = host.request_states.get(request_id, "not_found")
                        if state == "queued":
                            host.request_states[request_id] = state = "cancelled"
                        self.wfile.write(json.dumps({"ok": True, "result": {"mode": "live", "session_id": host.config["session_id"], "request_id": request_id, "status": state}}).encode() + b"\n")
                        return
                    if request_id and command["operation"] != "request_status":
                        host.request_states.setdefault(request_id, "queued")
                response = queue.Queue(maxsize=1)
                host.requests.put_nowait((payload["command"], response))
                result = response.get(timeout=55)
            except Exception as error:
                result = {"ok": False, "error": str(error)}
            self.wfile.write(json.dumps(result).encode() + b"\n")

    server = socketserver.ThreadingTCPServer(("127.0.0.1", host.config["port"]), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if bpy.app.background:
        import time
        while not host.stopping:
            host.tick()
            time.sleep(0.05)
        server.shutdown()
    else:
        bpy.app.timers.register(host.tick, first_interval=0.1, persistent=True)
