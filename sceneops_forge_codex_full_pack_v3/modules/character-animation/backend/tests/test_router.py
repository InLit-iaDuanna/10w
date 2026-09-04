import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sceneops_character_animation.adapter import DeterministicMockCharacterToolAdapter
from sceneops_character_animation.fixtures import fixed_preview_camera, remember_home_bundle
from sceneops_character_animation.operation_models import PreviewCaptureRequest
from sceneops_character_animation.router import create_router
from sceneops_character_animation.service import CharacterAnimationService


def client_for(service=None):
    app = FastAPI()
    app.include_router(create_router(service))
    return TestClient(app)


class RouterTests(unittest.TestCase):
    def test_offline_preview_returns_flat_structured_error(self):
        request = PreviewCaptureRequest(
            request_id="req_router_offline",
            character=remember_home_bundle().character,
            rig=remember_home_bundle().rig,
            clip=remember_home_bundle().clips[0],
            camera=fixed_preview_camera(),
        )
        response = client_for().post(
            "/api/modules/character-animation/previews/capture",
            json=request.model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "INTEGRATION_OFFLINE")
        self.assertEqual(response.json()["request_id"], "req_router_offline")
        self.assertTrue(response.json()["retryable"])

    def test_mock_preview_route_returns_mock_not_live(self):
        service = CharacterAnimationService(adapter=DeterministicMockCharacterToolAdapter())
        request = PreviewCaptureRequest(
            request_id="req_router_mock",
            character=remember_home_bundle().character,
            rig=remember_home_bundle().rig,
            clip=remember_home_bundle().clips[0],
            camera=fixed_preview_camera(),
        )
        response = client_for(service).post(
            "/api/modules/character-animation/previews/capture",
            json=request.model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["execution_mode"], "mock")

    def test_integration_route_exposes_imported_path_and_blocked_automatic_rigging(self):
        response = client_for().get("/api/modules/character-animation/integrations")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["imported_character_path_available"])
        auto = next(item for item in response.json()["integrations"] if item["integration_id"] == "automatic-rigging")
        self.assertEqual(auto["mode"], "blocked")

    def test_schema_failure_uses_module_error_contract(self):
        response = client_for().post(
            "/api/modules/character-animation/previews/capture",
            json={"request_id": "req_invalid", "timeout_seconds": -1},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "REQUEST_VALIDATION_FAILED")
        self.assertEqual(response.json()["request_id"], "req_invalid")
        self.assertNotIn("detail", response.json())


if __name__ == "__main__":
    unittest.main()
