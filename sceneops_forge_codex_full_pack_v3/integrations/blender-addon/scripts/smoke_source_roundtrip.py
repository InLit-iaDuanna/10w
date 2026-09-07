"""Explicit live native-source acceptance using only an owned isolated session."""
import json
import sys
import struct
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sceneops_blender import BlenderAgentSession

root = Path(tempfile.mkdtemp(prefix="sceneops-native-roundtrip-")).resolve()
grant = dict(task_id="task_smoke", grant_id="grant_smoke", project_id="project_smoke", workspace_root=str(root / "project"), allowed_capabilities=["blender.scene.inspect", "blender.asset.begin", "blender.asset.edit", "blender.asset.publish"], expires_at=(datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
session = BlenderAgentSession(root / "project", root / "state", headless="--headless" in sys.argv, grant_content="--grant-content" in sys.argv)
session.bind_authorization(grant)
def auth(cap):
    return dict(grant, action_id="action_smoke", change_set_id="change_smoke", approval_id="approval_smoke", capability_id="blender.asset." + cap)
def args(request, candidate="candidate_one", cap="edit"):
    return dict(request_id=request, candidate_id=candidate, asset_id="asset_door", authorization=auth(cap))
print(str(root), flush=True)
try:
    initial = session.start()
    made = session.bootstrap_door(**args("bootstrap", cap="begin"), node_ids=dict(frame="node_frame", leaf="node_leaf", hinge="node_hinge"), recipe=dict(width_m=1.3, height_m=2.4, thickness_m=0.2, material=dict(color_hex="#836344", roughness=0.6, metalness=0)))
    first = session.edit_nodes(**args("edit_one"), edits=[dict(node_id="node_leaf", dimensions_m=[1.14, 0.19, 2.32], base_color=[0.8, 0.1, 0.03, 1])])
    reopened = session.open_source(**args("reopen_one", cap="begin"))
    leaf = next(x for x in reopened["objects"] if x["sceneops_role"] == "leaf")
    assert abs(leaf["dimensions_m"][1] - 0.19) < 1e-5
    exported = session.export_source(**args("export_one", cap="publish"))
    assert session.export_source(**args("export_one", cap="publish"))["deduplicated"]
    raw = Path(exported["glb_path"]).read_bytes()
    assert raw[:4] == b"glTF" and struct.unpack_from("<I", raw, 8)[0] == len(raw)
    document = json.loads(raw[20:20 + struct.unpack_from("<I", raw, 12)[0]])
    assert {x.get("extras", {}).get("sceneops_role") for x in document["nodes"]} >= {"frame", "leaf", "hinge"}
    copied = session.register_source("candidate_two", exported["blend_path"])
    session.open_source(**args("open_two_before_external", "candidate_two", "begin"))
    session.save_source(**args("save_two_before_external", "candidate_two"))
    fixture = Path(__file__).with_name("fixture_add_manual_handle.py").resolve()
    subprocess.run(["/usr/bin/sandbox-exec", "-f", str(root / "state" / "sandbox.sb"),
        str(session.executable), "--background", "--factory-startup", "--disable-autoexec",
        "--python", str(fixture), "--", copied], check=True, timeout=60,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    stale = session.inspect()
    assert stale["source_state"]["disk_changed"] and not stale["source_state"]["memory_dirty"]
    assert not any(obj["name"] == "Developer simulated manual handle" for obj in stale["objects"])
    synchronized = session.export_source(**args("export_external_saved", "candidate_two", "publish"))
    assert any(obj["name"] == "Developer simulated manual handle" for obj in synchronized["objects"])
    assert not synchronized["source_state"]["disk_changed"]
    session.register_source("candidate_three", synchronized["blend_path"])
    session.open_source(**args("open_two", "candidate_three", "begin"))
    second = session.edit_nodes(**args("edit_two", "candidate_three"), edits=[dict(node_id="node_frame", base_color=[0.1, 0.2, 0.8, 1])])
    session.open_source(**args("reopen_two", "candidate_three", "begin"))
    leaf2 = next(x for x in session.inspect()["objects"] if x["sceneops_role"] == "leaf")
    assert abs(leaf2["dimensions_m"][1] - 0.19) < 1e-5 and leaf2["base_color"][0] > 0.79
    final = session.export_source(**args("export_two", "candidate_three", "publish"))
    handle = next(obj for obj in final["objects"] if obj["name"] == "Developer simulated manual handle")
    assert handle["sceneops_id"] and handle["asset_id"] == "asset_door"
    handle_id = handle["sceneops_id"]
    session.open_source(**args("reopen_final", "candidate_three", "begin"))
    assert next(obj for obj in session.inspect()["objects"] if obj["sceneops_id"] == handle_id)
    final_raw = Path(final["glb_path"]).read_bytes()
    final_doc = json.loads(final_raw[20:20 + struct.unpack_from("<I", final_raw, 12)[0]])
    assert any(node.get("extras", {}).get("sceneops_id") == handle_id for node in final_doc["nodes"])

    conflict_source = session.register_source("candidate_conflict", final["blend_path"])
    session.open_source(**args("open_conflict", "candidate_conflict", "begin"))
    session.save_source(**args("save_conflict", "candidate_conflict"))
    subprocess.run(["/usr/bin/sandbox-exec", "-f", str(root / "state" / "sandbox.sb"),
        str(session.executable), "--background", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "1", "--python", str(Path(__file__).with_name("fixture_source_conflict.py").resolve()),
        "--", conflict_source], check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    conflict = json.loads((Path(conflict_source).parent / "fixture_conflict_evidence.json").read_text())
    evidence = dict(conflict=conflict, synchronized=synchronized, mode="live", initial=initial, first=first, exported=exported, final=final, checks=["native_save_reopen", "second_candidate_preserves_first_edit", "stable_semantic_nodes", "glb_header_and_nodes", "export_idempotency", "sandbox_outside_denied", "developer_simulated_manual_geometry_preserved", "external_saved_source_auto_reload", "disk_and_memory_conflict_preserves_both"])
    if "--grant-content" in sys.argv:
        original_source = final["blend_path"]
        session.stop()
        session = BlenderAgentSession(root / "project", root / "state_renewed", headless=True, grant_content=True)
        renewed_grant = dict(grant, grant_id="grant_renewed")
        session.bind_authorization(renewed_grant)
        session.start()
        session.register_source("candidate_renewed", original_source)
        renewed = session.open_source(request_id="open_renewed", candidate_id="candidate_renewed", asset_id="asset_door", authorization=dict(renewed_grant, action_id="action_renewed", change_set_id="change_renewed", approval_id="approval_renewed", capability_id="blender.asset.begin"))
        assert any(obj["sceneops_id"] == handle_id for obj in renewed["objects"])
        assert renewed["content_root"] != final["content_root"]
        evidence["renewed_grant"] = renewed
        evidence["checks"].append("new_grant_isolated_source_reopen")
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(str(root / "evidence.json"), flush=True)
finally:
    session.stop()
