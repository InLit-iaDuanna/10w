from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from .models import (
    GameplayGraph,
    GameplayGraphDiff,
    GraphDiffEntry,
)


CURRENT_GAMEPLAY_GRAPH_SCHEMA_VERSION = 1


class UnsupportedGraphVersion(ValueError):
    pass


class InvalidGraphVersionTransition(ValueError):
    pass


def serialize_gameplay_graph(graph: GameplayGraph) -> str:
    return json.dumps(
        graph.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def deserialize_gameplay_graph(document: str) -> GameplayGraph:
    payload = json.loads(document)
    version = payload.get("schema_version") if isinstance(payload, dict) else None
    if version != CURRENT_GAMEPLAY_GRAPH_SCHEMA_VERSION:
        raise UnsupportedGraphVersion(
            f"Unsupported gameplay graph schema_version: {version!r}"
        )
    return GameplayGraph.model_validate(payload)


def diff_gameplay_graphs(
    base: GameplayGraph, proposed: GameplayGraph
) -> GameplayGraphDiff:
    if proposed.graph_id != base.graph_id:
        raise InvalidGraphVersionTransition("Cannot diff different graph IDs.")
    if proposed.version <= base.version:
        raise InvalidGraphVersionTransition(
            "Proposed graph version must be greater than the base version."
        )

    entries: List[GraphDiffEntry] = []
    collections = (
        ("state_variable", "variable_id", base.state_variables, proposed.state_variables),
        ("event", "event_id", base.events, proposed.events),
        ("scene_object", "sceneops_id", base.scene_objects, proposed.scene_objects),
        ("node", "node_id", base.nodes, proposed.nodes),
        ("edge", "edge_id", base.edges, proposed.edges),
        (
            "relationship",
            "relationship_id",
            base.relationships,
            proposed.relationships,
        ),
        (
            "acceptance_criterion",
            "criterion_id",
            base.acceptance_criteria,
            proposed.acceptance_criteria,
        ),
        ("generated_test", "test_id", base.generated_tests, proposed.generated_tests),
    )
    for entity_type, identity_field, previous, current in collections:
        entries.extend(
            _diff_collection(entity_type, identity_field, previous, current)
        )
    return GameplayGraphDiff(
        graph_id=base.graph_id,
        base_version=base.version,
        proposed_version=proposed.version,
        entries=sorted(
            entries,
            key=lambda entry: (entry.entity_type, entry.entity_id, entry.change),
        ),
    )


def _diff_collection(
    entity_type: str,
    identity_field: str,
    previous: Iterable[Any],
    proposed: Iterable[Any],
) -> List[GraphDiffEntry]:
    previous_by_id = _index(identity_field, previous)
    proposed_by_id = _index(identity_field, proposed)
    entries: List[GraphDiffEntry] = []
    for entity_id in sorted(set(previous_by_id) | set(proposed_by_id)):
        old = previous_by_id.get(entity_id)
        new = proposed_by_id.get(entity_id)
        if old is None:
            entries.append(
                GraphDiffEntry(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    change="added",
                    proposed=new,
                )
            )
        elif new is None:
            entries.append(
                GraphDiffEntry(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    change="removed",
                    previous=old,
                )
            )
        elif old != new:
            entries.append(
                GraphDiffEntry(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    change="modified",
                    previous=old,
                    proposed=new,
                )
            )
    return entries


def _index(identity_field: str, values: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for value in values:
        payload = value.model_dump(mode="json")
        result[str(payload[identity_field])] = payload
    return result
