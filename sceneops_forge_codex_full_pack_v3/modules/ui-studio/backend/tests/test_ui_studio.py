import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ui_studio import (ChangeSet, ChangeSetState, ExecutionMode, Provenance,
                       ResolutionProfile, SafeArea, UiFlow, UiMappingRequest,
                       UiElement, UiScreen, UiStudioService, UnityUiMappingResult,
                       compare_visual_fixture, load_ui_flow_template,
                       load_warehouse_escape_template)


class MockUnityUiAdapter:
    """Explicit deterministic mock; it never reaches Unity."""
    def capability_report(self): return {"ui_mapping": True}
    def dry_run_ui_mapping(self, request):
        return UnityUiMappingResult(request.mapping_id, request.unity_canvas_path, request.prefab_id, ExecutionMode.MOCK, "mock-unity-ui/1", "已生成提议预览。", provenance("mock-unity-ui/1"))
    def publish_ui_mapping(self, request):
        return UnityUiMappingResult(request.mapping_id, request.unity_canvas_path, request.prefab_id, ExecutionMode.MOCK, "mock-unity-ui/1", "模拟发布；未写入 Unity。", published_provenance())


def provenance(adapter_version="0.1.0"):
    return _provenance(ChangeSetState.PROPOSED, adapter_version)


def published_provenance():
    return _provenance(ChangeSetState.PUBLISHED, "mock-unity-ui/1")


def _provenance(state, adapter_version):
    return Provenance("art_ui_key_door_v1", "ui-flow", "prj_home", "v1", "ui-studio", "ui-studio", adapter_version, "abc123", ("so_key_home_01",), "ui-flow@1", "hero-key-door@1", "usr_designer", ExecutionMode.MOCK, "2026-09-04T00:00:00Z", state, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def profile(): return ResolutionProfile("iphone-notch-landscape", 2532, 1170, SafeArea(80, 30, 80, 30))


def hero_flow():
    return UiFlow("flow.key-door", "find-my-way-home", "hud.home", (
        UiScreen("hud.home", "任务 HUD", "hud", {"zh-CN": "寻找回家的钥匙", "en-US": "Find the key home"}, ("prompt.key-picked", "prompt.door-locked")),
        UiScreen("prompt.key-picked", "拾取钥匙", "feedback_prompt", {"zh-CN": "获得：家门钥匙", "en-US": "Key acquired: Home key"}, ("prompt.door-unlocked",)),
        UiScreen("prompt.door-locked", "锁门反馈", "quest_prompt", {"zh-CN": "门锁着，需要找到钥匙。", "en-US": "The door is locked. Find a key."}),
        UiScreen("prompt.door-unlocked", "解锁反馈", "feedback_prompt", {"zh-CN": "钥匙转动，门已解锁。", "en-US": "The key turns. Door unlocked."}),
    ))


def mapping_request(target="so_key_home_01"):
    return UiMappingRequest(
        "map_key", "flow.key-door", "prompt.key-picked", "Canvas/Hud", "prefab.key",
        "v1", "usr_designer", "prj_home", (target,),
    )


def mapping_change(change_set_id, request=None):
    request = request or mapping_request()
    proposed = {
        "flow_id": request.flow_id, "screen_id": request.screen_id,
        "unity_canvas_path": request.unity_canvas_path, "prefab_id": request.prefab_id,
    }
    return ChangeSet(
        change_set_id, request, "v1", "unity", request.target_sceneops_ids,
        {"prefab_id": "none"}, proposed, "增强拾取反馈", "显示钥匙提示", "HUD", "low",
        "验证流程", "移除映射", ("ui:publish", "human-approval"),
    )


class UiStudioTests(unittest.TestCase):
    def setUp(self): self.service = UiStudioService()

    def test_manifest_and_public_api(self):
        path = os.path.join(ROOT, "..", "module.yaml")
        with open(path, encoding="utf-8") as source: text = source.read()
        self.assertIn("id: ui-studio", text); self.assertIn("frontend: ./frontend/src/index.ts", text)
        self.assertNotIn("    - engine-unity", text); self.assertIn("optional_integrations:\n    - unity", text)
        from ui_studio import UiStudioService as PublicService
        self.assertIs(PublicService, UiStudioService)

    def test_hero_flow_success_and_resolution_safe_area(self):
        report = self.service.validate_flow(hero_flow(), profile(), 80, provenance())
        self.assertTrue(report.valid); self.assertEqual(report.mode, ExecutionMode.MOCK)

    def test_failure_for_missing_target_and_empty_safe_area(self):
        broken = UiFlow("flow.bad", "second-game", "missing", (UiScreen("one", "One", "hud", {"en-US": "x"}, ("nope",)),))
        report = self.service.validate_flow(broken, ResolutionProfile("bad", 10, 10, SafeArea(5, 0, 5, 0)), 80, provenance())
        self.assertFalse(report.valid); self.assertEqual({i.code for i in report.issues}, {"FLOW_ENTRY_INVALID", "FLOW_TARGET_MISSING", "SAFE_AREA_EMPTY"})

    def test_localization_overflow(self):
        flow = UiFlow("flow.copy", "second-game", "one", (UiScreen("one", "One", "menu", {"de-DE": "x" * 9}),))
        self.assertEqual(self.service.validate_flow(flow, profile(), 8, provenance()).issues[0].code, "LOCALIZATION_OVERFLOW")

    def test_safe_area_checks_element_bounds_and_anchors(self):
        flow = UiFlow("flow.bounds", "second-game", "one", (
            UiScreen("one", "One", "hud", {"zh-CN": "任务"}, elements=(UiElement("prompt", "safe-bottom-center", 0, 1, 300, 64),)),
        ))
        report = self.service.validate_flow(flow, profile(), 80, provenance())
        self.assertEqual(report.issues[0].code, "SAFE_AREA_ELEMENT_OUT_OF_BOUNDS")

    def test_visual_fixture_is_deterministic_mock(self):
        path = os.path.join(ROOT, "..", "frontend", "src", "fixtures", "keyDoorVisualFixture.json")
        with open(path, encoding="utf-8") as source: fixture = json.load(source)
        self.assertEqual(fixture["mode"], "mock"); self.assertEqual(fixture["fixture_id"], "ui-visual-key-door-v1")
        self.assertEqual([item["id"] for item in fixture["screens"]][-2:], ["prompt.door-locked", "prompt.door-unlocked"])
        self.assertTrue(compare_visual_fixture(fixture, fixture).passed)
        changed = dict(fixture); changed["profile"] = "wrong"
        self.assertFalse(compare_visual_fixture(fixture, changed).passed)

    def test_warehouse_template_loads_and_validates(self):
        report = self.service.validate_flow(load_warehouse_escape_template(), profile(), 80, provenance())
        self.assertTrue(report.valid)
        with self.assertRaisesRegex(ValueError, "unknown bundled UI template"):
            load_ui_flow_template("../../outside-workspace")

    def test_disabled_and_offline_availability_contract(self):
        with open(os.path.join(ROOT, "..", "frontend", "src", "commands", "uiCommands.ts"), encoding="utf-8") as source: commands = source.read()
        self.assertIn('reason: "offline"', commands); self.assertIn('reason: "disabled"', commands)

    def test_public_editors_are_non_placeholder_and_expose_states(self):
        editor_dir = os.path.join(ROOT, "..", "frontend", "src", "editors")
        for filename in ("uiFlowEditorView.tsx", "uiPreviewEditorView.tsx"):
            with open(os.path.join(editor_dir, filename), encoding="utf-8") as source: view = source.read()
            self.assertNotIn("return null", view)
            for state in ("loading", "empty", "failed", "offline", "permission", "disabled"):
                self.assertIn(state, view)
        with open(os.path.join(editor_dir, "uiFlowEditorView.tsx"), encoding="utf-8") as source: flow_view = source.read()
        self.assertIn("onPromptTextChange", flow_view); self.assertIn("resolutionLabel", flow_view); self.assertIn("validationStatus", flow_view)
        with open(os.path.join(editor_dir, "uiPreviewEditorView.tsx"), encoding="utf-8") as source: preview_view = source.read()
        self.assertIn("safeAreaLabel", preview_view); self.assertIn("diffStatus", preview_view); self.assertIn("onSelectPrompt", preview_view)

    def test_frontend_commands_have_runtime_schema_and_gateway_surface(self):
        path = os.path.join(ROOT, "..", "frontend", "src", "commands", "uiCommands.ts")
        with open(path, encoding="utf-8") as source: commands = source.read()
        for surface in ("inputSchema", "parse(input", "UiCommandGateway", "gateway.execute", "canExecute", "permission", "offline"):
            self.assertIn(surface, commands)

    def test_declared_event_contracts_exist_and_are_json_schemas(self):
        with open(os.path.join(ROOT, "..", "module.yaml"), encoding="utf-8") as source: manifest = source.read()
        declared = re.findall(r"- (ui\.[\w.]+@\d+)", manifest)
        events_dir = os.path.join(ROOT, "..", "contracts", "events")
        for event in declared:
            name, version = event.split("@")
            path = os.path.join(events_dir, f"{name}.v{version}.json")
            with open(path, encoding="utf-8") as source: schema = json.load(source)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema); self.assertIn("payload", schema["properties"])
            self.assertIn("actor", schema["properties"]); self.assertIn("actor", schema["required"])
            self.assertFalse(schema["additionalProperties"])

    def test_provenance_is_complete_and_mock(self):
        record = provenance()
        self.assertEqual(record.producing_module, "ui-studio"); self.assertEqual(record.mode, ExecutionMode.MOCK)
        self.assertEqual(record.approval_state, ChangeSetState.PROPOSED)
        self.assertRegex(record.checksum, r"^[0-9a-f]{64}$")
        record.validate()

    def test_unity_adapter_contract_and_changeset_lifecycle(self):
        change = mapping_change("cs_key")
        preview = self.service.propose_mapping(change, MockUnityUiAdapter())
        self.assertEqual(preview.mapping_result.mode, ExecutionMode.MOCK); self.assertEqual(change.state, ChangeSetState.PROPOSED)
        with self.assertRaises(PermissionError): change.publish(MockUnityUiAdapter())
        change.approve("usr_reviewer", "2026-09-04T00:01:00Z"); result = change.publish(MockUnityUiAdapter())
        self.assertEqual(change.state, ChangeSetState.PUBLISHED); self.assertEqual(result.mode, ExecutionMode.MOCK)
        self.assertEqual(change.target_integration, "unity"); self.assertEqual(change.approved_by, "usr_reviewer")

    def test_changeset_rejects_wrong_targets_and_unpublishable_output(self):
        request = mapping_request()
        change = ChangeSet("cs_bad", request, "wrong", "engine-unity", (), {}, {}, "", "", "", "", "", "", ())
        with self.assertRaises(ValueError): change.approve("reviewer", "2026-09-04T00:00:00Z")

        valid = mapping_change("cs_output", request)
        valid.approve("reviewer", "2026-09-04T00:00:00Z")
        class BadAdapter:
            def capability_report(self): return {"ui_mapping": True}
            def publish_ui_mapping(self, ignored):
                return UnityUiMappingResult("wrong", "Canvas/Hud", "prefab.key", ExecutionMode.PLANNED, "v1", "bad", None)
        with self.assertRaises(ValueError): valid.publish(BadAdapter())

        for mode, output_provenance in ((ExecutionMode.BLOCKED, published_provenance()), (ExecutionMode.MOCK, None)):
            candidate = mapping_change("cs_output_" + mode.value, request)
            candidate.approve("reviewer", "2026-09-04T00:00:00Z")
            class OutputAdapter:
                def capability_report(self): return {"ui_mapping": True}
                def publish_ui_mapping(self, ignored):
                    return UnityUiMappingResult(request.mapping_id, request.unity_canvas_path, request.prefab_id, mode, "mock-unity-ui/1", "bad", output_provenance)
            with self.assertRaises(ValueError): candidate.publish(OutputAdapter())

    def test_publish_revalidates_approved_changeset_before_adapter_call(self):
        change = mapping_change("cs_mutated")
        change.approve("reviewer", "2026-09-04T00:00:00Z")
        change.id = "cs_replaced_after_approval"
        replacement = mapping_request("so_door_home_01")
        change.request = replacement
        change.target_object_ids = replacement.target_sceneops_ids
        change.proposed_values = {
            "flow_id": replacement.flow_id, "screen_id": replacement.screen_id,
            "unity_canvas_path": replacement.unity_canvas_path, "prefab_id": replacement.prefab_id,
        }
        class NoCallAdapter:
            def capability_report(self): return {"ui_mapping": True}
            def publish_ui_mapping(self, ignored): raise AssertionError("adapter must not be called")
        with self.assertRaisesRegex(PermissionError, "content changed after approval"):
            change.publish(NoCallAdapter())


if __name__ == "__main__": unittest.main()
