from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import bpy


PERSISTENT_SCENE_MUTATIONS = {
    "assign_stable_ids",
    "set_transform",
    "set_normals",
    "set_material_parameter",
    "set_light_parameter",
    "generate_lod",
    "generate_collider",
}


def completed_result(command):
    values = _read_journal(command)
    record = values.get(command["request_id"])
    if record is None:
        return None
    if record.get("command") != _command_binding(command):
        raise ValueError("request_id is already bound to different Blender inputs")
    return record.get("result")


def record_completed_result(command, result):
    values = _read_journal(command)
    values[command["request_id"]] = {
        "command": _command_binding(command),
        "result": result,
    }
    if len(values) > 256:
        del values[next(iter(values))]
    journal = _journal_path(command)
    temporary = journal.with_name(".%s.%s.tmp" % (journal.name, uuid.uuid4().hex))
    try:
        temporary.write_text(
            json.dumps(values, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, journal)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def mutation_lock(command):
    path = Path(command["operation_state_directory"]) / "operation.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError("another Blender mutation is active for this pipeline run") from error
    try:
        os.write(descriptor, command["request_id"].encode("utf-8"))
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def sanitize_scene():
    for scene in bpy.data.scenes:
        scene.render.use_freestyle = False
        scene.use_nodes = False


def validate_paths(command):
    root = Path(command["project_root"]).resolve(strict=True)
    for raw in [command.get("source_path"), *command.get("output_paths", [])]:
        if not raw:
            continue
        resolved = Path(raw).resolve(strict=bool(raw == command.get("source_path")))
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError("bridge path escapes project root") from error
    operation = command["operation"]
    if operation in PERSISTENT_SCENE_MUTATIONS:
        _require_internal_path(root, command["source_path"], "working.blend")
        state_root = Path(command.get("operation_state_directory", ""))
        if not state_root.is_absolute() or not state_root.resolve(strict=True).is_dir():
            raise ValueError("server-owned operation state directory is unavailable")
        try:
            state_root.resolve(strict=True).relative_to(root)
        except ValueError:
            pass
        else:
            raise ValueError("operation state directory must be outside project content")
    if operation == "save_snapshot":
        _require_internal_path(root, command["output_paths"][0], "rollback.blend")
        _require_internal_path(root, command["output_paths"][1], "working.blend")
    if operation == "rollback_snapshot":
        _require_internal_path(root, command["source_path"], "rollback.blend")
        _require_internal_path(root, command["output_paths"][0], "working.blend")


def _read_journal(command):
    journal = _journal_path(command)
    if not journal.exists():
        return {}
    values = json.loads(journal.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("Blender operation journal must be an object")
    return values


def _journal_path(command):
    return Path(command["operation_state_directory"]) / "operation-journal.json"


def _command_binding(command):
    return {key: value for key, value in command.items() if key != "request_id"}


def _require_internal_path(root, raw, filename):
    relative = Path(raw).resolve().relative_to(root)
    if (
        len(relative.parts) != 4
        or relative.parts[:2] != (".sceneops", "asset-factory")
        or relative.name != filename
    ):
        raise ValueError("persistent Blender state must use the SceneOps internal run directory")
