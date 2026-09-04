"""Compatibility rules for append-only, versioned event payload schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .references import EventReference


class EventSchemaError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EventSchemaDescriptor:
    reference: EventReference
    payload_schema: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EventSchemaDescriptor":
        event_type = value.get("x-event-type")
        version = value.get("x-event-version")
        if not isinstance(event_type, str) or not isinstance(version, int):
            raise EventSchemaError(
                "EVENT_SCHEMA_METADATA_INVALID",
                "event schema requires x-event-type and integer x-event-version",
            )
        reference = EventReference.parse(f"{event_type}@{version}")
        if value.get("type") != "object":
            raise EventSchemaError(
                "EVENT_PAYLOAD_NOT_OBJECT", "event payload schema type must be object"
            )
        return cls(reference=reference, payload_schema=value)


def _canonical(schema: Mapping[str, Any]) -> str:
    return json.dumps(schema, separators=(",", ":"), sort_keys=True)


def validate_event_evolution(
    previous: EventSchemaDescriptor, candidate: EventSchemaDescriptor
) -> None:
    """Enforce immutability within a version and sequential version changes.

    A schema may make a breaking or additive change only under the next event
    version. Published versions are immutable, which makes compatibility
    behavior explicit instead of attempting to infer semantic intent.
    """

    if previous.reference.event_type != candidate.reference.event_type:
        raise EventSchemaError(
            "EVENT_TYPE_CHANGED", "event evolution must retain the event type"
        )
    previous_version = previous.reference.version
    candidate_version = candidate.reference.version
    if candidate_version < previous_version:
        raise EventSchemaError(
            "EVENT_VERSION_REGRESSED", "candidate event version cannot decrease"
        )
    if candidate_version == previous_version:
        if _canonical(previous.payload_schema) != _canonical(candidate.payload_schema):
            raise EventSchemaError(
                "EVENT_SCHEMA_CHANGED_WITHOUT_VERSION",
                "published event schema changed without a new version",
            )
        return
    if candidate_version != previous_version + 1:
        raise EventSchemaError(
            "EVENT_VERSION_GAP",
            f"event version must advance by one from {previous_version}",
        )
