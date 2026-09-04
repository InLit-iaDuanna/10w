import json
import unittest
from pathlib import Path

import yaml

import integration_center


MODULE_ROOT = Path(__file__).resolve().parents[4]


class IntegrationCenterContractTests(unittest.TestCase):
    def test_manifest_declares_public_entrypoints_and_dependency_direction(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual("integration-center", manifest["id"])
        self.assertIn("observability", manifest["requires"]["modules"])
        self.assertEqual("integration_center", manifest["entrypoints"]["backend"])
        self.assertEqual(["integration.health", "worker.monitor"], manifest["contributes"]["editors"])
        self.assertEqual("integration_center", manifest["feature_flag"])
        self.assertTrue((MODULE_ROOT / "frontend/src/index.ts").is_file())
        self.assertTrue((MODULE_ROOT / "README.md").is_file())
        self.assertTrue((MODULE_ROOT / "AGENTS.md").is_file())
        self.assertTrue((MODULE_ROOT.parent / "observability").is_dir())
        for event in manifest["contributes"]["events"]:
            name, version = event.split("@")
            self.assertTrue((MODULE_ROOT / "contracts/events" / f"{name}.v{version}.schema.json").is_file())

    def test_all_json_contracts_are_parseable_and_versioned(self) -> None:
        for path in (MODULE_ROOT / "contracts").rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if path.name.endswith(".schema.json"):
                self.assertIn("$schema", payload, path)

    def test_worker_schema_constrains_nested_job_queue_and_actions(self) -> None:
        schema = json.loads(
            (MODULE_ROOT / "contracts/manifests/worker-health.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        definitions = schema["$defs"]
        for name in ("job_pointer", "queue", "recommended_action", "evidence"):
            self.assertFalse(definitions[name]["additionalProperties"])
        self.assertIn("pattern", definitions["queue"]["properties"]["oldest_queued_at"])
        self.assertEqual(32, schema["properties"]["recommended_actions"]["maxItems"])
        self.assertIn("expires_at", schema["required"])
        self.assertIn("is_current", schema["required"])
        self.assertEqual(2, len(definitions["evidence"]["allOf"]))

        health_schema = json.loads(
            (MODULE_ROOT / "contracts/manifests/integration-health.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(2, len(health_schema["properties"]["evidence"]["allOf"]))

    def test_fixture_mode_is_explicit_and_schema_versioned(self) -> None:
        for name in ("integration-health.mock.json", "workers.mock.json"):
            payload = json.loads((MODULE_ROOT / "contracts/examples" / name).read_text(encoding="utf-8"))
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual("mock", payload["mode"])

    def test_public_surface_exposes_ports_not_vendor_sdks(self) -> None:
        self.assertIn("IntegrationAdapter", integration_center.__all__)
        self.assertIn("IntegrationGateway", integration_center.__all__)
        self.assertIn("create_router", integration_center.__all__)
        source_files = list((MODULE_ROOT / "backend/src/integration_center").glob("*.py"))
        source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in source_files)
        for forbidden in ("import bpy", "unityeditor", "import git", "import boto3", "comfy.client"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
