import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sceneops_blender import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderIdentityRegistry,
    BlenderObjectIdentity,
    BlenderOperation,
    DeterministicMockBlenderAdapter,
    ExecutionMode,
    LiveBlenderAdapter,
    MutationAuthorization,
    PathBoundaryError,
    ProjectPathPolicy,
    extract_sceneops_ids,
    read_glb_json,
)


AUTHORIZATION = MutationAuthorization(change_set_id="chg_key", approval_id="apr_key")


class HealthyTransport:
    filesystem_isolated = False

    def __init__(self):
        self.execute_calls = 0

    def health(self, executable, timeout_seconds):
        return "Blender 4.3.0"

    def execute(self, executable, bridge_path, payload, timeout_seconds, is_cancelled):
        self.execute_calls += 1
        request = json.loads(payload)
        return {
            "succeeded": True,
            "data": {"scene": "Scene", "objects": []},
            "logs": [],
        }


class BlenderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "Assets").mkdir()
        (self.root / "Assets" / "key.blend").write_bytes(b"deterministic mock source")

    def tearDown(self):
        self.temporary.cleanup()

    def test_offline_and_online_health_are_truthful(self):
        offline = LiveBlenderAdapter(self.root, executable=None, discover_executable=False)
        self.assertFalse(offline.health_check().healthy)
        self.assertEqual(offline.health_check().mode, ExecutionMode.BLOCKED)

        fake_executable = self.root / "blender"
        fake_executable.write_text("#!/bin/sh\nexit 0\n")
        fake_executable.chmod(0o700)
        online = LiveBlenderAdapter(
            self.root,
            executable=fake_executable,
            transport=HealthyTransport(),
        )
        health = online.health_check()
        self.assertTrue(health.healthy)
        self.assertEqual(health.mode, ExecutionMode.LIVE)
        self.assertEqual(health.version, "Blender 4.3.0")

    def test_live_project_file_requires_filesystem_isolated_transport(self):
        fake_executable = self.root / "blender"
        fake_executable.write_text("#!/bin/sh\nexit 0\n")
        fake_executable.chmod(0o700)
        transport = HealthyTransport()
        adapter = LiveBlenderAdapter(
            self.root,
            executable=fake_executable,
            transport=transport,
        )
        command = BlenderCommand(
            request_id="req_live_project_scan",
            project_id="prj_home",
            operation=BlenderOperation.SCAN_SCENE,
            source_path="Assets/key.blend",
        )
        with self.assertRaises(BlenderAdapterError) as raised:
            adapter.execute(command, timeout_seconds=2)
        self.assertEqual(raised.exception.code, "BLENDER_SANDBOX_REQUIRED")
        self.assertEqual(transport.execute_calls, 0)

    def test_path_boundary_rejects_parent_absolute_and_symlink_escape(self):
        policy = ProjectPathPolicy(self.root)
        with self.assertRaises(PathBoundaryError):
            policy.resolve("../outside.blend")
        with self.assertRaises(PathBoundaryError):
            policy.resolve("/etc/passwd", must_exist=True)
        outside = self.root.parent / (self.root.name + "-outside.blend")
        outside.write_bytes(b"outside")
        try:
            (self.root / "Assets" / "linked.blend").symlink_to(outside)
            with self.assertRaises(PathBoundaryError):
                policy.resolve("Assets/linked.blend", must_exist=True)
        finally:
            outside.unlink(missing_ok=True)

    def test_invalid_or_unapproved_commands_never_reach_an_adapter(self):
        with self.assertRaises(ValueError):
            BlenderCommand(
                request_id="req_bad",
                project_id="prj_home",
                operation="execute_python",
                source_path="Assets/key.blend",
            )
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            BlenderCommand(
                request_id="req_bad_parameter",
                project_id="prj_home",
                operation=BlenderOperation.SCAN_SCENE,
                source_path="Assets/key.blend",
                parameters={"python": "import os"},
            )
        with self.assertRaisesRegex(ValueError, "ChangeSet approval"):
            BlenderCommand(
                request_id="req_export",
                project_id="prj_home",
                operation=BlenderOperation.EXPORT_ASSET,
                source_path="Assets/key.blend",
                output_paths=["Published/key.glb"],
                parameters={"formats": ["glb"], "include_extras": True},
            )
        with self.assertRaisesRegex(ValueError, "selected asset objects"):
            BlenderCommand(
                request_id="req_export_all",
                project_id="prj_home",
                operation=BlenderOperation.EXPORT_ASSET,
                source_path="Assets/key.blend",
                output_paths=["Published/key.glb"],
                object_ids=["sop_key"],
                parameters={
                    "formats": ["glb"],
                    "include_extras": True,
                    "selection_only": False,
                },
                authorization=AUTHORIZATION,
            )
        with self.assertRaisesRegex(ValueError, "formats must be a bounded list"):
            BlenderCommand(
                request_id="req_export_no_formats",
                project_id="prj_home",
                operation=BlenderOperation.EXPORT_ASSET,
                source_path="Assets/key.blend",
                output_paths=["Published/key.glb"],
                object_ids=["sop_key"],
                parameters={"include_extras": True, "selection_only": True},
                authorization=AUTHORIZATION,
            )

    def test_mutation_cannot_overwrite_source_and_repeated_request_is_idempotent(self):
        adapter = DeterministicMockBlenderAdapter(self.root)
        snapshot = BlenderCommand(
            request_id="req_snapshot",
            project_id="prj_home",
            operation=BlenderOperation.SAVE_SNAPSHOT,
            source_path="Assets/key.blend",
            output_paths=[
                ".sceneops/asset-factory/run_key/rollback.blend",
                ".sceneops/asset-factory/run_key/working.blend",
            ],
            authorization=AUTHORIZATION,
        )
        adapter.execute(snapshot, timeout_seconds=2)
        with self.assertRaises(PathBoundaryError):
            adapter.execute(
                BlenderCommand(
                    request_id="req_unsafe_normals",
                    project_id="prj_home",
                    operation=BlenderOperation.SET_NORMALS,
                    source_path="Assets/key.blend",
                    object_ids=["sop_key"],
                    parameters={"mode": "recalculate_outside"},
                    authorization=AUTHORIZATION,
                ),
                timeout_seconds=2,
            )
        lod = BlenderCommand(
            request_id="req_lod_once",
            project_id="prj_home",
            operation=BlenderOperation.GENERATE_LOD,
            source_path=".sceneops/asset-factory/run_key/working.blend",
            object_ids=["sop_key"],
            parameters={"ratios": [0.5, 0.25]},
            authorization=AUTHORIZATION,
        )
        first = adapter.execute(lod, timeout_seconds=2)
        replay = adapter.execute(lod, timeout_seconds=2)
        self.assertEqual(first.model_dump(), replay.model_dump())
        self.assertEqual(len(adapter.generated_identities), 2)
        self.assertEqual(adapter.call_counts[BlenderOperation.GENERATE_LOD], 1)

    def test_rename_preserves_identity_copy_gets_new_identity_and_manifest_round_trips(self):
        registry = BlenderIdentityRegistry(
            [BlenderObjectIdentity("Collection/Key", "Key", "sop_key")]
        )
        renamed = registry.rename("sop_key", "HomeKey", "Collection/HomeKey")
        copied = registry.copy("sop_key", "HomeKeyCopy", "Collection/HomeKeyCopy", lambda: "sop_key_copy")
        self.assertEqual(renamed.sceneops_id, "sop_key")
        self.assertNotEqual(copied.sceneops_id, renamed.sceneops_id)
        loaded = BlenderIdentityRegistry.from_manifest(registry.export_manifest())
        self.assertEqual(loaded.export_manifest(), registry.export_manifest())

    def test_mock_export_has_checksums_and_sceneops_ids_survive_glb_load(self):
        adapter = DeterministicMockBlenderAdapter(self.root)
        command = BlenderCommand(
            request_id="req_export",
            project_id="prj_home",
            operation=BlenderOperation.EXPORT_ASSET,
            source_path="Assets/key.blend",
            output_paths=["Published/key.glb", "Published/key.fbx"],
            object_ids=["sop_key", "sop_key_teeth"],
            parameters={
                "formats": ["glb", "fbx"],
                "include_extras": True,
                "selection_only": True,
            },
            authorization=AUTHORIZATION,
        )
        result = adapter.execute(command, timeout_seconds=2)
        self.assertEqual(result.mode, ExecutionMode.MOCK)
        self.assertEqual(len(result.data["artifacts"]), 2)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in result.data["artifacts"]))
        document = read_glb_json(self.root / "Published" / "key.glb")
        self.assertEqual(extract_sceneops_ids(document), ["sop_key", "sop_key_teeth"])

    def test_mock_cancellation_is_structured(self):
        adapter = DeterministicMockBlenderAdapter(self.root)
        command = BlenderCommand(
            request_id="req_scan",
            project_id="prj_home",
            operation=BlenderOperation.SCAN_SCENE,
            source_path="Assets/key.blend",
        )
        with self.assertRaises(BlenderAdapterError) as raised:
            adapter.execute(command, timeout_seconds=1, is_cancelled=lambda: True)
        self.assertEqual(raised.exception.code, "BLENDER_CANCELLED")

    def test_capability_report_explicitly_disables_arbitrary_python(self):
        adapter = DeterministicMockBlenderAdapter(self.root)
        capabilities = adapter.capabilities()
        self.assertFalse(capabilities.arbitrary_python)
        self.assertNotIn("execute_python", [item.value for item in capabilities.operations])

    def test_live_contract_smoke_is_live_or_truthfully_blocked(self):
        executable = shutil.which("blender")
        adapter = LiveBlenderAdapter(self.root, Path(executable) if executable else None)
        health = adapter.health_check(timeout_seconds=10)
        if health.healthy:
            result = adapter.execute(
                BlenderCommand(
                    request_id="req_live_smoke",
                    project_id="prj_smoke",
                    operation=BlenderOperation.SCAN_SCENE,
                ),
                timeout_seconds=30,
            )
            self.assertEqual(result.mode, ExecutionMode.LIVE)
            self.assertTrue(result.succeeded)
        else:
            self.assertEqual(health.mode, ExecutionMode.BLOCKED)
            self.assertEqual(health.code, "BLENDER_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
