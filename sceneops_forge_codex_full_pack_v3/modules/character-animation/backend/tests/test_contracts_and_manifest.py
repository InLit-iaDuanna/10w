import json
import unittest
from pathlib import Path

import yaml

from sceneops_character_animation import backend_module_contribution
from sceneops_character_animation.event_models import EVENT_MODELS
from sceneops_character_animation.fixtures import remember_home_bundle
from sceneops_character_animation.operation_models import CharacterBundle
from sceneops_character_animation.operation_models import UnityMappingProposalResult
from sceneops_character_animation.animation_models import PreviewArtifact


MODULE_ROOT = Path(__file__).resolve().parents[2]


class ManifestAndContractTests(unittest.TestCase):
    def test_manifest_declares_required_public_surface(self):
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "character-animation")
        self.assertEqual(manifest["feature_flag"], "character_animation")
        self.assertEqual(len(manifest["contributes"]["editors"]), 6)
        self.assertIn("unity", manifest["requires"]["optional_integrations"])
        self.assertEqual(manifest["entrypoints"]["frontend"], "./frontend/src/index.ts")
        self.assertEqual(backend_module_contribution.manifest_id, manifest["id"])
        self.assertEqual(
            {job.id for job in backend_module_contribution.jobs},
            set(manifest["contributes"]["jobs"]),
        )
        dependencies = manifest["requires"]["modules"]
        self.assertEqual(len(dependencies), len(set(dependencies)))
        self.assertNotIn(manifest["id"], dependencies)
        self.assertEqual(len(manifest["permissions"]), len(set(manifest["permissions"])))

    def test_fixture_round_trips_through_public_bundle_contract(self):
        fixture_path = MODULE_ROOT / "contracts/examples/remember-home-character.json"
        restored = CharacterBundle.model_validate_json(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(restored, remember_home_bundle())
        self.assertEqual(restored.character.feature_links[0].feature_spec_id, "feature_key_door_branch")

    def test_generated_schema_and_openapi_include_public_types_and_routes(self):
        schema = json.loads(
            (MODULE_ROOT / "contracts/manifests/character-animation.schema.json").read_text(encoding="utf-8")
        )
        openapi = json.loads((MODULE_ROOT / "backend/openapi.json").read_text(encoding="utf-8"))
        expected_types = {
            "CharacterSpec",
            "RigVersion",
            "SkinVersion",
            "AnimationClipSpec",
            "RetargetProfile",
            "AnimatorStateSpec",
            "PreviewArtifact",
        }
        self.assertTrue(expected_types.issubset(schema["$defs"]))
        self.assertIn("/api/modules/character-animation/inspect", openapi["paths"])
        self.assertIn("/api/modules/character-animation/unity-mappings/execute", openapi["paths"])

    def test_preview_and_unity_examples_preserve_truthful_modes_and_provenance(self):
        preview = PreviewArtifact.model_validate_json(
            (MODULE_ROOT / "contracts/examples/preview-artifact.json").read_text(encoding="utf-8")
        )
        proposal = UnityMappingProposalResult.model_validate_json(
            (MODULE_ROOT / "contracts/examples/unity-mapping-proposal.json").read_text(encoding="utf-8")
        )
        self.assertEqual(preview.execution_mode.value, "mock")
        self.assertEqual(proposal.mode.value, "planned")
        self.assertEqual(len(proposal.mapping.source_provenance_artifact_ids), 4)

    def test_declared_workflow_has_explicit_approval_and_offline_states(self):
        workflow = yaml.safe_load(
            (MODULE_ROOT / "workflows/imported-character-to-unity.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(workflow["id"], "imported-character-to-unity")
        self.assertEqual([node["id"] for node in workflow["nodes"] if node.get("type") == "approval"], [
            "review_versions",
            "approve_mapping",
        ])
        self.assertEqual(workflow["truthfulness"]["default_external_mode"], "blocked")

    def test_every_declared_event_has_a_generated_versioned_schema(self):
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        for event_name in manifest["contributes"]["events"]:
            event_type, version = event_name.split("@")
            self.assertEqual(version, "1")
            self.assertIn(event_type, EVENT_MODELS)
            path = MODULE_ROOT / "contracts/events/{}.v1.schema.json".format(event_type)
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["event_version"]["const"], 1)


if __name__ == "__main__":
    unittest.main()
