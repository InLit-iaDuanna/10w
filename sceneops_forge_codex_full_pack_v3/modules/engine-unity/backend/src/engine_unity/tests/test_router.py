from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine_unity.router import create_router
from engine_unity.service import UnityEngineService

from engine_unity.tests.support import adapter, context, request
from engine_unity.contracts import CommandName


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        application = FastAPI()
        application.include_router(create_router(UnityEngineService(adapter()), lambda: context()))
        self.client = TestClient(application)

    def test_capability_route_exposes_fixed_allowlist(self) -> None:
        response = self.client.get("/api/modules/engine-unity/capabilities")
        self.assertEqual(200, response.status_code)
        self.assertEqual(16, len(response.json()["command_allowlist"]))
        self.assertFalse(response.json()["arbitrary_csharp_execution"])

    def test_execute_route_returns_truthful_mock_result(self) -> None:
        command = request(CommandName.HEALTH)
        response = self.client.post(
            "/api/modules/engine-unity/commands/execute",
            json=command.model_dump(mode="json"),
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("succeeded", response.json()["status"])
        self.assertEqual("mock", response.json()["mode"])

    def test_preview_route_returns_structured_path_error(self) -> None:
        command = request(CommandName.HEALTH).model_copy(
            update={"project_root": "/tmp/not-configured"}
        )
        response = self.client.post(
            "/api/modules/engine-unity/commands/preview",
            json=command.model_dump(mode="json"),
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("UNITY_PATH_OUTSIDE_PROJECT", response.json()["code"])


if __name__ == "__main__":
    unittest.main()
