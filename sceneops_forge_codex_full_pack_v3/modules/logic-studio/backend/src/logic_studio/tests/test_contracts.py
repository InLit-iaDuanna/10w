import importlib
import unittest
from pathlib import Path

import yaml

from logic_studio.tests.support import MODULE_ROOT, load_json


class ContractTests(unittest.TestCase):
    def test_manifest_declares_complete_public_surface(self):
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "logic-studio")
        self.assertEqual(manifest["feature_flag"], "logic_studio")
        self.assertEqual(
            set(manifest["contributes"]["editors"]),
            {
                "logic.feature",
                "logic.state_graph",
                "logic.interaction_graph",
                "logic.quest_dialogue",
                "logic.code_diff",
                "logic.test_cases",
            },
        )
        self.assertEqual(
            manifest["requires"]["modules"], ["core-kernel", "module-runtime"]
        )
        self.assertEqual(manifest["requires"]["optional_integrations"], ["unity"])

    def test_every_manifest_event_has_a_versioned_schema(self):
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text())
        for event in manifest["contributes"]["events"]:
            event_type, version = event.split("@")
            schema_path = (
                MODULE_ROOT
                / "contracts"
                / "events"
                / f"{event_type}.v{version}.schema.json"
            )
            schema = load_json(str(schema_path.relative_to(MODULE_ROOT)))
            self.assertEqual(schema["properties"]["event_type"]["const"], event_type)
            self.assertEqual(schema["properties"]["event_version"]["const"], int(version))

    def test_manifest_schemas_are_versioned_json_schema(self):
        for name in (
            "gameplay-graph.v1.schema.json",
            "code-change-proposal.v1.schema.json",
        ):
            schema = load_json(f"contracts/manifests/{name}")
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema["additionalProperties"])

    def test_backend_public_entrypoint_imports(self):
        public = importlib.import_module("logic_studio")
        self.assertTrue(callable(public.validate_gameplay_graph))
        self.assertTrue(callable(public.serialize_gameplay_graph))
        self.assertEqual(public.router.prefix, "/logic-studio")

    def test_frontend_has_no_direct_tool_or_shell_calls(self):
        forbidden = ("fetch(", "dockview", "UnityEngine", "child_process", "exec(")
        sources = list((MODULE_ROOT / "frontend" / "src").rglob("*.ts"))
        self.assertTrue(sources)
        for source in sources:
            text = source.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{marker} found in {source}")


if __name__ == "__main__":
    unittest.main()
