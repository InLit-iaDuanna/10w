from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .models import (
    Condition,
    ConditionOperator,
    Effect,
    EffectOperation,
    GameplayEdge,
    GameplayGraph,
    NodeKind,
)
from .validation import validate_gameplay_graph


class InvalidRuntimeGraph(ValueError):
    pass


class TransitionUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeStep:
    previous_node_id: str
    current_node_id: str
    emitted_event_ids: List[str]
    state: Dict[str, Any]


class GameplayGraphRuntime:
    """Small deterministic interpreter used for behavior tests and previews."""

    def __init__(self, graph: GameplayGraph):
        report = validate_gameplay_graph(graph)
        if not report.valid:
            codes = ", ".join(issue.code for issue in report.issues)
            raise InvalidRuntimeGraph(f"Gameplay graph is invalid: {codes}")
        self.graph = graph
        self._nodes = {node.node_id: node for node in graph.nodes}
        self._edges = sorted(graph.edges, key=lambda edge: edge.edge_id)
        start = next(node for node in graph.nodes if node.kind == NodeKind.START)
        self.current_node_id = start.node_id
        self.state: Dict[str, Any] = {
            variable.variable_id: _clone_value(variable.initial_value)
            for variable in graph.state_variables
        }
        self.event_log: List[str] = []
        self.event_log.extend(self._enter_node(start.node_id))

    def available_transitions(
        self, event_id: Optional[str] = None
    ) -> List[GameplayEdge]:
        return [
            edge
            for edge in self._edges
            if edge.source_node_id == self.current_node_id
            and (edge.event_id is None or edge.event_id == event_id)
            and all(_evaluate(condition, self.state) for condition in edge.conditions)
        ]

    def step(
        self, target_node_id: str, event_id: Optional[str] = None
    ) -> RuntimeStep:
        candidates = [
            edge
            for edge in self.available_transitions(event_id)
            if edge.target_node_id == target_node_id
        ]
        if len(candidates) != 1:
            raise TransitionUnavailable(
                f"Expected one transition from '{self.current_node_id}' to "
                f"'{target_node_id}', found {len(candidates)}."
            )
        edge = candidates[0]
        previous_node_id = self.current_node_id
        for effect in edge.effects:
            _apply(effect, self.state)
        emitted = list(edge.emitted_event_ids)
        self.current_node_id = target_node_id
        emitted.extend(self._enter_node(target_node_id))
        self.event_log.extend(emitted)
        return RuntimeStep(
            previous_node_id=previous_node_id,
            current_node_id=self.current_node_id,
            emitted_event_ids=emitted,
            state={key: _clone_value(value) for key, value in self.state.items()},
        )

    def _enter_node(self, node_id: str) -> List[str]:
        node = self._nodes[node_id]
        if not all(_evaluate(condition, self.state) for condition in node.conditions):
            raise TransitionUnavailable(f"Node '{node_id}' conditions are not satisfied.")
        for effect in node.effects:
            _apply(effect, self.state)
        return list(node.emitted_event_ids)


def _evaluate(condition: Condition, state: Dict[str, Any]) -> bool:
    current = state[condition.variable_id]
    expected = condition.value
    operations = {
        ConditionOperator.EQUALS: lambda: current == expected,
        ConditionOperator.NOT_EQUALS: lambda: current != expected,
        ConditionOperator.GREATER_THAN: lambda: current > expected,
        ConditionOperator.GREATER_THAN_OR_EQUAL: lambda: current >= expected,
        ConditionOperator.LESS_THAN: lambda: current < expected,
        ConditionOperator.LESS_THAN_OR_EQUAL: lambda: current <= expected,
        ConditionOperator.CONTAINS: lambda: expected in current,
        ConditionOperator.NOT_CONTAINS: lambda: expected not in current,
    }
    return operations[condition.operator]()


def _apply(effect: Effect, state: Dict[str, Any]) -> None:
    operation = effect.operation
    variable_id = effect.variable_id
    if operation == EffectOperation.SET:
        state[variable_id] = _clone_value(effect.value)
    elif operation == EffectOperation.INCREMENT:
        state[variable_id] += effect.value
    elif operation == EffectOperation.DECREMENT:
        state[variable_id] -= effect.value
    elif operation == EffectOperation.ADD:
        if effect.value not in state[variable_id]:
            state[variable_id].append(effect.value)
            state[variable_id].sort()
    elif operation == EffectOperation.REMOVE:
        if effect.value in state[variable_id]:
            state[variable_id].remove(effect.value)
    elif operation == EffectOperation.TOGGLE:
        state[variable_id] = not state[variable_id]


def _clone_value(value: Any) -> Any:
    return list(value) if isinstance(value, list) else value
