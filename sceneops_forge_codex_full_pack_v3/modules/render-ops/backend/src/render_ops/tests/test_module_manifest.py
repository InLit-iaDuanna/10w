import json
import unittest
from pathlib import Path

import yaml


MODULE_ROOT = Path(__file__).resolve().parents[4]


class ModuleManifestTests(unittest.TestCase):
    def test_manifest_declares_owned_surface_and_dependencies(self):
        payload = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["id"], "render-ops")
        self.assertEqual(payload["feature_flag"], "render_ops")
        self.assertEqual(payload["entrypoints"]["frontend"], "./frontend/src/index.ts")
        self.assertEqual(payload["entrypoints"]["backend"], "render_ops")
        self.assertEqual(
            set(payload["requires"]["modules"]), {"core-kernel", "module-runtime"}
        )
        self.assertEqual(
            set(payload["requires"]["optional_integrations"]),
            {"comfyui", "blender", "unity"},
        )
        self.assertEqual(len(payload["contributes"]["editors"]), 6)

    def test_required_module_files_and_event_schemas_exist(self):
        for relative in (
            "AGENTS.md",
            "README.md",
            "module.yaml",
            "frontend/src/index.ts",
            "backend/src/render_ops/__init__.py",
            "contracts/manifests/render-manifest.v1.schema.json",
            "contracts/examples/render-manifest.mock.json",
        ):
            self.assertTrue((MODULE_ROOT / relative).is_file(), relative)
        events = list((MODULE_ROOT / "contracts/events").glob("*.schema.json"))
        self.assertEqual(len(events), 7)
        for path in events:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertNotIn("execution_mode", schema["properties"])

    def test_module_does_not_import_other_module_internals(self):
        for path in (MODULE_ROOT / "backend/src/render_ops").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("modules.", source)
            self.assertNotIn("integrations.", source)


if __name__ == "__main__":
    unittest.main()
