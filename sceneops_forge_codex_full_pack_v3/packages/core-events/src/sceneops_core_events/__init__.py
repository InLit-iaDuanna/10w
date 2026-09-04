"""Public SceneOps Forge core-event entrypoint."""

from .references import (
    EVENT_REFERENCE_PATTERN,
    EventReference,
    EventReferenceError,
    ensure_contiguous_versions,
)
from .schema import EventSchemaDescriptor, EventSchemaError, validate_event_evolution

__all__ = [
    "EVENT_REFERENCE_PATTERN",
    "EventReference",
    "EventReferenceError",
    "EventSchemaDescriptor",
    "EventSchemaError",
    "ensure_contiguous_versions",
    "validate_event_evolution",
]
