from __future__ import annotations

from collections import Counter
from typing import Any, List, Mapping, Set

from .graph_analysis import check_reachability
from .models import (
    GameplayGraph,
    GraphValidationReport,
    NodeKind,
    StateVariable,
    ValidationIssue,
)
from .validation_support import add_issue
from .validation_values import (
    check_conditions,
    check_effects,
    check_variable_initial_values,
)


def validate_gameplay_graph(graph: GameplayGraph) -> GraphValidationReport:
    issues: List[ValidationIssue] = []
    variables = {item.variable_id: item for item in graph.state_variables}
    nodes = {item.node_id: item for item in graph.nodes}
    events = {item.event_id for item in graph.events}
    scene_objects = {item.sceneops_id for item in graph.scene_objects}
    criteria = {item.criterion_id for item in graph.acceptance_criteria}

    _check_duplicates(graph, issues)
    check_variable_initial_values(graph.state_variables, issues)
    _check_nodes(graph, variables, nodes, events, scene_objects, criteria, issues)
    _check_edges(graph, variables, nodes, events, issues)
    _check_relationships(graph, scene_objects, issues)
    check_reachability(graph, nodes, issues)
    _check_generated_tests(graph, nodes, criteria, issues)

    ordered = sorted(issues, key=lambda item: (item.location, item.code, item.message))
    return GraphValidationReport(
        graph_id=graph.graph_id,
        graph_version=graph.version,
        valid=not any(item.severity == "error" for item in ordered),
        issues=ordered,
    )


def _check_duplicates(graph: GameplayGraph, issues: List[ValidationIssue]) -> None:
    groups = {
        "state_variables": [item.variable_id for item in graph.state_variables],
        "events": [item.event_id for item in graph.events],
        "scene_objects": [item.sceneops_id for item in graph.scene_objects],
        "nodes": [item.node_id for item in graph.nodes],
        "edges": [item.edge_id for item in graph.edges],
        "relationships": [item.relationship_id for item in graph.relationships],
        "acceptance_criteria": [
            item.criterion_id for item in graph.acceptance_criteria
        ],
        "generated_tests": [item.test_id for item in graph.generated_tests],
    }
    for group, identifiers in groups.items():
        for identifier, count in sorted(Counter(identifiers).items()):
            if count > 1:
                add_issue(
                    issues,
                    "DUPLICATE_ID",
                    f"{group}.{identifier}",
                    f"ID '{identifier}' appears {count} times.",
                )


def _check_nodes(
    graph: GameplayGraph,
    variables: Mapping[str, StateVariable],
    nodes: Mapping[str, Any],
    events: Set[str],
    scene_objects: Set[str],
    criteria: Set[str],
    issues: List[ValidationIssue],
) -> None:
    starts = [node for node in graph.nodes if node.kind == NodeKind.START]
    endings = [node for node in graph.nodes if node.kind == NodeKind.ENDING]
    if len(starts) != 1:
        add_issue(
            issues,
            "START_NODE_COUNT",
            "nodes",
            f"Graph requires exactly one start node; found {len(starts)}.",
        )
    if not endings:
        add_issue(issues, "MISSING_ENDING", "nodes", "Graph requires an ending node.")

    for node in graph.nodes:
        location = f"nodes.{node.node_id}"
        if node.kind == NodeKind.INTERACTION and not node.sceneops_ids:
            add_issue(
                issues,
                "INTERACTION_WITHOUT_OBJECT",
                location,
                "Interaction nodes must link to at least one sceneops_id.",
            )
        if node.kind == NodeKind.QUEST and node.quest is None:
            add_issue(issues, "MISSING_QUEST_CONFIG", location, "Quest config is required.")
        if node.kind != NodeKind.QUEST and node.quest is not None:
            add_issue(issues, "UNEXPECTED_QUEST_CONFIG", location, "Only quest nodes may carry quest config.")
        if node.kind == NodeKind.DIALOGUE and node.dialogue is None:
            add_issue(issues, "MISSING_DIALOGUE_CONFIG", location, "Dialogue config is required.")
        if node.kind != NodeKind.DIALOGUE and node.dialogue is not None:
            add_issue(
                issues,
                "UNEXPECTED_DIALOGUE_CONFIG",
                location,
                "Only dialogue nodes may carry dialogue config.",
            )

        for sceneops_id in node.sceneops_ids:
            _check_scene_reference(sceneops_id, scene_objects, location, issues)
        for event_id in node.emitted_event_ids:
            _check_event_reference(event_id, events, location, issues)
        for criterion_id in node.acceptance_criterion_ids:
            if criterion_id not in criteria:
                add_issue(
                    issues,
                    "MISSING_ACCEPTANCE_REFERENCE",
                    location,
                    f"Acceptance criterion '{criterion_id}' is not declared.",
                )
        check_conditions(node.conditions, variables, f"{location}.conditions", issues)
        check_effects(node.effects, variables, f"{location}.effects", issues)

        if node.quest:
            _check_event_reference(
                node.quest.completion_event_id, events, f"{location}.quest", issues
            )
        if node.dialogue:
            _check_scene_reference(
                node.dialogue.speaker_sceneops_id,
                scene_objects,
                f"{location}.dialogue",
                issues,
            )
            for choice in node.dialogue.choices:
                if choice.target_node_id not in nodes:
                    add_issue(
                        issues,
                        "MISSING_NODE_REFERENCE",
                        f"{location}.dialogue.choices.{choice.choice_id}",
                        f"Target node '{choice.target_node_id}' is not declared.",
                    )
                check_conditions(
                    choice.conditions,
                    variables,
                    f"{location}.dialogue.choices.{choice.choice_id}.conditions",
                    issues,
                )


def _check_edges(
    graph: GameplayGraph,
    variables: Mapping[str, StateVariable],
    nodes: Mapping[str, Any],
    events: Set[str],
    issues: List[ValidationIssue],
) -> None:
    for edge in graph.edges:
        location = f"edges.{edge.edge_id}"
        if edge.source_node_id not in nodes:
            add_issue(
                issues,
                "MISSING_NODE_REFERENCE",
                location,
                f"Source node '{edge.source_node_id}' is not declared.",
            )
        if edge.target_node_id not in nodes:
            add_issue(
                issues,
                "MISSING_NODE_REFERENCE",
                location,
                f"Target node '{edge.target_node_id}' is not declared.",
            )
        if edge.event_id:
            _check_event_reference(edge.event_id, events, location, issues)
        for event_id in edge.emitted_event_ids:
            _check_event_reference(event_id, events, location, issues)
        check_conditions(edge.conditions, variables, f"{location}.conditions", issues)
        check_effects(edge.effects, variables, f"{location}.effects", issues)


def _check_relationships(
    graph: GameplayGraph,
    scene_objects: Set[str],
    issues: List[ValidationIssue],
) -> None:
    for relationship in graph.relationships:
        location = f"relationships.{relationship.relationship_id}"
        _check_scene_reference(
            relationship.source_sceneops_id, scene_objects, location, issues
        )
        _check_scene_reference(
            relationship.target_sceneops_id, scene_objects, location, issues
        )


def _check_generated_tests(
    graph: GameplayGraph,
    nodes: Mapping[str, Any],
    criteria: Set[str],
    issues: List[ValidationIssue],
) -> None:
    covered: Set[str] = set()
    mapped: Set[str] = set()
    for node in graph.nodes:
        mapped.update(node.acceptance_criterion_ids)
    for reference in graph.generated_tests:
        location = f"generated_tests.{reference.test_id}"
        for node_id in reference.target_node_ids:
            if node_id not in nodes:
                add_issue(
                    issues,
                    "MISSING_NODE_REFERENCE",
                    location,
                    f"Target node '{node_id}' is not declared.",
                )
        for criterion_id in reference.acceptance_criterion_ids:
            if criterion_id not in criteria:
                add_issue(
                    issues,
                    "MISSING_ACCEPTANCE_REFERENCE",
                    location,
                    f"Acceptance criterion '{criterion_id}' is not declared.",
                )
            else:
                covered.add(criterion_id)

    for criterion_id in sorted(criteria - mapped):
        add_issue(
            issues,
            "UNMAPPED_ACCEPTANCE_CRITERION",
            f"acceptance_criteria.{criterion_id}",
            "Acceptance criterion is not linked to a gameplay node.",
        )
    for criterion_id in sorted(criteria - covered):
        add_issue(
            issues,
            "UNSATISFIED_ACCEPTANCE_CRITERION",
            f"acceptance_criteria.{criterion_id}",
            "Acceptance criterion has no generated test reference.",
        )


def _check_scene_reference(
    sceneops_id: str,
    scene_objects: Set[str],
    location: str,
    issues: List[ValidationIssue],
) -> None:
    if sceneops_id not in scene_objects:
        add_issue(
            issues,
            "MISSING_SCENE_OBJECT_REFERENCE",
            location,
            f"sceneops_id '{sceneops_id}' is not declared by this graph.",
        )


def _check_event_reference(
    event_id: str, events: Set[str], location: str, issues: List[ValidationIssue]
) -> None:
    if event_id not in events:
        add_issue(
            issues,
            "MISSING_EVENT_REFERENCE",
            location,
            f"Event '{event_id}' is not declared.",
        )
