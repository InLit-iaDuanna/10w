import unittest
from datetime import datetime, timezone

from observability import (
    CorrelationContext,
    ExecutionMode,
    LogLevel,
    ObservabilityGateway,
    REDACTED,
    REDACTED_PATH,
    StructuredLogEvent,
)


class RedactionTests(unittest.TestCase):
    def test_ingress_redacts_secrets_urls_and_local_paths(self) -> None:
        context = CorrelationContext(
            project_id="prj_redaction",
            run_id="run_redaction",
            job_id="job_redaction",
            correlation_id="corr_must_survive",
            causation_id="cmd_must_survive",
        )
        event = StructuredLogEvent(
            event_id="log_redaction",
            emitted_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            level=LogLevel.ERROR,
            source_module="engine-unity",
            source_tool="unity",
            message=(
                "Bearer abc.def password=hunter2 "
                "https://alice:secret@example.test/build?token=raw&view=short "
                "https://user:pass@example.test:bad/path?api_key=url-secret "
                "AWS_SECRET_ACCESS_KEY=\"quoted secret value\" "
                "https://example.test/view#access_token=fragment-secret "
                "https://host.test/Users/alice/x?next=/private/tmp/key&value=Bearer%20abc.def "
                "cwd:/Users/alice/private/project file:/private/tmp/secret "
                "signature=raw-signature session_key=session-secret "
                "/secret /Users/alice/private/project/scene.unity "
                "C:\\secret C:\\Users\\alice\\secret\\file.txt"
            ),
            context=context,
            fields={
                "code": "BUILD_FAILED",
                "status": "failed",
                "operation": "build.run",
            },
            mode=ExecutionMode.MOCK,
        )
        unsafe_fields = event.model_copy(
            update={
                "fields": {
                    "code": "BUILD_FAILED",
                    "status": "failed",
                    "operation": "build.run",
                    "artifact_id": {
                        "api_token": "raw-token",
                        "project_path": "/private/tmp/secret/project",
                    },
                }
            }
        )

        stored = ObservabilityGateway().publish_log(unsafe_fields)
        serialized = stored.model_dump_json()

        for secret in (
            "abc.def",
            "hunter2",
            "alice:secret",
            "url-secret",
            "quoted secret value",
            "fragment-secret",
            "raw-token",
            "raw-signature",
            "session-secret",
            "/Users/alice",
            "/private/tmp",
            "C:\\Users",
            "C:\\secret",
            "view=short",
            "next=%2Fprivate",
        ):
            self.assertNotIn(secret, serialized)
        self.assertIn(REDACTED, serialized)
        self.assertIn(REDACTED_PATH, serialized)
        self.assertEqual("corr_must_survive", stored.context.correlation_id)
        self.assertEqual("cmd_must_survive", stored.context.causation_id)


if __name__ == "__main__":
    unittest.main()
