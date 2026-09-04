import json
import unittest
from pathlib import Path

from sceneops_core_events import (
    EventReference,
    EventReferenceError,
    EventSchemaDescriptor,
    EventSchemaError,
    ensure_contiguous_versions,
    validate_event_evolution,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class EventContractTests(unittest.TestCase):
    def setUp(self):
        self.v1_payload = json.loads(
            (PACKAGE_ROOT / "fixtures" / "fixture.completed.v1.json").read_text()
        )

    def test_event_reference_parses_version(self):
        reference = EventReference.parse("fixture.completed@12")
        self.assertEqual(reference.event_type, "fixture.completed")
        self.assertEqual(reference.version, 12)

    def test_invalid_event_reference_fails(self):
        with self.assertRaises(EventReferenceError):
            EventReference.parse("fixture.completed")

    def test_event_versions_must_be_contiguous(self):
        with self.assertRaisesRegex(EventReferenceError, "contiguous"):
            ensure_contiguous_versions(["fixture.completed@1", "fixture.completed@3"])

    def test_published_version_is_immutable(self):
        previous = EventSchemaDescriptor.from_mapping(self.v1_payload)
        changed = json.loads(json.dumps(self.v1_payload))
        changed["properties"]["new_field"] = {"type": "string"}
        candidate = EventSchemaDescriptor.from_mapping(changed)
        with self.assertRaises(EventSchemaError) as caught:
            validate_event_evolution(previous, candidate)
        self.assertEqual(caught.exception.code, "EVENT_SCHEMA_CHANGED_WITHOUT_VERSION")

    def test_changed_schema_is_allowed_at_next_version(self):
        previous = EventSchemaDescriptor.from_mapping(self.v1_payload)
        changed = json.loads(json.dumps(self.v1_payload))
        changed["x-event-version"] = 2
        changed["properties"]["new_field"] = {"type": "string"}
        candidate = EventSchemaDescriptor.from_mapping(changed)
        validate_event_evolution(previous, candidate)

    def test_version_gap_fails(self):
        previous = EventSchemaDescriptor.from_mapping(self.v1_payload)
        changed = json.loads(json.dumps(self.v1_payload))
        changed["x-event-version"] = 3
        candidate = EventSchemaDescriptor.from_mapping(changed)
        with self.assertRaises(EventSchemaError) as caught:
            validate_event_evolution(previous, candidate)
        self.assertEqual(caught.exception.code, "EVENT_VERSION_GAP")


if __name__ == "__main__":
    unittest.main()
