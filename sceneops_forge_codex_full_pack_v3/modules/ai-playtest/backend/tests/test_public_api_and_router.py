from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_support import fixed_clock, load_test_case, make_adapter

import ai_playtest
from ai_playtest import AIPlaytestService, InMemoryPlaytestRepository, create_router
from ai_playtest.schemas import ExecutionMode, RunRequest


class PublicApiAndRouterTests(unittest.TestCase):
    def test_public_entrypoint_exposes_domain_contract_and_no_repository_internals(self):
        expected = {
            "AIPlaytestService",
            "TestCase",
            "Observation",
            "AvailableAction",
            "PlaytestStep",
            "GoalProgress",
            "FailureSignal",
            "EvidenceBundle",
            "Issue",
            "Backpin",
            "RegressionComparison",
            "PlaytestRunnerAdapter",
            "RestoreIssueCommand",
            "EVENT_MODELS",
        }
        self.assertTrue(expected.issubset(set(ai_playtest.__all__)))

    def test_router_contributes_typed_openapi_without_runtime_bootstrap_logic(self):
        service = AIPlaytestService(
            make_adapter("find-my-way-home-before.runtime.json"),
            InMemoryPlaytestRepository(),
            clock=fixed_clock,
        )
        app = FastAPI()
        app.include_router(create_router(service))
        schema = app.openapi()
        paths = schema["paths"]
        self.assertIn("/api/v1/playtests/runs", paths)
        self.assertIn("/api/v1/playtests/runs/{run_id}/cancel", paths)
        self.assertIn("/api/v1/playtests/regressions", paths)
        self.assertIn("/api/v1/playtests/issues/{issue_id}/restore", paths)
        self.assertIn(
            "/api/v1/playtests/issues/{issue_id}/backpin-reviews", paths
        )
        self.assertIn("RunRequest", schema["components"]["schemas"])
        self.assertIn("RegressionComparison", schema["components"]["schemas"])
        self.assertIn("ErrorBody", schema["components"]["schemas"])

    def test_adapter_error_uses_top_level_typed_envelope(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        service = AIPlaytestService(
            adapter, InMemoryPlaytestRepository(), clock=fixed_clock
        )
        app = FastAPI()
        app.include_router(create_router(service))
        client = TestClient(app)
        request = RunRequest(
            run_id="run.api.live-blocked",
            test_case=load_test_case(),
            build=adapter.build,
            execution_mode=ExecutionMode.LIVE,
        )
        response = client.post(
            "/api/v1/playtests/runs",
            json=request.model_dump(mode="json"),
            headers={"x-request-id": "request.api-test"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["code"], "EXECUTION_MODE_UNAVAILABLE")
        self.assertEqual(body["request_id"], "request.api-test")
        self.assertNotIn("detail", body)

    def test_cancel_endpoint_reports_non_running_run(self):
        service = AIPlaytestService(
            make_adapter("find-my-way-home-before.runtime.json"),
            InMemoryPlaytestRepository(),
            clock=fixed_clock,
        )
        app = FastAPI()
        app.include_router(create_router(service))
        response = TestClient(app).post(
            "/api/v1/playtests/runs/run.not-active/cancel"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "not_running")

    def test_backpin_review_identity_comes_from_authenticated_request_state(self):
        adapter = make_adapter("find-my-way-home-before.runtime.json")
        repository = InMemoryPlaytestRepository()
        service = AIPlaytestService(adapter, repository, clock=fixed_clock)
        run = service.run(
            RunRequest(
                run_id="run.api-review",
                test_case=load_test_case(),
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )
        )
        issue = next(item for item in run.issues if item.backpin.status == "resolved")
        app = FastAPI()
        app.include_router(create_router(service))
        client = TestClient(app)
        response = client.post(
            f"/api/v1/playtests/issues/{issue.issue_id}/backpin-reviews",
            json={"decision": "confirm"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTHENTICATED_ACTOR_REQUIRED")

        authenticated_app = FastAPI()

        @authenticated_app.middleware("http")
        async def inject_actor(request, call_next):
            request.state.actor_id = "user.api-reviewer"
            return await call_next(request)

        authenticated_app.include_router(create_router(service))
        response = TestClient(authenticated_app).post(
            f"/api/v1/playtests/issues/{issue.issue_id}/backpin-reviews",
            json={"decision": "confirm"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["backpin"]["reviewed_by"], "user.api-reviewer")


if __name__ == "__main__":
    unittest.main()
