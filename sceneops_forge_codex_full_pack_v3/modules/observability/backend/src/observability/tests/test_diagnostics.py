import io
import json
import unittest
import zipfile
from datetime import datetime, timezone

from observability import (
    CorrelationContext,
    DiagnosticBundleRequest,
    DiagnosticBundleService,
    ExecutionMode,
    LogLevel,
    StructuredLogEvent,
)


class DiagnosticBundleTests(unittest.TestCase):
    def test_bundle_is_deterministic_scoped_and_redacted(self) -> None:
        event = StructuredLogEvent(
            event_id="log_bundle",
            emitted_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            level=LogLevel.ERROR,
            source_module="asset-factory",
            source_tool="blender",
            message="token=secret-value at /Users/alice/game/file.blend",
            context=CorrelationContext(
                project_id="prj_bundle",
                run_id="run_bundle",
                job_id="job_bundle",
                correlation_id="corr_bundle",
                causation_id="cmd_bundle",
            ),
            fields={"code": "EXPORT_FAILED", "operation": "asset.export"},
            mode=ExecutionMode.MOCK,
        )
        request = DiagnosticBundleRequest(
            project_id="prj_bundle",
            correlation_id="corr_bundle",
        )
        service = DiagnosticBundleService(clock=lambda: datetime(2026, 9, 4, tzinfo=timezone.utc))

        health = [{"integration_id": "blender", "token": "health-secret"}]
        first = service.create(request, [event], health_snapshots=health)
        second = service.create(request, [event], health_snapshots=health)

        self.assertEqual(first.content, second.content)
        self.assertEqual("mock", first.mode.value)
        with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
            self.assertEqual(["health.json", "logs.jsonl", "manifest.json"], sorted(archive.namelist()))
            extracted = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
            manifest = json.loads(archive.read("manifest.json"))
        self.assertNotIn("secret-value", extracted)
        self.assertNotIn("health-secret", extracted)
        self.assertNotIn("/Users/alice", extracted)
        self.assertEqual("mock", manifest["execution_mode"])
        self.assertTrue(manifest["redaction"]["applied"])

    def test_empty_bundle_cannot_claim_live_execution(self) -> None:
        request = DiagnosticBundleRequest(project_id="prj_bundle")
        service = DiagnosticBundleService(clock=lambda: datetime(2026, 9, 4, tzinfo=timezone.utc))
        result = service.create(request, [])
        self.assertEqual(ExecutionMode.BLOCKED, result.mode)


if __name__ == "__main__":
    unittest.main()
