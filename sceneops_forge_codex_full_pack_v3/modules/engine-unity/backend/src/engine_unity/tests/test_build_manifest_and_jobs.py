from __future__ import annotations

import json
import tempfile
import unittest
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine_unity.build_manifest import (
    BuildTestEvidence,
    UnityBuildManifest,
    artifact_record,
)
from engine_unity.contracts import ExecutionMode
from engine_unity.jobs import JobState, UnityJob

from engine_unity.tests.support import MODULE_ROOT


class BuildManifestAndJobTests(unittest.TestCase):
    def test_module_manifest_declares_required_public_surface(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual("engine-unity", manifest["id"])
        self.assertEqual("engine_unity", manifest["feature_flag"])
        self.assertEqual(20, len(manifest["contributes"]["commands"]))
        self.assertEqual("engine_unity", manifest["entrypoints"]["backend"])

        security_source = (
            MODULE_ROOT.parents[1]
            / "integrations"
            / "unity-package"
            / "Editor"
            / "SceneOpsCommandSecurity.cs"
        ).read_text(encoding="utf-8")
        unity_commands = set(re.findall(r'"(unity\.[a-z_.]+)"', security_source))
        self.assertEqual(set(manifest["contributes"]["commands"]), unity_commands)

    def test_import_contract_example_uses_distinct_asset_and_object_ids(self) -> None:
        example = json.loads(
            (MODULE_ROOT / "contracts" / "examples" / "unity-import-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotEqual(example["source_asset_id"], example["objects"][0]["sceneops_id"])
        self.assertEqual("meters", example["coordinate_space"]["units"])

    def test_declared_events_have_a_versioned_schema(self) -> None:
        event_schema = json.loads(
            (
                MODULE_ROOT / "contracts" / "events" / "unity-events.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        declared = {item.removesuffix("@1") for item in manifest["contributes"]["events"]}
        schema_events = set(event_schema["properties"]["event_type"]["enum"])
        self.assertEqual(declared, schema_events)
        self.assertEqual(1, event_schema["properties"]["event_version"]["const"])

    def test_mock_build_manifest_is_explicit_and_matches_fixture_artifact(self) -> None:
        manifest_data = json.loads(
            (
                MODULE_ROOT
                / "contracts"
                / "examples"
                / "unity-build-manifest.mock.json"
            ).read_text(encoding="utf-8")
        )
        manifest = UnityBuildManifest.model_validate(manifest_data)
        artifact = artifact_record(
            MODULE_ROOT,
            MODULE_ROOT / manifest.artifacts[0].path,
        )
        self.assertEqual(ExecutionMode.MOCK, manifest.execution_mode)
        self.assertEqual(manifest.artifacts[0].sha256, artifact.sha256)
        self.assertEqual(manifest.artifacts[0].size_bytes, artifact.size_bytes)

    def test_build_manifest_records_sha256_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "Builds" / "RememberHomeA.app"
            executable = build / "Contents" / "MacOS" / "RememberHomeA"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"playable-fixture")
            artifact = artifact_record(root, build)
            manifest = UnityBuildManifest(
                build_id="bld_remember_home_a",
                project_id="prj_remember_home",
                profile="Remember Home A",
                execution_mode=ExecutionMode.MOCK,
                unity_version="2022.3.62f3c1",
                package_version="0.1.0",
                source_commit="1d4f0f3",
                scenes=["Assets/Scenes/RememberHomeA.unity"],
                source_assets=[
                    {
                        "source_asset_id": "ast_home_key",
                        "source_asset_version_id": "astv_home_key_001",
                    }
                ],
                settings={"target": "StandaloneOSX", "development": False},
                tests=[
                    BuildTestEvidence(
                        run_id="testrun_fixture",
                        status="passed",
                        mode=ExecutionMode.MOCK,
                        results_path="Artifacts/TestResults.xml",
                    )
                ],
                artifacts=[artifact],
                produced_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            )
            self.assertEqual(64, len(manifest.artifacts[0].sha256))
            self.assertEqual(len(b"playable-fixture"), manifest.artifacts[0].size_bytes)
            with self.assertRaises(Exception):
                manifest.profile = "mutated"

    def test_build_job_cancel_and_retry_state_machine(self) -> None:
        job = UnityJob(
            job_id="job_build_a",
            request_id="req_build_a",
            max_attempts=2,
        )
        job.transition(JobState.RUNNING, "UNITY_BUILD_STARTED")
        job.transition(JobState.CANCELLED, "UNITY_BUILD_CANCELLED")
        job.retry()
        job.transition(JobState.RUNNING, "UNITY_BUILD_RESTARTED")
        job.transition(JobState.SUCCEEDED, "UNITY_BUILD_SUCCEEDED")
        self.assertEqual(JobState.SUCCEEDED, job.state)
        self.assertEqual(2, job.attempt)
        self.assertIn("UNITY_BUILD_CANCELLED", job.log_codes)

    def test_succeeded_job_cannot_be_retried(self) -> None:
        job = UnityJob(job_id="job_done", request_id="req_done")
        job.transition(JobState.RUNNING, "UNITY_BUILD_STARTED")
        job.transition(JobState.SUCCEEDED, "UNITY_BUILD_SUCCEEDED")
        with self.assertRaises(ValueError):
            job.retry()


if __name__ == "__main__":
    unittest.main()
