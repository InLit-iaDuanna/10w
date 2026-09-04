import json
import unittest

from logic_studio.models import GameplayGraph
from logic_studio.serialization import (
    InvalidGraphVersionTransition,
    UnsupportedGraphVersion,
    deserialize_gameplay_graph,
    diff_gameplay_graphs,
    serialize_gameplay_graph,
)
from logic_studio.tests.support import compile_example
from logic_studio.validation import validate_gameplay_graph


def issue_codes(graph):
    return {issue.code for issue in validate_gameplay_graph(graph).issues}


class ValidationTests(unittest.TestCase):
    def test_serialization_round_trip_and_version_rejection(self):
        graph = compile_example("hero-key-door.binding.json")
        document = serialize_gameplay_graph(graph)
        self.assertEqual(deserialize_gameplay_graph(document), graph)
        payload = json.loads(document)
        payload["schema_version"] = 2
        with self.assertRaises(UnsupportedGraphVersion):
            deserialize_gameplay_graph(json.dumps(payload))

    def test_meaningful_graph_diff_requires_a_new_version(self):
        base = compile_example("warehouse-switch-door.binding.json")
        payload = base.model_dump(mode="json")
        payload["version"] = 2
        open_node = next(node for node in payload["nodes"] if node["node_id"] == "open_feedback")
        open_node["effects"][0]["value"] = False
        proposed = GameplayGraph.model_validate(payload)
        diff = diff_gameplay_graphs(base, proposed)
        self.assertEqual(len(diff.entries), 1)
        self.assertEqual(diff.entries[0].entity_id, "open_feedback")
        self.assertEqual(diff.entries[0].change, "modified")
        with self.assertRaises(InvalidGraphVersionTransition):
            diff_gameplay_graphs(base, base)

    def test_unreachable_and_dead_branches_are_detected(self):
        payload = compile_example("warehouse-switch-door.binding.json").model_dump(mode="json")
        payload["nodes"].extend(
            [
                {"node_id": "orphan", "kind": "state", "label": "Orphan"},
                {"node_id": "dead", "kind": "state", "label": "Dead"},
            ]
        )
        payload["edges"].append(
            {"edge_id": "start_to_dead", "source_node_id": "start", "target_node_id": "dead"}
        )
        graph = GameplayGraph.model_validate(payload)
        self.assertIn("UNREACHABLE_NODE", issue_codes(graph))
        self.assertIn("DEAD_BRANCH", issue_codes(graph))

    def test_cycle_without_exit_is_detected(self):
        payload = compile_example("warehouse-switch-door.binding.json").model_dump(mode="json")
        payload["nodes"].extend(
            [
                {"node_id": "cycle_a", "kind": "state", "label": "Cycle A"},
                {"node_id": "cycle_b", "kind": "state", "label": "Cycle B"},
            ]
        )
        payload["edges"].extend(
            [
                {"edge_id": "start_to_cycle", "source_node_id": "start", "target_node_id": "cycle_a"},
                {"edge_id": "cycle_a_b", "source_node_id": "cycle_a", "target_node_id": "cycle_b"},
                {"edge_id": "cycle_b_a", "source_node_id": "cycle_b", "target_node_id": "cycle_a"},
            ]
        )
        self.assertIn(
            "CYCLE_WITHOUT_EXIT",
            issue_codes(GameplayGraph.model_validate(payload)),
        )

    def test_condition_effect_and_conflict_validation(self):
        payload = compile_example("warehouse-switch-door.binding.json").model_dump(mode="json")
        target = next(node for node in payload["nodes"] if node["node_id"] == "target_interaction")
        target["conditions"][0]["operator"] = "greater_than"
        switch = next(node for node in payload["nodes"] if node["node_id"] == "switch_interaction")
        switch["effects"].append(
            {"effect_id": "deactivate_switch", "variable_id": "switch.is_active", "operation": "set", "value": False}
        )
        codes = issue_codes(GameplayGraph.model_validate(payload))
        self.assertIn("INVALID_CONDITION_OPERATOR", codes)
        self.assertIn("CONFLICTING_EFFECTS", codes)

    def test_missing_stable_object_reference_is_detected(self):
        payload = compile_example("hero-key-door.binding.json").model_dump(mode="json")
        payload["scene_objects"] = [
            item for item in payload["scene_objects"] if item["sceneops_id"] != "sobj_home_door_01"
        ]
        codes = issue_codes(GameplayGraph.model_validate(payload))
        self.assertIn("MISSING_SCENE_OBJECT_REFERENCE", codes)

    def test_unsatisfied_acceptance_criterion_is_detected(self):
        payload = compile_example("warehouse-switch-door.binding.json").model_dump(mode="json")
        payload["generated_tests"] = []
        codes = issue_codes(GameplayGraph.model_validate(payload))
        self.assertIn("UNSATISFIED_ACCEPTANCE_CRITERION", codes)


if __name__ == "__main__":
    unittest.main()
