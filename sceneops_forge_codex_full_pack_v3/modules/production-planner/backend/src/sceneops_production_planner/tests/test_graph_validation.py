from __future__ import annotations

import unittest

from sceneops_production_planner.graph import apply_validation, build_graph_view
from sceneops_production_planner.models import MilestoneState, TaskDependency, TaskInput
from sceneops_production_planner.tests.support import create_plan


class GraphValidationTests(unittest.TestCase):
    def test_cycle_detection_blocks_plan(self) -> None:
        _, plan = create_plan()
        design = plan.tasks[0]
        test = plan.tasks[-1]
        reverse = TaskDependency(
            dependency_id="dependency:cycle:test:design",
            predecessor_task_id=test.task_id,
            successor_task_id=design.task_id,
            required_output_type=test.outputs[0].artifact_type,
        )
        design_with_input = design.model_copy(
            update={
                "inputs": design.inputs
                + [
                    TaskInput(
                        input_id="input:cycle:test:design",
                        source_kind="task_output",
                        source_id=test.task_id,
                        required_artifact_type=test.outputs[0].artifact_type,
                    )
                ]
            }
        )
        tasks = [design_with_input if task.task_id == design.task_id else task for task in plan.tasks]
        blocked = apply_validation(plan.model_copy(update={"tasks": tasks, "dependencies": plan.dependencies + [reverse]}))
        cycle = [blocker for blocker in blocked.blockers if blocker.code.value == "dependency_cycle"]
        self.assertEqual(blocked.status.value, "blocked")
        self.assertEqual(len(cycle), 1)
        self.assertEqual(cycle[0].task_ids[0], cycle[0].task_ids[-1])
        self.assertEqual(build_graph_view(blocked).critical_path.task_ids, [])

    def test_missing_prerequisite_blocks_plan(self) -> None:
        _, plan = create_plan()
        missing = TaskDependency(
            dependency_id="dependency:missing",
            predecessor_task_id="task:missing",
            successor_task_id=plan.tasks[0].task_id,
            required_output_type="missing-output",
        )
        blocked = apply_validation(plan.model_copy(update={"dependencies": plan.dependencies + [missing]}))
        codes = {blocker.code.value for blocker in blocked.blockers}
        self.assertIn("missing_prerequisite", codes)
        self.assertEqual(blocked.status.value, "blocked")

    def test_orphan_task_input_is_reported_as_missing_prerequisite(self) -> None:
        _, plan = create_plan()
        design = plan.tasks[0]
        orphan = TaskInput(
            input_id="input:orphan",
            source_kind="task_output",
            source_id="task:missing-source",
            required_artifact_type="missing-output",
        )
        changed_design = design.model_copy(update={"inputs": design.inputs + [orphan]})
        tasks = [changed_design if task.task_id == design.task_id else task for task in plan.tasks]
        graph = build_graph_view(plan.model_copy(update={"tasks": tasks}))
        matching = [blocker for blocker in graph.blockers if blocker.blocker_id.endswith("orphan-input")]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].code.value, "missing_prerequisite")

    def test_impossible_milestone_state_is_blocked(self) -> None:
        _, plan = create_plan()
        milestone = plan.milestones[0].model_copy(update={"state": MilestoneState.READY})
        changed = plan.model_copy(update={"milestones": [milestone] + plan.milestones[1:]})
        graph = build_graph_view(changed)
        self.assertIn("impossible_milestone_state", {blocker.code.value for blocker in graph.blockers})
        self.assertEqual(graph.milestone_readiness[0].state, MilestoneState.BLOCKED)


if __name__ == "__main__":
    unittest.main()
