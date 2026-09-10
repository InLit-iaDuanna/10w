"""HTTP regressions for audit failures; uses isolated SQLite and no model calls."""
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app import create_app


class ProjectScopeHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        environment = patch.dict(os.environ, {
            "SCENEOPS_DATA_DIR": self.directory.name,
            "SCENEOPS_LOCAL_TOKEN": "project-scope-test",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.app = create_app()
        self.client = TestClient(self.app, base_url="http://127.0.0.1",
            raise_server_exceptions=False, headers={
                "x-sceneops-token": "project-scope-test",
                "origin": "http://127.0.0.1:4300",
            })
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_missing_project_requests_are_not_server_failures(self):
        project_id = "prj_nonexistent_audit"
        cases = [
            ("GET", f"/api/design/journeys/{project_id}", None),
            ("GET", f"/api/agent/projects/{project_id}/production", None),
            ("GET", f"/api/card-assets?project_id={project_id}&card_id=world-3d", None),
            ("POST", f"/api/design/journeys/{project_id}/command", {
                "request_id": "audit_missing", "expected_revision": 0,
                "operation": "save_draft", "text": "x",
            }),
            ("POST", "/api/agent/tasks", {
                "project_id": project_id, "goal": "audit invalid project",
            }),
        ]
        for method, url, body in cases:
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, json=body)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json()["code"], "PROJECT_NOT_FOUND")
                self.assertFalse(response.json()["retryable"])

    def test_existing_project_requires_folder_binding(self):
        response = self.client.post("/api/workspace/projects", json={"name": "Legacy"})
        self.assertEqual(response.status_code, 201, response.text)
        project_id = response.json()["project_id"]
        response = self.client.get(f"/api/design/journeys/{project_id}")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "FOLDER_PROJECT_REQUIRED")
        self.assertFalse(response.json()["retryable"])
        response = self.client.get(f"/api/workspace/folder-projects/{project_id}")
        self.assertEqual(response.status_code, 409, response.text)

    def test_unknown_task_is_not_found(self):
        response = self.client.get("/api/agent/tasks/task_nonexistent_audit")
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["code"], "TASK_NOT_FOUND")

    def test_unrelated_key_error_remains_a_server_error(self):
        with patch.object(self.app.state.workspace_repository, "get_project",
                          side_effect=KeyError("broken internal record")):
            response = self.client.get("/api/agent/projects/prj_nonexistent_audit/production")
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()
