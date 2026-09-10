"""Authenticated HTTP smoke for bounded production preparation without a model call."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app import create_app


class ProductionPreparationHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        environment = patch.dict(os.environ, {
            "SCENEOPS_DATA_DIR": self.directory.name,
            "SCENEOPS_LOCAL_TOKEN": "production-preparation-test",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.app = create_app()
        self.client = TestClient(self.app, base_url="http://127.0.0.1",
            raise_server_exceptions=False, headers={
                "x-sceneops-token": "production-preparation-test",
                "origin": "http://127.0.0.1:4300",
            })
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.project = self.app.state.workspace_repository.create_folder_project(
            Path(self.directory.name).resolve(), "preparation-project")

    def test_unconfigured_selector_returns_reusable_directory_without_using_main_model(self):
        body = {
            "project_id": self.project.project_id,
            "request_key": "first-game-request",
            "production_kind": "game_create",
            "requirement": "做一个一屏收集游戏",
            "target_platform": "web",
            "available_capability_ids": ["code.demo_assets.install"],
            "model_call_allowed": True,
            "remaining_model_calls": 2,
            "remaining_time_seconds": 30,
        }

        first = self.client.post("/api/production-preparation/prepare", json=body)
        second = self.client.post("/api/production-preparation/prepare", json=body)
        saved = self.client.get(
            "/api/production-preparation/results/first-game-request",
            params={"project_id": self.project.project_id})

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "skipped")
        self.assertEqual(first.json()["call"]["status"], "skipped")
        self.assertGreater(len(first.json()["candidate_directory"]["candidates"]), 0)
        self.assertTrue(second.json()["reused"])
        self.assertEqual(saved.json()["preparation_id"], first.json()["preparation_id"])

    def test_fixed_primitive_modeling_does_not_receive_unexecutable_reuse_or_edit_paths(self):
        base = {
            "project_id": self.project.project_id,
            "request_key": "primitive-model-request",
            "production_kind": "modeling",
            "requirement": "制作一棵低多边形树",
            "target_platform": "web",
            "current_state": {"executor": "fixed-blender-primitives"},
            "available_capability_ids": ["model.primitive.create"],
            "model_call_allowed": False,
            "remaining_model_calls": 0,
        }
        response = self.client.post("/api/production-preparation/candidates/search", json={
            "request": base, "kinds": ["asset", "skill"]})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["candidates"], [])

        import_request = {**base, "request_key": "unity-import-request",
            "target_platform": "unity",
            "available_capability_ids": ["unity.asset.import"]}
        response = self.client.post("/api/production-preparation/candidates/search", json={
            "request": import_request, "kinds": ["asset", "skill"]})
        candidates = response.json()["candidates"]

        self.assertTrue(any(item["kind"] == "asset" for item in candidates))
        self.assertIn("sceneops-unity-project-engineer",
                      {item["candidate_id"] for item in candidates})
        self.assertNotIn("sceneops-blender-technical-artist",
                         {item["candidate_id"] for item in candidates})


if __name__ == "__main__":
    unittest.main()
