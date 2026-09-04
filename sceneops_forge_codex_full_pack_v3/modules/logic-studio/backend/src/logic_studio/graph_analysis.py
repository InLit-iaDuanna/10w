from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Set

from .models import GameplayGraph, NodeKind, ValidationIssue
from .validation_support import add_issue


def check_reachability(
    graph: GameplayGraph,
    nodes: Mapping[str, Any],
    issues: List[ValidationIssue],
) -> None:
    starts = sorted(node.node_id for node in graph.nodes if node.kind == NodeKind.START)
    endings = {node.node_id for node in graph.nodes if node.kind == NodeKind.ENDING}
    adjacency: Dict[str, Set[str]] = {node_id: set() for node_id in nodes}
    reverse: Dict[str, Set[str]] = {node_id: set() for node_id in nodes}
    for edge in graph.edges:
        if edge.source_node_id in nodes and edge.target_node_id in nodes:
            adjacency[edge.source_node_id].add(edge.target_node_id)
            reverse[edge.target_node_id].add(edge.source_node_id)

    reachable = _walk(starts, adjacency)
    can_reach_ending = _walk(sorted(endings), reverse)
    for node_id in sorted(set(nodes) - reachable):
        add_issue(
            issues,
            "UNREACHABLE_NODE",
            f"nodes.{node_id}",
            "Node cannot be reached from the start node.",
        )

    cyclic_without_exit: Set[str] = set()
    for component in _strongly_connected_components(adjacency):
        has_cycle = len(component) > 1 or any(
            node_id in adjacency[node_id] for node_id in component
        )
        if has_cycle and component.isdisjoint(can_reach_ending):
            cyclic_without_exit.update(component)
            add_issue(
                issues,
                "CYCLE_WITHOUT_EXIT",
                "nodes." + ",".join(sorted(component)),
                "Cycle has no path to an ending node.",
            )

    for node_id in sorted(reachable - can_reach_ending - cyclic_without_exit):
        add_issue(
            issues,
            "DEAD_BRANCH",
            f"nodes.{node_id}",
            "Reachable branch has no path to an ending node.",
        )


def _walk(starts: Iterable[str], adjacency: Mapping[str, Set[str]]) -> Set[str]:
    visited: Set[str] = set()
    queue = deque(starts)
    while queue:
        node_id = queue.popleft()
        if node_id in visited or node_id not in adjacency:
            continue
        visited.add(node_id)
        queue.extend(sorted(adjacency[node_id] - visited))
    return visited


def _strongly_connected_components(
    adjacency: Mapping[str, Set[str]],
) -> List[Set[str]]:
    index = 0
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    stack: List[str] = []
    on_stack: Set[str] = set()
    components: List[Set[str]] = []

    def visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for target_id in sorted(adjacency[node_id]):
            if target_id not in indices:
                visit(target_id)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target_id])
            elif target_id in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target_id])

        if lowlinks[node_id] == indices[node_id]:
            component: Set[str] = set()
            while stack:
                target_id = stack.pop()
                on_stack.remove(target_id)
                component.add(target_id)
                if target_id == node_id:
                    break
            components.append(component)

    for node_id in sorted(adjacency):
        if node_id not in indices:
            visit(node_id)
    return components
