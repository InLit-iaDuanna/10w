"""Developer fixture: real Blender dirty-state conflict, not manual UI evidence."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "sceneops_blender"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from agent_source import remember_source, synchronize_source, source_state

source = Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
host = SimpleNamespace(root=source.parent)
remember_source(host, source)
original_bytes = source.read_bytes()
# A second saved version is produced by Blender itself, then placed on disk while
# the first version stays loaded. This models an independent editor's Ctrl-S.
bpy.ops.mesh.primitive_cube_add(size=0.123)
bpy.context.object.name = "External fixture geometry"
external = source.with_name("fixture_external.blend")
bpy.ops.wm.save_as_mainfile(filepath=str(external), copy=True, compress=False)
bpy.ops.wm.open_mainfile(filepath=str(source))
source.write_bytes(external.read_bytes())
bpy.ops.mesh.primitive_cube_add(size=0.234)
bpy.context.object.name = "Unsaved fixture geometry"
bpy.ops.ed.undo_push(message="Developer fixture unsaved edit")
assert bpy.data.is_dirty, "fixture must establish Blender's actual unsaved state"
before = source.read_bytes()
try:
    synchronize_source(host, {"candidate_id": source.stem, "asset_id": "asset_door"})
except ValueError as error:
    assert "BLENDER_SOURCE_CONFLICT" in str(error)
else:
    raise AssertionError("both-edited source must fail")
assert source.read_bytes() == before != original_bytes
assert bpy.context.scene.objects.get("Unsaved fixture geometry") is not None
assert bpy.context.scene.objects.get("External fixture geometry") is None
(source.parent / "fixture_conflict_evidence.json").write_text(json.dumps({
    "mode": "live", "evidence_kind": "developer_fixture_not_manual_ui", "source_state": source_state(host),
    "disk_preserved": True, "unsaved_memory_preserved": True,
}, indent=2))
