import tempfile
import unittest
from pathlib import Path

from sceneops_blender import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    BlenderResult,
    CachedBlenderAdapter,
    ExecutionMode,
    MutationAuthorization,
    VerifiedCacheArtifact,
    VerifiedLiveOperationRecord,
    artifact_sha256,
    cache_behavior_payload,
    cache_key_for,
)


AUTHORIZATION = MutationAuthorization(change_set_id="chg_key", approval_id="apr_key")


class TrustedFixtureStore:
    def __init__(self, records=(), blobs=None):
        if isinstance(records, VerifiedLiveOperationRecord):
            records = [records]
        self.records = {
            (record.source_run_id, record.cache_key): record for record in records
        }
        self.blobs = blobs or {}

    def has_verified_live_run(self, source_run_id):
        return any(key[0] == source_run_id for key in self.records)

    def get_verified(self, source_run_id, cache_key):
        try:
            return self.records[(source_run_id, cache_key)]
        except KeyError as error:
            raise LookupError(cache_key) from error

    def materialize_verified_artifact(
        self, source_run_id, live_evidence_id, artifact_id, destination
    ):
        try:
            payload = self.blobs[(source_run_id, live_evidence_id, artifact_id)]
        except KeyError as error:
            raise LookupError(artifact_id) from error
        destination.write_bytes(payload)


class CachedBlenderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "Assets").mkdir()
        (self.root / "Assets/key.blend").write_bytes(b"deterministic source")

    def tearDown(self):
        self.temporary.cleanup()

    def test_result_requires_trusted_live_run_and_bound_inputs(self):
        command = BlenderCommand(
            request_id="req_scan_source",
            project_id="prj_home",
            operation=BlenderOperation.SCAN_SCENE,
            source_path="Assets/key.blend",
        )
        record = VerifiedLiveOperationRecord(
            source_run_id="run_live_scan_1",
            cache_key=cache_key_for(command),
            live_evidence_id="evidence_fixture_live_scan_1",
            tool_version="Blender 4.3.0",
            command_payload=cache_behavior_payload(command),
            source_sha256=artifact_sha256(self.root / "Assets/key.blend"),
            result=BlenderResult(
                request_id=command.request_id,
                operation=command.operation,
                mode=ExecutionMode.LIVE,
                succeeded=True,
                data={"scene": "TrustedFixture", "objects": []},
            ),
        )
        cached = CachedBlenderAdapter(
            self.root, TrustedFixtureStore(record), "run_live_scan_1"
        )
        replay = cached.execute(
            command.model_copy(update={"request_id": "req_cached_scan"}, deep=True),
            timeout_seconds=2,
        )
        self.assertEqual(replay.mode, ExecutionMode.CACHED)
        self.assertEqual(replay.request_id, "req_cached_scan")
        (self.root / "Assets/key.blend").write_bytes(b"changed source")
        with self.assertRaisesRegex(BlenderAdapterError, "source checksum"):
            cached.execute(
                command.model_copy(update={"request_id": "req_cached_again"}, deep=True),
                timeout_seconds=2,
            )

        missing = CachedBlenderAdapter(
            self.root, TrustedFixtureStore(), "run_without_verified_live_result"
        )
        self.assertFalse(missing.health_check().healthy)
        self.assertEqual(missing.health_check().mode, ExecutionMode.BLOCKED)

    def test_export_distinguishes_slots_and_materializes_for_a_new_run(self):
        old_working = self.root / ".sceneops/asset-factory/run_live/working.blend"
        new_working = self.root / ".sceneops/asset-factory/run_cached/working.blend"
        old_working.parent.mkdir(parents=True)
        new_working.parent.mkdir(parents=True)
        old_working.write_bytes(b"verified working state")
        new_working.write_bytes(b"verified working state")
        old = BlenderCommand(
            request_id="run_live:10:export_asset",
            project_id="prj_home",
            operation=BlenderOperation.EXPORT_ASSET,
            source_path=".sceneops/asset-factory/run_live/working.blend",
            output_paths=[
                ".sceneops/asset-factory/run_live/exports/asset.glb",
                ".sceneops/asset-factory/run_live/exports/asset.fbx",
            ],
            object_ids=["sop_key"],
            parameters={
                "formats": ["glb", "fbx"],
                "include_extras": True,
                "selection_only": True,
            },
            authorization=AUTHORIZATION,
        )
        new = old.model_copy(
            update={
                "request_id": "run_cached:10:export_asset",
                "source_path": ".sceneops/asset-factory/run_cached/working.blend",
                "output_paths": [
                    ".sceneops/asset-factory/run_cached/exports/asset.glb",
                    ".sceneops/asset-factory/run_cached/exports/asset.fbx",
                ],
            },
            deep=True,
        )
        glb_bytes = b"verified cached GLB fixture"
        fbx_bytes = b"verified cached FBX fixture"
        checksum_files = self.root / "checksum-fixtures"
        checksum_files.mkdir()
        glb_file = checksum_files / "asset.glb"
        fbx_file = checksum_files / "asset.fbx"
        glb_file.write_bytes(glb_bytes)
        fbx_file.write_bytes(fbx_bytes)
        evidence_id = "evidence_fixture_export_1"
        bindings = [
            VerifiedCacheArtifact(
                artifact_id="art_cached_glb",
                target="output",
                output_index=0,
                byte_size=len(glb_bytes),
                sha256=artifact_sha256(glb_file),
                format="glb",
                media_type="model/gltf-binary",
            ),
            VerifiedCacheArtifact(
                artifact_id="art_cached_fbx",
                target="output",
                output_index=1,
                byte_size=len(fbx_bytes),
                sha256=artifact_sha256(fbx_file),
                format="fbx",
                media_type="application/octet-stream",
            ),
        ]
        record = VerifiedLiveOperationRecord(
            source_run_id="run_live",
            cache_key=cache_key_for(old),
            live_evidence_id=evidence_id,
            tool_version="Blender 4.3.0",
            command_payload=cache_behavior_payload(old),
            source_sha256=artifact_sha256(old_working),
            result=BlenderResult(
                request_id=old.request_id,
                operation=old.operation,
                mode=ExecutionMode.LIVE,
                succeeded=True,
                data={
                    "sceneops_ids": ["sop_key"],
                    "object_identities": [],
                    "artifacts": [],
                },
            ),
            materializations=bindings,
        )
        blobs = {
            ("run_live", evidence_id, "art_cached_glb"): glb_bytes,
            ("run_live", evidence_id, "art_cached_fbx"): fbx_bytes,
        }
        cached = CachedBlenderAdapter(
            self.root, TrustedFixtureStore(record, blobs), "run_live"
        )
        result = cached.execute(new, timeout_seconds=2)
        self.assertEqual(result.mode, ExecutionMode.CACHED)
        self.assertEqual((self.root / new.output_paths[0]).read_bytes(), glb_bytes)
        self.assertEqual(
            {item["project_relative_path"] for item in result.data["artifacts"]},
            set(new.output_paths),
        )
        first_check = new.model_copy(
            update={
                "request_id": "run_cached:02:check_geometry",
                "operation": BlenderOperation.CHECK_GEOMETRY,
                "output_paths": [],
                "parameters": {
                    "triangle_budget": 1000,
                    "require_uv": True,
                    "allow_nonmanifold": False,
                },
            },
            deep=True,
        )
        second_check = first_check.model_copy(
            update={"request_id": "run_cached:09:check_geometry"}, deep=True
        )
        self.assertNotEqual(cache_key_for(first_check), cache_key_for(second_check))
        self.assertEqual(cache_behavior_payload(old), cache_behavior_payload(new))


if __name__ == "__main__":
    unittest.main()
