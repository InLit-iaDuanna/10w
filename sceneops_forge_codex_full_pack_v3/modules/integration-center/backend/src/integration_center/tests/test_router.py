import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from observability import CorrelationContext, ExecutionMode, ObservabilityGateway

from integration_center import (
    ActivityState,
    AuthorizationState,
    AvailabilityState,
    CapabilityReport,
    ConnectionState,
    ExecutionEvidence,
    HealthProbe,
    InMemoryRecoveryLedger,
    InMemoryRecoveryRepository,
    IntegrationCenterService,
    IntegrationDefinition,
    IntegrationGateway,
    JobState,
    QueueSnapshot,
    ReconciliationResult,
    ReconciliationState,
    RecoveryCoordinator,
    RecoveryJob,
    RetrySafety,
    SideEffectState,
)
from integration_center.router import create_router


NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
CONTEXT = CorrelationContext(
    project_id="prj_api",
    run_id="run_api",
    job_id="job_api",
    correlation_id="corr_api",
    causation_id="cmd_api",
)


class Adapter:
    integration_id = "unity"

    def health_check(self, context):
        evidence = ExecutionEvidence(mode=ExecutionMode.MOCK, observed_at=NOW)
        return HealthProbe(
            integration_id="unity",
            display_name="Unity",
            connection=ConnectionState.CONNECTED,
            authorization=AuthorizationState.AUTHORIZED,
            availability=AvailabilityState.AVAILABLE,
            activity=ActivityState.IDLE,
            observed_at=NOW,
            expires_at=NOW + timedelta(days=1),
            last_seen_at=NOW,
            tool_version="6000.0.23",
            adapter_version="0.1.0",
            queue=QueueSnapshot(depth=0, running=0),
            evidence=evidence,
        )

    def capability_report(self, context):
        evidence = ExecutionEvidence(mode=ExecutionMode.MOCK, observed_at=NOW)
        return CapabilityReport(
            integration_id="unity",
            tool_version="6000.0.23",
            adapter_version="0.1.0",
            observed_at=NOW,
            capability_ids=["build.run"],
            allowlisted_command_ids=["unity.build.run"],
            evidence=evidence,
        )


class Workers:
    def list_workers(self, project_id):
        return []


class Controller:
    def __init__(self):
        self.retry_calls = 0

    def request_cancel(self, job, context, idempotency_key):
        pass

    def reconcile_operation(self, job, context):
        return ReconciliationResult(ReconciliationState.NOT_FOUND)

    def retry(self, job, context, attempt_id, skip_step_ids, idempotency_key):
        self.retry_calls += 1

    def resume(self, job, context, attempt_id, resume_token, skip_step_ids, idempotency_key):
        pass


class IntegrationCenterRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        gateway.register(Adapter())
        service = IntegrationCenterService(gateway, ObservabilityGateway(), Workers())
        repository = InMemoryRecoveryRepository()
        repository.put(
            RecoveryJob(
                job_id="job_api",
                integration_id="unity",
                operation_id="op_api",
                attempt_id="attempt_1",
                state=JobState.FAILED,
                retry_safety=RetrySafety.IDEMPOTENT,
                side_effect_state=SideEffectState.NONE,
                completed_step_ids=("scan",),
                resume_token="resume_api",
                mode=ExecutionMode.LIVE,
                context=CONTEXT,
            )
        )
        self.controller = Controller()
        recovery = RecoveryCoordinator(repository, self.controller, InMemoryRecoveryLedger())
        app = FastAPI()
        app.include_router(
            create_router(
                service,
                recovery,
                lambda _permission: lambda: None,
                lambda _permission, _project_id: None,
            )
        )
        self.app = app
        self.client = TestClient(app)

    def test_health_and_recovery_api_preserve_context_and_mode(self) -> None:
        query = {
            "project_id": "prj_api",
            "run_id": "run_api",
            "job_id": "job_api",
            "correlation_id": "corr_api",
            "causation_id": "cmd_api",
        }
        health = self.client.get("/api/v1/integration-center/integrations", params=query)
        recovery_payload = {
            "context": {
                "project_id": "prj_api",
                "run_id": "run_api",
                "job_id": "job_api",
                "correlation_id": "corr_api",
                "causation_id": "cmd_retry_api"
            },
            "idempotency_key": "retry_api_key",
            "attempt_id": "attempt_2"
        }
        retry = self.client.post("/api/v1/integration-center/jobs/job_api/retry", json=recovery_payload)
        duplicate = self.client.post("/api/v1/integration-center/jobs/job_api/retry", json=recovery_payload)

        self.assertEqual(200, health.status_code)
        self.assertEqual("mock", health.json()[0]["evidence"]["mode"])
        self.assertFalse(health.json()[0]["live_actions_enabled"])
        self.assertEqual(200, retry.status_code)
        self.assertEqual("corr_api", retry.json()["context"]["correlation_id"])
        self.assertEqual("cmd_retry_api", retry.json()["context"]["causation_id"])
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(1, self.controller.retry_calls)

    def test_openapi_exposes_typed_health_and_recovery_routes(self) -> None:
        schema = self.app.openapi()
        paths = schema["paths"]
        self.assertIn("/api/v1/integration-center/integrations", paths)
        self.assertIn("/api/v1/integration-center/jobs/{job_id}/retry", paths)
        self.assertIn("IntegrationHealthSnapshot", schema["components"]["schemas"])
        self.assertIn("RecoveryResult", schema["components"]["schemas"])

    def test_job_control_route_requires_injected_permission(self) -> None:
        gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        gateway.register(Adapter())
        service = IntegrationCenterService(gateway, ObservabilityGateway(), Workers())
        repository = InMemoryRecoveryRepository()
        controller = Controller()
        recovery = RecoveryCoordinator(repository, controller, InMemoryRecoveryLedger())

        def permission(permission_id):
            def check():
                if permission_id == "job:operate":
                    raise HTTPException(status_code=403, detail="denied")
            return check

        app = FastAPI()
        app.include_router(
            create_router(
                service,
                recovery,
                permission,
                lambda _permission, _project_id: None,
            )
        )
        response = TestClient(app).post(
            "/api/v1/integration-center/jobs/job_api/retry",
            json={
                "context": CONTEXT.model_dump(mode="json"),
                "idempotency_key": "denied_key",
                "attempt_id": "attempt_2",
            },
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual(0, controller.retry_calls)

    def test_project_authorizer_cannot_be_bypassed_by_query_context(self) -> None:
        gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        gateway.register(Adapter())
        service = IntegrationCenterService(gateway, ObservabilityGateway(), Workers())
        recovery = RecoveryCoordinator(
            InMemoryRecoveryRepository(),
            Controller(),
            InMemoryRecoveryLedger(),
        )

        def authorize_project(permission_id, project_id):
            if project_id != "prj_allowed":
                raise HTTPException(status_code=403, detail="project denied")

        app = FastAPI()
        app.include_router(
            create_router(
                service,
                recovery,
                lambda _permission: lambda: None,
                authorize_project,
            )
        )
        response = TestClient(app).get(
            "/api/v1/integration-center/integrations",
            params={
                "project_id": "prj_other",
                "correlation_id": "corr_other",
                "causation_id": "cmd_other",
            },
        )
        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
