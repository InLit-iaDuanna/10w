from __future__ import annotations

import unittest

from sceneops_production_planner.fixtures import key_door_snapshot
from sceneops_production_planner.models import AssignmentKind, EstimateKind, Workstream
from sceneops_production_planner.tests.support import create_context, create_request, create_service


class GenerationTests(unittest.TestCase):
    def test_key_door_fixture_generates_deterministic_complete_graph(self) -> None:
        snapshot = key_door_snapshot()
        first = create_service(snapshot).create_plan(create_request(snapshot), create_context())
        second = create_service(snapshot).create_plan(create_request(snapshot), create_context())

        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))
        self.assertEqual([task.workstream for task in first.plan.tasks], list(Workstream))
        self.assertEqual(len(first.plan.tasks), 12)
        self.assertEqual(len(first.plan.dependencies), 21)
        self.assertTrue(all(not task.confirmed for task in first.plan.tasks))
        self.assertTrue(all(task.inputs and task.outputs and task.acceptance for task in first.plan.tasks))
        self.assertEqual(first.event_payloads[0].event_type, "production.plan.drafted")

    def test_assignments_include_human_and_agent_owners(self) -> None:
        snapshot = key_door_snapshot()
        plan = create_service(snapshot).create_plan(create_request(snapshot), create_context()).plan
        kinds = {task.assignment.kind for task in plan.tasks}
        self.assertEqual(kinds, {AssignmentKind.HUMAN, AssignmentKind.AGENT})
        self.assertTrue(all(task.assignment.assignee_id for task in plan.tasks))

    def test_critical_path_is_visible_and_uses_predicted_estimates(self) -> None:
        snapshot = key_door_snapshot()
        graph = create_service(snapshot).create_plan(create_request(snapshot), create_context()).graph
        self.assertEqual(graph.critical_path.total_hours, 60)
        self.assertEqual(graph.critical_path.task_ids[0], "task:feature:key-and-door:design")
        self.assertEqual(graph.critical_path.task_ids[-1], "task:feature:key-and-door:test")
        self.assertTrue(all(kind == EstimateKind.PREDICTED for kind in graph.critical_path.estimate_basis))
        self.assertEqual(len(graph.nodes), 12)


if __name__ == "__main__":
    unittest.main()
