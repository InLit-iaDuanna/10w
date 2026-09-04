from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from sceneops_production_planner.fixtures import (
    StaticExecutionContextProvider,
    StaticFeatureSpecProvider,
    UnavailableApprovalProvider,
    UnavailableRunEvidenceProvider,
    key_door_snapshot,
)
from sceneops_production_planner.repository import InMemoryProductionPlanRepository
from sceneops_production_planner.router import create_app
from sceneops_production_planner.service import ProductionPlannerService
from sceneops_production_planner.tests.support import create_context, create_request


MODULE_ROOT = Path(__file__).resolve().parents[4]


class ApiAndContractTests(unittest.TestCase):
    def test_api_route_delegates_to_service(self) -> None:
        snapshot = key_door_snapshot()
        service = ProductionPlannerService(
            InMemoryProductionPlanRepository(),
            StaticFeatureSpecProvider([snapshot]),
            UnavailableRunEvidenceProvider(),
            UnavailableApprovalProvider(),
        )
        client = TestClient(create_app(service, StaticExecutionContextProvider(create_context())))
        response = client.post(
            "/v1/production-planner/commands/production.plan.create",
            json=create_request(snapshot).model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])
        self.assertEqual(response.json()["plan"]["status"], "draft_unconfirmed")
        self.assertEqual(len(response.json()["graph"]["nodes"]), 12)

    def test_network_body_cannot_assert_core_actor_or_execution_mode(self) -> None:
        snapshot = key_door_snapshot()
        service = ProductionPlannerService(
            InMemoryProductionPlanRepository(),
            StaticFeatureSpecProvider([snapshot]),
            UnavailableRunEvidenceProvider(),
            UnavailableApprovalProvider(),
        )
        client = TestClient(create_app(service, StaticExecutionContextProvider(create_context())))
        payload = create_request(snapshot).model_dump(mode="json")
        payload.update({"execution_mode": "live", "ai_initiated": False, "actor_id": "user:spoofed"})
        response = client.post(
            "/v1/production-planner/commands/production.plan.create",
            json=payload,
        )
        self.assertEqual(response.status_code, 422)

    def test_default_api_truthfully_reports_blocked_core_context(self) -> None:
        snapshot = key_door_snapshot()
        client = TestClient(create_app())
        response = client.post(
            "/v1/production-planner/commands/production.plan.create",
            json=create_request(snapshot).model_dump(mode="json"),
            headers={"x-request-id": "request:test-blocked"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "CORE_CONTEXT_UNAVAILABLE")
        self.assertEqual(response.json()["details"]["mode"], "blocked")
        self.assertEqual(response.json()["request_id"], "request:test-blocked")

    def test_api_reports_blocked_feature_source_after_trusted_context(self) -> None:
        snapshot = key_door_snapshot()
        client = TestClient(create_app(contexts=StaticExecutionContextProvider(create_context())))
        response = client.post(
            "/v1/production-planner/commands/production.plan.create",
            json=create_request(snapshot).model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "FEATURE_SOURCE_UNAVAILABLE")
        self.assertEqual(response.json()["details"]["mode"], "blocked")

    def test_manifest_and_public_entrypoints_are_compliant(self) -> None:
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "production-planner")
        self.assertEqual(manifest["requires"]["modules"], ["core-kernel", "module-runtime", "design-room"])
        self.assertEqual(manifest["requires"]["integrations"], [])
        self.assertEqual(manifest["contributes"]["editors"], [])
        self.assertEqual(manifest["contributes"]["commands"], [])
        self.assertTrue((MODULE_ROOT / "frontend/src/index.ts").is_file())
        self.assertTrue((MODULE_ROOT / "backend/src/sceneops_production_planner/__init__.py").is_file())

    def test_generated_contracts_are_current(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(MODULE_ROOT / "backend/src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            ["python3", "backend/scripts/export_contracts.py", "--check"],
            cwd=MODULE_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
