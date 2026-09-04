from __future__ import annotations

from typing import Dict, List

from .models import GeneratedTestCase, GeneratedTestPlan, GameplayGraph


_KIND_ASSERTIONS: Dict[str, List[str]] = {
    "edit_mode": [
        "Graph serialization preserves stable IDs and schema version.",
        "All referenced sceneops_id values resolve in the project scene map.",
    ],
    "play_mode": [
        "Unity reaches every target node through allowed transitions.",
        "Observed state effects match the graph version under test.",
    ],
    "behavior": [
        "The structured action sequence reaches its declared acceptance criteria.",
        "Runtime events and state changes are recorded as structured evidence.",
    ],
}


def generate_test_plan(graph: GameplayGraph) -> GeneratedTestPlan:
    tests = [
        GeneratedTestCase(
            test_id=reference.test_id,
            test_kind=reference.test_kind,
            graph_id=graph.graph_id,
            graph_version=graph.version,
            target_node_ids=list(reference.target_node_ids),
            acceptance_criterion_ids=list(reference.acceptance_criterion_ids),
            assertions=list(_KIND_ASSERTIONS[reference.test_kind]),
        )
        for reference in sorted(graph.generated_tests, key=lambda item: item.test_id)
    ]
    return GeneratedTestPlan(
        graph_id=graph.graph_id,
        graph_version=graph.version,
        tests=tests,
    )
