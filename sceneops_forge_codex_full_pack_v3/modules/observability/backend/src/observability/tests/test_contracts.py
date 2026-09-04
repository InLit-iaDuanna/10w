import json
import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

import observability
from observability import StructuredLogEvent


MODULE_ROOT = Path(__file__).resolve().parents[4]


class ObservabilityContractTests(unittest.TestCase):
    def test_manifest_and_entrypoints_are_declared(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual("observability", manifest["id"])
        self.assertEqual("./frontend/src/index.ts", manifest["entrypoints"]["frontend"])
        self.assertEqual("observability", manifest["entrypoints"]["backend"])
        self.assertEqual("observability", manifest["feature_flag"])
        self.assertTrue((MODULE_ROOT / "frontend/src/index.ts").is_file())
        self.assertTrue((MODULE_ROOT / "README.md").is_file())
        self.assertTrue((MODULE_ROOT / "AGENTS.md").is_file())
        self.assertIn("observability.log.recorded@1", manifest["contributes"]["events"])
        for event in manifest["contributes"]["events"]:
            name, version = event.split("@")
            self.assertTrue((MODULE_ROOT / "contracts/events" / f"{name}.v{version}.schema.json").is_file())

    def test_all_json_contracts_are_parseable_and_versioned(self) -> None:
        for path in (MODULE_ROOT / "contracts").rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if path.name.endswith(".schema.json"):
                self.assertIn("$schema", payload, path)

    def test_json_event_schema_constrains_nested_public_fields(self) -> None:
        schema = json.loads(
            (MODULE_ROOT / "contracts/events/observability.log.recorded.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(32, schema["properties"]["fields"]["maxProperties"])
        self.assertNotEqual(True, schema["properties"]["fields"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["correlation_context"]["additionalProperties"])
        self.assertIn("pattern", schema["properties"]["emitted_at"])

    def test_mock_fixture_round_trips_public_model(self) -> None:
        payload = json.loads(
            (MODULE_ROOT / "contracts/examples/log-record.mock.json").read_text(encoding="utf-8")
        )
        event = StructuredLogEvent.model_validate(payload)
        self.assertEqual(payload, event.model_dump(mode="json"))
        self.assertEqual("mock", event.mode.value)

    def test_naive_timestamp_is_rejected(self) -> None:
        payload = json.loads(
            (MODULE_ROOT / "contracts/examples/log-record.mock.json").read_text(encoding="utf-8")
        )
        payload["emitted_at"] = "2026-09-04T00:00:00"
        with self.assertRaises(ValidationError):
            StructuredLogEvent.model_validate(payload)

    def test_public_surface_exports_gateway_and_contracts(self) -> None:
        self.assertIn("ObservabilityGateway", observability.__all__)
        self.assertIn("ObservabilityAccessPort", observability.__all__)
        self.assertIn("create_router", observability.__all__)
        self.assertIn("StructuredLogEvent", observability.__all__)
        self.assertNotIn("zipfile", observability.__all__)


if __name__ == "__main__":
    unittest.main()
