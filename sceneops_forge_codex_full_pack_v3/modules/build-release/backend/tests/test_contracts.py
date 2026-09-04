from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

import build_release
from build_release.events import EVENT_PAYLOAD_MODELS
from build_release.models_build import BuildManifest


MODULE_ROOT = Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def test_module_manifest_declares_public_contributions(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "build-release")
        self.assertEqual(manifest["feature_flag"], "build_release")
        self.assertEqual(
            manifest["contributes"]["editors"],
            [
                "build.matrix",
                "build.console",
                "release.gates",
                "release.center",
                "release.patch-notes",
            ],
        )
        self.assertIn("artifact-store", manifest["requires"]["optional_integrations"])
        self.assertEqual(manifest["entrypoints"]["backend"], "build_release")

    def test_generated_manifest_schema_matches_pydantic_source(self) -> None:
        generated = json.loads(
            (MODULE_ROOT / "contracts/manifests/build-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(generated, BuildManifest.model_json_schema())

    def test_all_declared_event_schemas_are_generated(self) -> None:
        for event_name, model in EVENT_PAYLOAD_MODELS.items():
            filename = event_name.replace("@", "-v") + ".schema.json"
            generated = json.loads(
                (MODULE_ROOT / "contracts/events" / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(generated, model.model_json_schema())

    def test_public_backend_entrypoint_is_explicit(self) -> None:
        expected = {
            "BuildManifest",
            "BuildMatrix",
            "BuildReleaseService",
            "BuildRun",
            "BuildTarget",
            "Deployment",
            "DeploymentPlan",
            "ReleaseCandidate",
            "ReleaseGate",
            "RollbackPlan",
            "create_router",
        }
        self.assertTrue(expected.issubset(set(build_release.__all__)))

    def test_openapi_exposes_release_mutations_and_failure_models(self) -> None:
        openapi = json.loads(
            (MODULE_ROOT / "contracts/openapi/build-release.openapi.json").read_text(
                encoding="utf-8"
            )
        )
        paths = openapi["paths"]
        self.assertIn("/build-release/deployments/prepare", paths)
        self.assertIn("/build-release/deployments", paths)
        self.assertIn("/build-release/rollback-plans/{plan_id}/execute", paths)
        self.assertIn("ReleaseCandidate", openapi["components"]["schemas"])

    def test_runtime_source_contains_no_shell_execution_api(self) -> None:
        forbidden = ("subprocess", "os.system", "Popen(", "shell=True", "eval(", "exec(")
        source_root = MODULE_ROOT / "backend/src/build_release"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in source_root.glob("*.py")
        )
        for token in forbidden:
            self.assertNotIn(token, combined)

    def test_example_fixtures_are_mock_and_do_not_fake_cached_artifacts(self) -> None:
        observed_scopes = set()
        for game in ("remember-home", "warehouse-escape"):
            fixture = json.loads(
                (MODULE_ROOT / "fixtures" / game / "release-scenario.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(fixture["fixture_mode"], "mock")
            self.assertEqual(fixture["cached_judge_expectation"]["mode"], "blocked")
            self.assertIn("No prior live", fixture["cached_judge_expectation"]["reason"])
            observed_scopes.add((fixture["project_id"], fixture["game_id"]))
        self.assertEqual(len(observed_scopes), 2)

    def test_workflows_make_external_blockers_and_approvals_explicit(self) -> None:
        release_workflow = yaml.safe_load(
            (MODULE_ROOT / "workflows/build-to-release-candidate.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(release_workflow["implementation_status"], "planned")
        nodes = {node["id"]: node for node in release_workflow["nodes"]}
        self.assertEqual(nodes["unity-build-a"]["state_when_unavailable"], "blocked")
        self.assertEqual(nodes["candidate-approval"]["state"], "waiting_approval")
        self.assertTrue(nodes["generate-patch-note"]["approved_changesets_only"])

        rollback_workflow = yaml.safe_load(
            (MODULE_ROOT / "workflows/rollback-known-good.yaml").read_text(
                encoding="utf-8"
            )
        )
        rollback_nodes = {node["id"]: node for node in rollback_workflow["nodes"]}
        self.assertEqual(
            rollback_nodes["activate-prior-candidate"]["mutation"],
            "append_only_activation",
        )


if __name__ == "__main__":
    unittest.main()
