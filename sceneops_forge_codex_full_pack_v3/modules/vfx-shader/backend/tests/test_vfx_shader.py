from __future__ import annotations

import json
import re
import sys
import unittest
from dataclasses import replace
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MODULE_ROOT / "backend" / "src"))

import vfx_shader as vfx  # noqa: E402


def validate_schema(value: object, schema: dict, path: str = "$") -> None:
    """Small validator for the strict schema keywords authored by this module."""
    expected_type = schema.get("type")
    if expected_type is not None:
        candidates = expected_type if isinstance(expected_type, list) else [expected_type]
        matches = {
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: type(item) is int,
            "boolean": lambda item: type(item) is bool,
            "null": lambda item: item is None,
        }
        assert any(matches[item](value) for item in candidates), f"{path}: wrong type"
    if "const" in schema:
        assert value == schema["const"], f"{path}: expected {schema['const']}"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: not in enum"
    if isinstance(value, str):
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), f"{path}: pattern mismatch"
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path}: too short"
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        assert required <= set(value), f"{path}: missing {required - set(value)}"
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(properties), f"{path}: extra {set(value) - set(properties)}"
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], f"{path}.{key}")
    if isinstance(value, list):
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path}: too few items"
        if schema.get("uniqueItems"):
            assert len(value) == len({json.dumps(item, sort_keys=True) for item in value}), f"{path}: duplicates"
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), f"{path}[{index}]")


def event_context(event_id: str = "evt_vfx_001") -> vfx.EventContext:
    return vfx.EventContext(
        event_id=event_id,
        occurred_at="2026-09-04T00:05:00Z",
        project_id="prj_find_my_way_home",
        correlation_id="corr_vfx_001",
        causation_id="cmd_vfx_001",
        actor=vfx.EventActor("user", "usr_reviewer_01"),
    )


def proposed_changeset(recipe: vfx.VfxShaderRecipe) -> vfx.ChangeSet:
    proposed_values = {
        "operation": "publish_recipe", "recipe_version": recipe.version,
        "template_id": recipe.template_id, "shader_family": recipe.shader_family,
        "quality_tier": recipe.quality_tier.value, "parameters": dict(recipe.parameters),
        "particle_count": recipe.particle_count,
        "estimated_overdraw_layers": recipe.estimated_overdraw_layers,
        "estimated_screen_coverage_percent": recipe.estimated_screen_coverage_percent,
        "bindings": [
            {
                "binding_id": binding.binding_id, "event_name": binding.event_name,
                "target_sceneops_id": binding.target_sceneops_id, "action": binding.action,
                "enabled": binding.enabled,
            }
            for binding in recipe.bindings
        ],
    }
    return vfx.ChangeSet(
        change_set_id="chg_vfx_home_001",
        base_version=recipe.provenance.source_version,
        target_integration="unity",
        target_object_ids=recipe.provenance.related_sceneops_ids,
        previous_values={"bindings_enabled": False},
        proposed_values=proposed_values,
        rationale="提升钥匙与门口的可发现性",
        expected_result="玩家能注意到关键交互对象",
        impact_scope="两个场景对象上的可选 VFX",
        risk="低；可能产生轻微 overdraw",
        validation_plan=("运行预算校验", "在 Unity 中验证事件触发"),
        rollback_plan=("停用绑定", "恢复上一 Recipe 版本"),
        approval_requirements=("technical-art-review",),
        approval_state=vfx.ApprovalState.PROPOSED,
    )


def approved_request(recipe: vfx.VfxShaderRecipe, event_id: str = "evt_vfx_001") -> vfx.PublicationRequest:
    changeset = proposed_changeset(recipe).approve("usr_reviewer_01", "2026-09-04T00:04:00Z")
    return vfx.PublicationRequest(recipe, changeset, event_context(event_id))


def binding_request(recipe: vfx.VfxShaderRecipe, binding_id: str, enabled: bool,
                    event_id: str, *, approved: bool) -> vfx.PublicationRequest:
    binding = next(item for item in recipe.bindings if item.binding_id == binding_id)
    change_set = replace(
        proposed_changeset(recipe),
        target_object_ids=(binding.target_sceneops_id,),
        proposed_values={
            "operation": "set_binding_enabled", "recipe_version": recipe.version,
            "binding_id": binding_id, "enabled": enabled,
        },
    )
    if approved:
        change_set = change_set.approve("usr_reviewer_01", "2026-09-04T00:04:00Z")
    return vfx.PublicationRequest(recipe, change_set, event_context(event_id))


class ManifestAndContractTests(unittest.TestCase):
    def test_manifest_and_public_entrypoints(self) -> None:
        manifest = (MODULE_ROOT / "module.yaml").read_text(encoding="utf-8")
        self.assertIn("id: vfx-shader", manifest)
        self.assertIn("feature_flag: vfx_shader", manifest)
        self.assertIn("frontend: ./frontend/src/index.ts", manifest)
        self.assertIn("backend: vfx_shader", manifest)
        self.assertIn("optional_integrations:\n    - unity\n    - render", manifest)
        frontend = (MODULE_ROOT / "frontend/src/index.ts").read_text(encoding="utf-8")
        self.assertIn("moduleContribution", frontend)
        self.assertIn("load: () => import('./editors/VfxShaderEditor')", frontend)
        for name in vfx.__all__:
            self.assertTrue(hasattr(vfx, name), name)

    def test_every_manifest_event_has_strict_schema(self) -> None:
        expected = {
            "vfx.recipe.validated@1",
            "vfx.preview.planned@1",
            "vfx.recipe.published@1",
            "vfx.binding.changed@1",
        }
        for event in expected:
            schema_name = event.replace("@", ".v") + ".schema.json"
            schema = json.loads((MODULE_ROOT / "contracts/events" / schema_name).read_text())
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["properties"]["event_type"]["const"], event.split("@")[0])
            self.assertEqual(schema["properties"]["event_version"]["const"], 1)
            self.assertIn("mode", schema["required"])
            self.assertNotIn("execution_mode", schema["properties"])


class RecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recipe = vfx.load_recipe_fixture("hero_home_highlight")

    def test_parameter_schema_and_deterministic_preview(self) -> None:
        self.assertEqual(self.recipe.validate(), ())
        invalid = replace(self.recipe, parameters={**self.recipe.parameters, "intensity": 1.5})
        self.assertIn("intensity must be <= 1.0", invalid.validate())
        first = vfx.plan_preview(self.recipe)
        second = vfx.plan_preview(self.recipe)
        self.assertEqual(first, second)
        self.assertEqual(first.execution_mode, vfx.ExecutionMode.MOCK)
        fixture = json.loads((MODULE_ROOT / "contracts/examples/mock-preview-plan.json").read_text())
        self.assertEqual(first.preview_id, fixture["preview_id"])

    def test_validate_and_preview_events_match_declared_schemas(self) -> None:
        validated = vfx.validate_recipe_operation(self.recipe, event_context("evt_vfx_validated_001"))
        validation_schema = json.loads((MODULE_ROOT / "contracts/events/vfx.recipe.validated.v1.schema.json").read_text())
        validate_schema(validated.events[0], validation_schema)
        _plan, planned = vfx.plan_preview_operation(self.recipe, event_context("evt_vfx_preview_001"))
        preview_schema = json.loads((MODULE_ROOT / "contracts/events/vfx.preview.planned.v1.schema.json").read_text())
        validate_schema(planned.events[0], preview_schema)

    def test_quality_tiers_and_budget_warning(self) -> None:
        self.assertEqual(vfx.QUALITY_BUDGETS[vfx.QualityTier.LOW].max_particles, 64)
        excessive = replace(self.recipe, quality_tier=vfx.QualityTier.LOW, particle_count=65, estimated_overdraw_layers=1.6)
        codes = {warning.code for warning in vfx.validate_budget(excessive)}
        self.assertEqual(codes, {"VFX_PARTICLE_BUDGET", "VFX_OVERDRAW_BUDGET"})

    def test_hero_bindings_and_enable_disable_are_data_driven(self) -> None:
        self.assertEqual(
            {binding.event_name for binding in self.recipe.bindings},
            {"gameplay.key.picked_up", "gameplay.door.unlocked"},
        )
        changed = self.recipe.with_binding_enabled("vfxbind_home_door_unlocked", True)
        self.assertTrue(next(item for item in changed.bindings if item.binding_id.endswith("door_unlocked")).enabled)
        restored = changed.with_binding_enabled("vfxbind_home_door_unlocked", False)
        self.assertFalse(next(item for item in restored.bindings if item.binding_id.endswith("door_unlocked")).enabled)

    def test_second_game_uses_same_template_without_platform_branch(self) -> None:
        warehouse = vfx.load_recipe_fixture("warehouse_escape")
        self.assertEqual(warehouse.template_id, self.recipe.template_id)
        self.assertEqual(warehouse.provenance.source_project_id, "prj_warehouse_escape")
        self.assertEqual(warehouse.validate(), ())

    def test_complete_provenance_and_checksum_format(self) -> None:
        provenance = self.recipe.provenance
        self.assertEqual(provenance.producing_module, "vfx-shader")
        self.assertEqual(provenance.execution_mode, vfx.ExecutionMode.MOCK)
        self.assertEqual(provenance.approval_state, vfx.ApprovalState.APPROVED)
        self.assertRegex(provenance.checksum_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(provenance.validate(), ())


class ChangeSetAndAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recipe = vfx.load_recipe_fixture("hero_home_highlight")

    def test_changeset_lifecycle_and_unapproved_publish_rejected_without_adapter_call(self) -> None:
        adapter = vfx.DeterministicMockUnityAdapter()
        change_set = proposed_changeset(self.recipe)
        request = vfx.PublicationRequest(self.recipe, change_set, event_context())
        result = vfx.VfxShaderService(adapter).publish(request, permissions={"vfx:publish"})
        self.assertEqual(result.code, "CHANGESET_APPROVAL_REQUIRED")
        self.assertEqual(adapter.commands, [])
        plan = vfx.plan_publication(request)
        self.assertEqual((plan.ok, plan.execution_mode, plan.code), (True, vfx.ExecutionMode.PLANNED, "WAITING_APPROVAL"))
        approved = change_set.approve("usr_reviewer_01", "2026-09-04T00:04:00Z")
        self.assertEqual(approved.approval_state, vfx.ApprovalState.APPROVED)

    def test_unapproved_enable_rejected(self) -> None:
        adapter = vfx.DeterministicMockUnityAdapter()
        request = binding_request(self.recipe, "vfxbind_home_door_unlocked", True, "evt_vfx_001", approved=False)
        result = vfx.VfxShaderService(adapter).set_binding_enabled(
            request, "vfxbind_home_door_unlocked", True, permissions={"vfx:write"}
        )
        self.assertEqual(result.code, "CHANGESET_APPROVAL_REQUIRED")
        self.assertEqual(adapter.commands, [])

    def test_publish_success_updates_provenance_and_event_matches_schema(self) -> None:
        adapter = vfx.DeterministicMockUnityAdapter()
        self.assertEqual(adapter.health_check().integration_id, "unity")
        self.assertEqual(adapter.capabilities().integration_id, "unity")
        result = vfx.VfxShaderService(adapter).publish(approved_request(self.recipe), permissions={"vfx:publish"})
        self.assertTrue(result.ok)
        self.assertEqual(result.execution_mode, vfx.ExecutionMode.MOCK)
        self.assertEqual(result.output_provenance.approval_state, vfx.ApprovalState.PUBLISHED)
        self.assertEqual(result.output_provenance.execution_mode, vfx.ExecutionMode.MOCK)
        self.assertRegex(result.output_provenance.checksum_sha256, r"^[0-9a-f]{64}$")
        schema = json.loads((MODULE_ROOT / "contracts/events/vfx.recipe.published.v1.schema.json").read_text())
        validate_schema(result.events[0], schema)

    def test_publication_rejects_scope_version_and_adapter_identity_mismatch(self) -> None:
        approved = approved_request(self.recipe)
        service = vfx.VfxShaderService(vfx.DeterministicMockUnityAdapter())
        wrong_scope = replace(approved, change_set=replace(approved.change_set, target_object_ids=("so_other",)))
        wrong_base = replace(approved, change_set=replace(approved.change_set, base_version="wrong-version"))
        self.assertEqual(service.publish(wrong_scope, permissions={"vfx:publish"}).code, "CHANGESET_INVALID")
        self.assertEqual(service.publish(wrong_base, permissions={"vfx:publish"}).code, "CHANGESET_INVALID")

        changed_parameters = dict(self.recipe.parameters)
        changed_parameters["intensity"] = 0.4
        changed_recipe = replace(self.recipe, parameters=changed_parameters)
        changed_request = replace(approved, recipe=changed_recipe)
        self.assertEqual(service.publish(changed_request, permissions={"vfx:publish"}).code, "CHANGESET_CONTENT_MISMATCH")

        mutated_approval = approved_request(self.recipe)
        mutated_approval.change_set.proposed_values["parameters"]["intensity"] = 0.45
        self.assertEqual(service.publish(mutated_approval, permissions={"vfx:publish"}).code, "CHANGESET_INVALID")

        class MismatchedAdapter(vfx.DeterministicMockUnityAdapter):
            def publish(self, command):
                return replace(super().publish(command), project_id="prj_wrong")

        mismatched = vfx.VfxShaderService(MismatchedAdapter()).publish(approved, permissions={"vfx:publish"})
        self.assertEqual((mismatched.code, mismatched.blocks_core_build), ("ADAPTER_RESULT_INVALID", False))

        class WrongIntegrationAdapter(vfx.DeterministicMockUnityAdapter):
            def health_check(self):
                return replace(super().health_check(), integration_id="engine-unity")

        contract = vfx.VfxShaderService(WrongIntegrationAdapter()).publish(approved, permissions={"vfx:publish"})
        self.assertEqual(contract.code, "ADAPTER_CONTRACT_INVALID")

        class InvalidTimestampAdapter(vfx.DeterministicMockUnityAdapter):
            def publish(self, command):
                return replace(super().publish(command), occurred_at="yesterday")

        timestamp = vfx.VfxShaderService(InvalidTimestampAdapter()).publish(approved, permissions={"vfx:publish"})
        self.assertEqual(timestamp.code, "ADAPTER_RESULT_INVALID")

    def test_binding_success_event_matches_schema(self) -> None:
        adapter = vfx.DeterministicMockUnityAdapter()
        result = vfx.VfxShaderService(adapter).set_binding_enabled(
            binding_request(self.recipe, "vfxbind_home_door_unlocked", True, "evt_vfx_binding_001", approved=True),
            "vfxbind_home_door_unlocked", True, permissions={"vfx:write"},
        )
        self.assertTrue(result.ok)
        schema = json.loads((MODULE_ROOT / "contracts/events/vfx.binding.changed.v1.schema.json").read_text())
        validate_schema(result.events[0], schema)
        disabled = vfx.VfxShaderService(adapter).set_binding_enabled(
            binding_request(self.recipe, "vfxbind_home_door_unlocked", False, "evt_vfx_binding_002", approved=True),
            "vfxbind_home_door_unlocked", False, permissions={"vfx:write"},
        )
        self.assertTrue(disabled.ok)
        self.assertFalse(disabled.events[0]["payload"]["enabled"])
        self.assertEqual(adapter.commands[-1].target_sceneops_ids, ("so_door_home_01",))

        class MissingEvidenceAdapter(vfx.DeterministicMockUnityAdapter):
            def publish(self, command):
                return replace(super().publish(command), checksum_sha256=None)

        missing = vfx.VfxShaderService(MissingEvidenceAdapter()).set_binding_enabled(
            binding_request(self.recipe, "vfxbind_home_door_unlocked", True, "evt_vfx_binding_003", approved=True),
            "vfxbind_home_door_unlocked", True, permissions={"vfx:write"},
        )
        self.assertEqual(missing.code, "ADAPTER_RESULT_INVALID")

        wrong_value = vfx.VfxShaderService(adapter).set_binding_enabled(
            binding_request(self.recipe, "vfxbind_home_door_unlocked", True, "evt_vfx_binding_004", approved=True),
            "vfxbind_home_door_unlocked", False, permissions={"vfx:write"},
        )
        self.assertEqual(wrong_value.code, "CHANGESET_CONTENT_MISMATCH")

    def test_disabled_offline_permission_and_publish_failure_are_non_blocking(self) -> None:
        request = approved_request(self.recipe)
        disabled = vfx.VfxShaderService().publish(request, module_enabled=False, permissions={"vfx:publish"})
        denied = vfx.VfxShaderService().publish(request)
        offline_adapter = vfx.DeterministicMockUnityAdapter(online=False)
        offline = vfx.VfxShaderService(offline_adapter).publish(request, permissions={"vfx:publish"})
        failed = vfx.VfxShaderService(vfx.DeterministicMockUnityAdapter(fail_publish=True)).publish(
            request, permissions={"vfx:publish"}
        )
        self.assertEqual([disabled.code, denied.code, offline.code, failed.code], [
            "MODULE_DISABLED", "PERMISSION_DENIED", "INTEGRATION_OFFLINE", "UNITY_PUBLISH_FAILED"
        ])
        self.assertTrue(all(not item.blocks_core_build for item in (disabled, denied, offline, failed)))

    def test_render_offline_makes_no_calls_and_mock_success_failure_are_truthful(self) -> None:
        offline = vfx.DeterministicMockRenderAdapter(online=False)
        offline_result = vfx.VfxShaderService(render_adapter=offline).render_external_preview(
            self.recipe, permissions={"vfx:read"}
        )
        self.assertEqual(offline_result.code, "INTEGRATION_OFFLINE")
        self.assertEqual((offline.dry_run_calls, offline.render_calls), (0, 0))
        render = vfx.DeterministicMockRenderAdapter()
        success = vfx.VfxShaderService(render_adapter=render).render_external_preview(self.recipe, permissions={"vfx:read"})
        failed = vfx.VfxShaderService(render_adapter=vfx.DeterministicMockRenderAdapter(fail_render=True)).render_external_preview(
            self.recipe, permissions={"vfx:read"}
        )
        self.assertEqual((success.ok, success.execution_mode), (True, vfx.ExecutionMode.MOCK))
        self.assertEqual(success.output_provenance.approval_state, vfx.ApprovalState.PROPOSED)
        self.assertEqual((failed.code, failed.execution_mode, failed.blocks_core_build), ("RENDER_FAILED", vfx.ExecutionMode.MOCK, False))


class FrontendStateTests(unittest.TestCase):
    def test_all_visible_editor_states_are_implemented(self) -> None:
        source = (MODULE_ROOT / "frontend/src/editors/VfxShaderEditor.tsx").read_text(encoding="utf-8")
        types = (MODULE_ROOT / "frontend/src/types.ts").read_text(encoding="utf-8")
        for state in ("loading", "empty", "failed", "offline", "permission", "disabled", "ready"):
            self.assertIn(f"'{state}'", types)
            self.assertIn(state, source)
        self.assertIn("role=\"alert\"", source)
        self.assertIn("核心构建不受影响", source)
        preview = (MODULE_ROOT / "frontend/src/editors/VfxPreviewEditor.tsx").read_text(encoding="utf-8")
        for field in ("previewId", "passes", "seed", "frameCount", "qualityTier", "warnings", "mode"):
            self.assertIn(field, preview)
        index = (MODULE_ROOT / "frontend/src/index.ts").read_text(encoding="utf-8")
        self.assertIn("import('./editors/VfxRecipeEditor')", index)
        self.assertIn("import('./editors/VfxShaderEditor')", index)
        self.assertIn("import('./editors/VfxPreviewEditor')", index)


if __name__ == "__main__":
    unittest.main()
