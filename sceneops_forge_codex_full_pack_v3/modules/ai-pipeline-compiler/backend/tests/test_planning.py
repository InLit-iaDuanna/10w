"""Maintenance cases; fake model never touches CLI/network. Not run this turn."""
import tempfile
import unittest
from pathlib import Path
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_pipeline import PlanningService, PlanningRequest


class FakeProvider:
    def provider_available(self):
        return True

    async def structured(self, prompt, schema, purpose="planning"):
        if purpose == "intent":
            return {"desired_outcome": "读取项目资料", "constraints": [], "acceptance_criteria": ["获得当前项目记录"],
                "requested_artifacts": [], "missing_facts": []}
        return {"title": "读取当前项目", "stages": [{"id": "stage-1", "title": "读取", "steps": [
            {"id": "read-project", "title": "读取项目", "capability_id": "workspace.project.read", "inputs": {}, "depends_on": []}]}]}


class PlanningTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_is_persisted_without_running(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.sqlite3"
            workspace = SqliteWorkspaceRepository(path)
            project = workspace.create_project("本地测试项目")
            service = PlanningService(path, workspace)
            service.provider = FakeProvider()
            proposal = await service.propose(PlanningRequest(project_id=project.project_id, goal="读取资料"))
            self.assertTrue(proposal.validation.valid)
            self.assertEqual(service.runtime.list(project.project_id), [])
            self.assertEqual(service.records.proposal(project.project_id, proposal.id).definition.title, "读取当前项目")

    async def test_unknown_project_rejected_before_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.sqlite3"
            service = PlanningService(path, SqliteWorkspaceRepository(path))
            with self.assertRaises(KeyError):
                await service.propose(PlanningRequest(project_id="unknown", goal="读取资料"))
