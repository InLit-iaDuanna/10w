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
        self.journal = sqlite3.connect(self.state / "requests.sqlite3")
        self.journal.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, command TEXT NOT NULL, result TEXT)")
        self.probe = self._probe_isolation()
        scene = contained(self.root, "scene.blend")
        if scene.exists():
            bpy.ops.wm.open_mainfile(filepath=str(scene))
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
        objects = [{"asset_id": obj.get("asset_id"), "sceneops_id": obj.get("sceneops_id"),
                    "name": obj.name, "type": obj.type, "dimensions_m": list(obj.dimensions),
                    "coordinate_space": "blender_z_up", "location_m": list(obj.location)}
                   for obj in bpy.context.scene.objects]
        artifacts = [str(path) for path in sorted(self.root.glob("*")) if path.suffix in (".blend", ".fbx", ".json") and path.is_file()]
        return {"mode": "live", "session_id": self.config["session_id"], "status": "connected",
                "workspace_root": self.config["workspace_root"], "content_root": str(self.root), "tool_version": bpy.app.version_string,
                "pid": os.getpid(), "objects": objects, "artifacts": artifacts,
                "capabilities": sorted(set(self.config["binding"]["allowed_capabilities"]) & {"blender.scene.inspect", "blender.asset.create", "blender.asset.export"}),
                "isolation": self.probe, "scene_path": bpy.data.filepath}

    def dispatch(self, command):
        validate_command(command, self.config["binding"])
        operation = command["operation"]
        if operation == "inspect":
            return self.inspect()
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
        else:
            with self.journal:
                self.journal.execute("INSERT INTO requests(request_id, command) VALUES (?, ?)", (command["request_id"], serialized))
        if operation == "create_asset":
            self.create_asset(command)
        else:
            self.export_asset(command)
        result = self.inspect()
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
            response.put({"ok": True, "result": self.dispatch(command)})
        except Exception as error:
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
                response = queue.Queue(maxsize=1)
                host.requests.put_nowait((payload["command"], response))
                result = response.get(timeout=55)
            except Exception as error:
                result = {"ok": False, "error": str(error)}
            self.wfile.write(json.dumps(result).encode() + b"\n")

    server = socketserver.ThreadingTCPServer(("127.0.0.1", host.config["port"]), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    bpy.app.timers.register(host.tick, first_interval=0.1, persistent=True)
