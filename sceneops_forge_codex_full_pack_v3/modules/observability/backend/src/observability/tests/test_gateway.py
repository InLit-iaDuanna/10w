import unittest
from datetime import datetime, timezone

from observability import (
    CorrelationContext,
    CursorExpiredError,
    DuplicateEventConflict,
    ExecutionMode,
    LogLevel,
    LogQuery,
    ObservabilityGateway,
    ProgressEvent,
    ProgressState,
    SearchFieldNotAllowed,
    StructuredLogEvent,
)


NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def context() -> CorrelationContext:
    return CorrelationContext(
        project_id="prj_test",
        run_id="run_test",
        job_id="job_test",
        correlation_id="corr_test",
        causation_id="cmd_test",
    )


def log(event_id: str, message: str = "build complete", level: LogLevel = LogLevel.INFO) -> StructuredLogEvent:
    return StructuredLogEvent(
        event_id=event_id,
        emitted_at=NOW,
        level=level,
        source_module="build-release",
        source_tool="unity",
        worker_id="worker_unity_01",
        message=message,
        context=context(),
        fields={"operation": "build.run", "status": "succeeded", "duration_ms": 12},
        mode=ExecutionMode.MOCK,
    )


class ObservabilityGatewayTests(unittest.TestCase):
    def test_duplicate_delivery_is_idempotent_and_conflict_is_rejected(self) -> None:
        gateway = ObservabilityGateway()
        first = gateway.publish_log(log("log_1"))
        duplicate = gateway.publish_log(log("log_1"))

        self.assertEqual(first.sequence, duplicate.sequence)
        self.assertEqual(1, gateway.query_logs(LogQuery(project_id="prj_test")).total)

        with self.assertRaises(DuplicateEventConflict):
            gateway.publish_log(log("log_1", message="different payload"))

    def test_reconnect_uses_opaque_cursor_without_duplicates(self) -> None:
        gateway = ObservabilityGateway()
        gateway.publish_log(log("log_1"))
        gateway.publish_progress(
            ProgressEvent(
                event_id="progress_1",
                occurred_at=NOW,
                source_module="build-release",
                state=ProgressState.RUNNING,
                progress=0.5,
                message="halfway",
                context=context(),
                fields={"operation": "build.run"},
                mode=ExecutionMode.MOCK,
            )
        )

        first = gateway.events_after("prj_test", None, limit=1)
        second = gateway.events_after("prj_test", first.next_cursor)

        self.assertEqual(["log_1"], [item.event_id for item in first.events])
        self.assertEqual(["progress_1"], [item.event_id for item in second.events])
        self.assertIsInstance(first.next_cursor, str)
        self.assertNotEqual(first.next_cursor, second.next_cursor)

    def test_pruned_cursor_requires_explicit_requery(self) -> None:
        gateway = ObservabilityGateway(max_records=1)
        gateway.publish_log(log("log_1"))
        cursor = gateway.events_after("prj_test", None).next_cursor
        gateway.publish_log(log("log_2"))
        gateway.publish_log(log("log_3"))

        with self.assertRaises(CursorExpiredError):
            gateway.events_after("prj_test", cursor)

    def test_cursor_is_server_issued_and_project_bound(self) -> None:
        gateway = ObservabilityGateway()
        gateway.publish_log(log("log_1"))
        cursor = gateway.events_after("prj_test", None).next_cursor
        with self.assertRaises(ValueError):
            gateway.events_after("prj_test", "caller-crafted-cursor")
        with self.assertRaises(ValueError):
            gateway.events_after("prj_other", cursor)

    def test_retention_evicted_cursor_is_explicitly_expired(self) -> None:
        gateway = ObservabilityGateway(max_records=1)
        cursor = gateway.events_after("prj_test", None).next_cursor
        for _index in range(130):
            gateway.events_after("prj_test", None)
        with self.assertRaises(CursorExpiredError):
            gateway.events_after("prj_test", cursor)
        with self.assertRaises(ValueError):
            gateway.events_after("prj_other", cursor)

    def test_query_correlates_and_searches_allowlisted_fields(self) -> None:
        gateway = ObservabilityGateway()
        stored = gateway.publish_log(log("log_error", "Unity build failed", LogLevel.ERROR))
        gateway.publish_log(log("log_info", "Unity build started", LogLevel.INFO))

        page = gateway.query_logs(
            LogQuery(
                text="failed",
                minimum_level=LogLevel.WARNING,
                project_id="prj_test",
                run_id="run_test",
                job_id="job_test",
                correlation_id="corr_test",
                field_equals={"status": "succeeded"},
            )
        )

        self.assertEqual(["log_error"], [item.event_id for item in page.items])
        self.assertEqual(context(), stored.context)

    def test_unbounded_structured_fields_are_rejected(self) -> None:
        gateway = ObservabilityGateway()
        unsafe = log("log_unsafe").model_copy(update={"fields": {"arbitrary_user_field": "value"}})
        with self.assertRaises(SearchFieldNotAllowed):
            gateway.publish_log(unsafe)

    def test_secret_only_payload_change_is_still_an_id_conflict(self) -> None:
        gateway = ObservabilityGateway()
        first = log("log_secret", message="token=alpha")
        second = log("log_secret", message="token=beta")
        gateway.publish_log(first)
        with self.assertRaises(DuplicateEventConflict):
            gateway.publish_log(second)

    def test_retention_bounds_idempotency_entries(self) -> None:
        gateway = ObservabilityGateway(max_records=1)
        gateway.publish_log(log("log_evicted", message="first"))
        gateway.publish_log(log("log_current"))
        replacement = gateway.publish_log(log("log_evicted", message="replacement"))
        self.assertEqual("replacement", replacement.message)


if __name__ == "__main__":
    unittest.main()
