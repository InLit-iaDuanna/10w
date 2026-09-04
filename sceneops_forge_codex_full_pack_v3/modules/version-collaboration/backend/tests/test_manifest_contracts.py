from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

import yaml

import version_collaboration
from version_collaboration.review_models import DomainEvent


MODULE_ROOT = Path(__file__).resolve().parents[2]


class ManifestAndContractTests(unittest.TestCase):
    def test_manifest_declares_owned_public_surface_and_entrypoints_exist(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text())

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "version-collaboration")
        self.assertEqual(manifest["feature_flag"], "version_collaboration")
        self.assertEqual(manifest["requires"]["modules"], ["core-kernel", "module-runtime"])
        self.assertEqual(manifest["requires"]["integrations"], ["git"])
        self.assertIn("git-lfs", manifest["requires"]["optional_integrations"])
        self.assertIn("review:create", manifest["permissions"])
        self.assertTrue((MODULE_ROOT / manifest["entrypoints"]["frontend"]).is_file())
        backend_entry = MODULE_ROOT / "backend" / "src" / manifest["entrypoints"]["backend"] / "__init__.py"
        self.assertTrue(backend_entry.is_file())

    def test_public_backend_surface_is_explicit(self) -> None:
        expected = {
            "ActionContext",
            "Actor",
            "ApprovalVerifier",
            "ChangeSetGateway",
            "ErrorCode",
            "ExecutionMode",
            "GitAdapter",
            "GitCliAdapter",
            "ReviewRepository",
            "SqliteReviewRepository",
            "VersionCollaborationError",
            "VersionCollaborationService",
            "VersionReference",
            "create_router",
            "version_collaboration_exception_handler",
        }

        self.assertEqual(set(version_collaboration.__all__), expected)

    def test_event_fixture_matches_pydantic_envelope_and_versioned_schema(self) -> None:
        schema = json.loads(
            (MODULE_ROOT / "contracts" / "events" / "review-events.v1.schema.json").read_text()
        )
        fixture = json.loads(
            (MODULE_ROOT / "contracts" / "examples" / "review-event.json").read_text()
        )

        event = DomainEvent.model_validate(fixture)
        self.assertEqual(event.event_version, 1)
        self.assertIn(event.event_type, schema["properties"]["event_type"]["enum"])
        self.assertEqual(schema["properties"]["event_version"]["const"], 1)
        self.assertEqual(schema["properties"]["mode"]["enum"], ["live", "cached", "mock", "planned", "blocked"])

    def test_generated_openapi_and_types_are_current(self) -> None:
        result = subprocess.run(
            ("python3", "backend/scripts/generate_contracts.py", "--check"),
            cwd=MODULE_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_frontend_has_no_direct_external_tool_or_network_call(self) -> None:
        sources = "\n".join(
            path.read_text()
            for path in (MODULE_ROOT / "frontend" / "src").rglob("*.ts*")
        )

        self.assertNotIn("child_process", sources)
        self.assertNotIn("subprocess", sources)
        self.assertIsNone(re.search(r"\bfetch\s*\(", sources))
        self.assertNotIn("dockview", sources.lower())


if __name__ == "__main__":
    unittest.main()
