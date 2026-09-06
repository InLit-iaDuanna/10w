"""Explicitly invoked live acceptance: creates only its own temporary project."""
from __future__ import annotations

import json
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sceneops_blender import BlenderAgentSession


def run():
    root = Path(tempfile.mkdtemp(prefix="sceneops-blender-session-smoke-")).resolve()
    grant = {"task_id": "task_smoke", "grant_id": "grant_smoke", "project_id": "project_smoke",
             "workspace_root": str(root / "project"),
             "allowed_capabilities": ["blender.asset.create", "blender.asset.export", "blender.scene.inspect"],
             "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()}
    session = BlenderAgentSession(root / "project", root / "state")
    session.bind_authorization(grant)
    evidence = {"root": str(root), "mode": "live"}
    print("Live smoke workspace:", root, flush=True)
    try:
        initial = session.start()
        assert initial["objects"] == [] and initial["isolation"]["outside_write_denied"]
        assert not Path(initial["isolation"]["probe_path"]).exists()
        auth = {**grant, "action_id": "action_create", "change_set_id": "change_create", "approval_id": "approval_create", "capability_id": "blender.asset.create"}
        create = dict(request_id="request_create", asset_id="ast_cube", sceneops_id="sop_cube", dimensions_m=[1, 2, 3], authorization=auth, name="验收方块")
        created = session.create_asset(**create)
        assert created["objects"][0]["dimensions_m"] == [1, 2, 3]
        assert session.create_asset(**create)["deduplicated"]
        export_auth = {**auth, "capability_id": "blender.asset.export", "action_id": "action_export"}
        exported = session.export_asset(request_id="request_export", asset_id="ast_cube", authorization=export_auth)
        assert Path(exported["fbx_path"]).stat().st_size > 100
        assert json.loads(Path(exported["manifest_path"]).read_text())["objects"][0]["sceneops_id"] == "sop_cube"
        metadata = json.loads((root / "state/session.json").read_text())
        with socket.create_connection(("127.0.0.1", metadata["port"]), timeout=5) as client:
            client.sendall(json.dumps({"token": "invalid-token", "command": {"operation": "inspect"}}).encode() + b"\n")
            assert not json.loads(client.makefile("rb").readline())["ok"]
        reconnected = BlenderAgentSession(root / "project", root / "state")
        reconnected.bind_authorization(grant)
        assert reconnected.start()["session_id"] == initial["session_id"]
        target = Path(exported["fbx_path"])
        backup = target.with_suffix(".fbx.saved")
        target.rename(backup)
        target.symlink_to(root / "outside.fbx")
        try:
            session.export_asset(request_id="request_escape", asset_id="ast_cube", authorization=export_auth)
            raise AssertionError("symlink escape was accepted")
        except RuntimeError as error:
            assert "escapes workspace" in str(error)
        finally:
            target.unlink()
            backup.rename(target)
        session._process.terminate()
        session._process.wait(timeout=15)
        session = BlenderAgentSession(root / "project", root / "state")
        session.bind_authorization(grant)
        recovered = session.start()
        assert len(recovered["objects"]) == 1
        assert recovered["objects"][0]["dimensions_m"] == [1, 2, 3]
        assert session.create_asset(**create)["deduplicated"]
        assert len(session.inspect()["objects"]) == 1
        assert metadata["token"] not in (root / "state/blender.log").read_text()
        evidence.update(initial=initial, exported=exported, recovered=recovered,
                        checks=["outside_write_denied", "cube_dimensions", "fbx_identity", "deduplication",
                                "authentication_denied", "reconnect", "symlink_escape_denied", "process_recovery", "secret_not_logged"])
    finally:
        session.stop()
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps({"passed": evidence["checks"], "evidence_path": str(root / "evidence.json")}), flush=True)


if __name__ == "__main__":
    run()
