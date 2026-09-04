import unittest
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from observability import (
    CorrelationContext,
    ExecutionMode,
    LogLevel,
    ObservabilityGateway,
    StructuredLogEvent,
)
from observability.router import create_router


class Access:
    def __init__(self, projects=None, producers=None):
        self.projects = set(projects or ["prj_api", "prj_denied"])
        self.producers = set(producers or ["engine-unity"])

    def authorize_project(self, permission_id, project_id):
        if project_id not in self.projects:
            raise HTTPException(status_code=403, detail="project denied")

    def authorize_producer(self, project_id, source_module, source_tool, mode):
        self.authorize_project("observability:write", project_id)
        if source_module not in self.producers:
            raise HTTPException(status_code=403, detail="producer denied")


class ObservabilityRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = ObservabilityGateway()
        app = FastAPI()
        app.include_router(create_router(self.gateway, lambda _permission: lambda: None, Access()))
        self.client = TestClient(app)

    def test_publish_search_and_download(self) -> None:
        event = StructuredLogEvent(
            event_id="log_api",
            emitted_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
            level=LogLevel.INFO,
            source_module="engine-unity",
            source_tool="unity",
            message="mock build complete",
            context=CorrelationContext(
                project_id="prj_api",
                run_id="run_api",
                job_id="job_api",
                correlation_id="corr_api",
                causation_id="cmd_api",
            ),
            fields={"status": "succeeded"},
            mode=ExecutionMode.MOCK,
        )
        published = self.client.post("/api/v1/observability/logs", json=event.model_dump(mode="json"))
        search = self.client.post(
            "/api/v1/observability/logs/search",
            json={"project_id": "prj_api", "limit": 20},
        )
        bundle = self.client.post(
            "/api/v1/observability/diagnostics",
            json={
                "project_id": "prj_api",
                "correlation_id": "corr_api",
            },
        )

        self.assertEqual(201, published.status_code)
        self.assertEqual(1, search.json()["total"])
        self.assertEqual(200, bundle.status_code)
        self.assertEqual("mock", bundle.headers["x-sceneops-execution-mode"])
        self.assertTrue(bundle.headers["content-type"].startswith("application/zip"))

    def test_router_requires_injected_export_permission(self) -> None:
        def permission(permission_id):
            def check():
                if permission_id == "observability:export":
                    raise HTTPException(status_code=403, detail="denied")
            return check

        app = FastAPI()
        app.include_router(create_router(ObservabilityGateway(), permission, Access()))
        client = TestClient(app)
        response = client.post(
            "/api/v1/observability/diagnostics",
            json={
                "project_id": "prj_denied",
            },
        )
        self.assertEqual(403, response.status_code)

    def test_project_and_producer_authorization_are_enforced(self) -> None:
        app = FastAPI()
        app.include_router(
            create_router(
                ObservabilityGateway(),
                lambda _permission: lambda: None,
                Access(projects=["prj_allowed"], producers=["trusted-module"]),
            )
        )
        client = TestClient(app)
        payload = {
            "event_id": "log_denied",
            "emitted_at": "2026-09-04T00:00:00Z",
            "level": "info",
            "source_module": "untrusted-module",
            "message": "attempted injection",
            "context": {
                "project_id": "prj_other",
                "correlation_id": "corr_other",
                "causation_id": "cmd_other",
            },
            "fields": {},
            "artifact_links": [],
            "mode": "mock",
        }
        publish = client.post("/api/v1/observability/logs", json=payload)
        producer_payload = {
            **payload,
            "event_id": "log_producer_denied",
            "context": {
                **payload["context"],
                "project_id": "prj_allowed",
            },
        }
        producer_publish = client.post("/api/v1/observability/logs", json=producer_payload)
        search = client.post(
            "/api/v1/observability/logs/search",
            json={"project_id": "prj_other"},
        )
        self.assertEqual(403, publish.status_code)
        self.assertEqual(403, producer_publish.status_code)
        self.assertEqual(403, search.status_code)


if __name__ == "__main__":
    unittest.main()
