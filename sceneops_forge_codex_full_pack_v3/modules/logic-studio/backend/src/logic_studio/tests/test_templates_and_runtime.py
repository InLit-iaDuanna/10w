import unittest

from logic_studio.models import CompileTemplateRequest
from logic_studio.runtime import GameplayGraphRuntime
from logic_studio.serialization import serialize_gameplay_graph
from logic_studio.templates import load_default_template_catalog
from logic_studio.tests.support import compile_example, load_json
from logic_studio.validation import validate_gameplay_graph


class TemplateAndRuntimeTests(unittest.TestCase):
    def test_hero_template_is_deterministic_and_valid(self):
        graph_a = compile_example("hero-key-door.binding.json")
        graph_b = compile_example("hero-key-door.binding.json")
        self.assertEqual(serialize_gameplay_graph(graph_a), serialize_gameplay_graph(graph_b))
        report = validate_gameplay_graph(graph_a)
        self.assertTrue(report.valid, report.issues)
        self.assertEqual(graph_a.mode.value, "mock")

    def test_key_door_behavior_reaches_home_ending(self):
        runtime = GameplayGraphRuntime(compile_example("hero-key-door.binding.json"))
        runtime.step("quest_active")
        runtime.step("target_interaction")
        self.assertEqual(
            [edge.target_node_id for edge in runtime.available_transitions()],
            ["locked_feedback"],
        )
        runtime.step("locked_feedback")
        runtime.step("collectible_pickup")
        self.assertIn("asset_key_home_01", runtime.state["inventory.items"])
        self.assertEqual(runtime.state["quest.stage"], "open_target")
        runtime.step("pickup_feedback")
        runtime.step("target_interaction")
        self.assertEqual(
            [edge.target_node_id for edge in runtime.available_transitions()],
            ["open_feedback"],
        )
        runtime.step("open_feedback")
        self.assertTrue(runtime.state["target.is_open"])
        self.assertEqual(runtime.state["quest.stage"], "complete")
        runtime.step("home_dialogue")
        runtime.step("ending")
        self.assertEqual(runtime.current_node_id, "ending")
        self.assertIn("target.locked_feedback_shown", runtime.event_log)
        self.assertIn("ending.reached", runtime.event_log)

    def test_warehouse_switch_door_reuses_template_compiler(self):
        graph = compile_example("warehouse-switch-door.binding.json")
        self.assertTrue(validate_gameplay_graph(graph).valid)
        runtime = GameplayGraphRuntime(graph)
        runtime.step("switch_interaction")
        self.assertTrue(runtime.state["switch.is_active"])
        runtime.step("switch_feedback")
        runtime.step("target_interaction")
        runtime.step("open_feedback")
        runtime.step("ending")
        self.assertTrue(runtime.state["target.is_open"])
        self.assertEqual(runtime.current_node_id, "ending")

    def test_template_bindings_keep_names_separate_from_identity(self):
        payload = load_json("contracts/examples/hero-key-door.binding.json")
        payload["bindings"]["target_display_name"] = "重命名后的家门"
        graph = load_default_template_catalog().compile(
            CompileTemplateRequest.model_validate(payload)
        )
        target = next(
            item for item in graph.scene_objects if item.sceneops_id == "sobj_home_door_01"
        )
        relationship = next(
            item
            for item in graph.relationships
            if item.relationship_id == "collectible_unlocks_target"
        )
        self.assertEqual(target.display_name, "重命名后的家门")
        self.assertEqual(relationship.target_sceneops_id, "sobj_home_door_01")
        self.assertTrue(validate_gameplay_graph(graph).valid)

    def test_missing_template_binding_fails_explicitly(self):
        payload = load_json("contracts/examples/warehouse-switch-door.binding.json")
        del payload["bindings"]["switch_sceneops_id"]
        request = CompileTemplateRequest.model_validate(payload)
        with self.assertRaisesRegex(ValueError, "switch_sceneops_id"):
            load_default_template_catalog().compile(request)


if __name__ == "__main__":
    unittest.main()
