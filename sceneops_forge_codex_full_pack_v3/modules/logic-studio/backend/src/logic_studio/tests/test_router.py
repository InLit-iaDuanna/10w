import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from logic_studio.router import router
from logic_studio.tests.support import code_change_proposal, compile_example, load_json


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def test_validate_graph_api_success(self):
        graph = compile_example("hero-key-door.binding.json")
        response = self.client.post(
            "/logic-studio/graphs/validate",
            json=graph.model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["mode"], "live")

    def test_compile_template_api_reports_missing_binding(self):
        request = load_json("contracts/examples/warehouse-switch-door.binding.json")
        del request["bindings"]["target_sceneops_id"]
        response = self.client.post(
            "/logic-studio/templates/compile",
            json=request,
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("target_sceneops_id", response.json()["detail"])

    def test_code_change_api_stops_at_waiting_approval(self):
        response = self.client.post(
            "/logic-studio/code-changes/propose",
            json=code_change_proposal().model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "waiting_approval")
        self.assertEqual(response.json()["mode"], "planned")
        self.assertTrue(response.json()["dry_run"])


if __name__ == "__main__":
    unittest.main()
