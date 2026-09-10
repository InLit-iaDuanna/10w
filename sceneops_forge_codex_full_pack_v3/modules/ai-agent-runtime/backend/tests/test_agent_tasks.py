"""Injected synthetic transport/session fixtures only; not run during implementation."""
import asyncio
import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from pydantic import ValidationError
from sceneops_ai_agents import (AgentTaskService, AuthorizeAgentTask, PrepareAgentTask)
from sceneops_harness import HarnessError


class WorkspaceFixture:
    def __init__(self):
        self.projects = {}

    def create_project(self, name):
        project = SimpleNamespace(project_id=f"prj_fixture{len(self.projects):08d}", name=name)
        self.projects[project.project_id] = project
        return project

    def get_project(self, project_id):
        return self.projects[project_id]


def action(action_id, cap, inputs=None):
    return {"action_id": action_id, "capability_id": cap, "rationale": "Synthetic unit-test action", "inputs": inputs or {}}


class ProviderFixture:
    def __init__(self, path, actions):
        self.database_path, self.actions, self.calls = path, list(actions), 0

    def settings(self):
        return SimpleNamespace(provider="codebuddycli", model="cli-default")

    async def generate(self, prompt, **kwargs):
        index = min(self.calls, len(self.actions) - 1)
        self.calls += 1
        value = self.actions[index]
        return SimpleNamespace(structured=value, text=json.dumps(value), provider="codebuddycli",
                               model="cli-default", latency_ms=0, usage=None)


class SessionFixture:
    def __init__(self, world, tool, root, state):
        self.world, self.tool, self.root = world, tool, root
        self.binding = None

    def bind_authorization(self, grant):
        self.binding = grant

    def start(self):
        assert self.binding is not None
        self.world["starts"].append(self.tool)
        if self.tool == "unity" and self.world.get("license_blocked"):
            raise RuntimeError("No valid Unity Editor license found. Please activate your license.")
        return self.inspect()

    def inspect(self):
        return {"mode": "live", "session_id": self.tool + "_fixture", "workspace_root": str(self.root),
                "objects": self.world[self.tool], "errors": []}

    def create_asset(self, *, request_id, asset_id, sceneops_id, name, dimensions_m, authorization):
        assert authorization["grant_id"] == self.binding["grant_id"]
        self.world["writes"].append(request_id)
        self.world["blender"] = [{"asset_id": asset_id, "sceneops_id": sceneops_id, "name": name, "dimensions_m": list(dimensions_m)}]
        return self.inspect()

    def export_asset(self, *, request_id, asset_id, authorization):
        self.world["writes"].append(request_id)
        return {"mode": "live", "fbx_path": str(self.root / "blender" / (asset_id + ".fbx")),
                "manifest_path": str(self.root / "blender" / (asset_id + ".json"))}

    def import_asset(self, *, request_id, asset_id, sceneops_id, fbx_path, manifest_path, authorization):
        self.world["writes"].append(request_id)
        cube = self.world["blender"][0]
        x, y, z = cube["dimensions_m"]
        self.world["unity"] = [{"asset_id": asset_id, "sceneops_id": sceneops_id,
                                "name": cube["name"], "dimensions_meters": [x, z, y]}]
        return self.inspect()

    def stop(self):
        self.world["stops"].append(self.tool)


class AgentTaskTests(IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.world = {"blender": [], "unity": [], "starts": [], "writes": [], "stops": []}
        self.workspace = WorkspaceFixture()

    def service(self, actions):
        provider = ProviderFixture(self.root / "state.sqlite3", actions)
        service = AgentTaskService(provider.database_path, self.workspace, self.root, provider=provider,
            blender_factory=lambda root, state: SessionFixture(self.world, "blender", root, state),
            unity_factory=lambda root, state: SessionFixture(self.world, "unity", root, state))
        self.addAsyncCleanup(service.close)
        return service

    def authorize(self, service, task):
        return service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))

    async def settled(self, service, task):
        jobs = list(service.jobs.values())
        await asyncio.wait_for(asyncio.gather(*jobs), timeout=5)
        return service.get(task.id)

    def production_actions(self):
        asset = "ast_fixtureasset1"
        return [action("create", "blender.asset.create", {"asset_id": asset, "sceneops_id": "sobj_fixtureobject1",
                    "name": "Test Cube", "dimensions_m": [1, 2, 3]}),
                action("export", "blender.asset.export", {"asset_id": asset}),
                action("import", "unity.asset.import", {"asset_id": asset}),
                action("finish", "agent.finish", {"summary": "Request verification"})]

    async def test_prepare_has_no_provider_or_tool_calls_and_grant_is_explicit(self):
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Create a cube"))
        self.assertEqual(task.status, "awaiting_authorization")
        self.assertIsNone(task.grant)
        self.assertEqual(service.provider.calls, 0)
        self.assertEqual(self.world["starts"], [])
        with self.assertRaises(HarnessError):
            service.check_grant(task.id, "blender.asset.create")

    async def test_complete_requires_two_tool_readbacks(self):
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Create Test Cube, 1×2×3 meters"))
        self.authorize(service, task)
        completed = await self.settled(service, task)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.model_calls_used, 4)
        self.assertIsNone(completed.cost_usd)
        self.assertFalse(completed.budget_accounting_complete)
        self.assertTrue(completed.observations["verification"]["verified"])
        for entry in completed.actions[:3]:
            self.assertIsNotNone(entry.change_set)
            self.assertIsNotNone(entry.approval_id)

    async def test_unknown_capability_cannot_expand_grant(self):
        service = self.service([action("bad", "shell.execute", {"command": "arbitrary"})])
        task = service.prepare(PrepareAgentTask(goal="A bounded cube"))
        self.authorize(service, task)
        blocked = await self.settled(service, task)
        self.assertEqual(blocked.status, "needs_approval")
        self.assertEqual(self.world["writes"], [])

    async def test_all_model_calls_count_including_repeated_planning(self):
        service = self.service([action("inspect", "blender.scene.inspect")])
        task = service.prepare(PrepareAgentTask(goal="Inspect"))
        self.authorize(service, task)
        stopped = await self.settled(service, task)
        self.assertEqual(stopped.model_calls_used, 8)
        self.assertEqual(service.provider.calls, 8)
        self.assertEqual(stopped.status, "needs_approval")
        self.assertEqual(stopped.actions[0].attempts, 1)

    async def test_license_block_does_not_consume_models_until_explicit_resume(self):
        self.world["license_blocked"] = True
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Cube to Unity"))
        self.authorize(service, task)
        blocked = await self.settled(service, task)
        self.assertEqual(blocked.status, "blocked")
        self.assertIn("license", blocked.reason)
        self.assertEqual(service.provider.calls, 3)
        original = blocked.actions[2].request_id
        self.world["license_blocked"] = False
        await service.resume(task.id)
        self.assertEqual(service.provider.calls, 3)
        completed = await self.settled(service, task)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.actions[2].request_id, original)
        self.assertEqual(completed.actions[2].attempts, 1)
        self.assertEqual(len(completed.actions[2].run_ids), 2)

    async def test_cancel_before_authorization_and_event_cursor(self):
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Cube"))
        cancelled = service.cancel(task.id)
        self.assertEqual(cancelled.status, "cancelled")
        events = service.events(task.id)
        self.assertGreater(events.next_cursor, 0)
        self.assertEqual(service.events(task.id, events.next_cursor).events, [])
        self.assertEqual(service.provider.calls, 0)

    async def test_expired_grant_does_not_silently_renew(self):
        service = self.service(self.production_actions())
        self.world["license_blocked"] = True
        task = service.prepare(PrepareAgentTask(goal="Cube"))
        self.authorize(service, task)
        await self.settled(service, task)
        service.records.update(task.id, lambda current: setattr(current.grant, "expires_at", current.created_at - timedelta(seconds=1)), "fixture.expired")
        with self.assertRaises(HarnessError) as error:
            await service.resume(task.id)
        self.assertEqual(error.exception.code, "GRANT_EXPIRED")
        self.assertEqual(service.provider.calls, 3)

    async def test_wrong_card_and_false_budget_consent_do_not_authorize(self):
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Cube"))
        with self.assertRaises(ValidationError):
            AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=False)
        with self.assertRaises(HarnessError) as error:
            service.authorize(task.id, AuthorizeAgentTask(authorization_card_id="wrong-card", accept_unknown_cost=True))
        self.assertEqual(error.exception.code, "AUTHORIZATION_CARD_CHANGED")
        self.assertIsNone(service.get(task.id).grant)
        self.assertEqual(service.provider.calls, 0)

    async def test_actual_provider_mismatch_cannot_execute_model_action(self):
        service = self.service(self.production_actions())
        generate = service.provider.generate
        async def wrong_provider(*args, **kwargs):
            response = await generate(*args, **kwargs)
            response.provider = "openai-compatible"
            return response
        service.provider.generate = wrong_provider
        task = service.prepare(PrepareAgentTask(goal="Cube"))
        self.authorize(service, task)
        stopped = await self.settled(service, task)
        self.assertEqual(stopped.status, "failed")
        self.assertEqual(self.world["starts"], [])
        self.assertEqual(service.provider.calls, 2)

    async def test_agent_can_repair_order_from_observed_failure(self):
        sequence = self.production_actions()
        service = self.service([sequence[1], sequence[0], sequence[1], sequence[2], sequence[3]])
        task = service.prepare(PrepareAgentTask(goal="Cube to Unity"))
        self.authorize(service, task)
        completed = await self.settled(service, task)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.model_calls_used, 5)
        export = next(item for item in completed.actions if item.action.action_id == "export")
        self.assertEqual(export.attempts, 1)
        self.assertEqual(len(export.run_ids), 1)

    async def test_model_cannot_inject_external_source_path(self):
        service = self.service([action("outside", "unity.asset.import",
            {"asset_id": "ast_fixtureasset1", "fbx_path": "/outside/other-project.fbx"})])
        task = service.prepare(PrepareAgentTask(goal="Bounded cube"))
        self.authorize(service, task)
        stopped = await self.settled(service, task)
        self.assertEqual(stopped.status, "needs_approval")
        self.assertEqual(self.world["starts"], [])
        self.assertEqual(self.world["writes"], [])

    async def test_finish_restores_lost_blender_cache_without_replaying_writes(self):
        service = self.service(self.production_actions())
        task = service.prepare(PrepareAgentTask(goal="Cube to Unity"))
        self.authorize(service, task)
        tools = service.tools[task.id]
        original_finish = tools.finish
        captured = {}

        async def finish_with_lost_cache(current):
            tools.sessions.pop("blender")
            tools.session_states.pop("blender")
            writes, calls = list(self.world["writes"]), service.provider.calls
            grant = current.grant.model_dump()
            evidence = await original_finish(current)
            self.assertTrue(evidence["verified"])
            self.assertIn("blender", tools.sessions)
            self.assertEqual(self.world["writes"], writes)
            self.assertEqual(service.provider.calls, calls)
            self.assertEqual(service.get(task.id).grant.model_dump(), grant)
            captured["verified"] = True
            return evidence

        tools.finish = finish_with_lost_cache
        completed = await self.settled(service, task)
        self.assertEqual(completed.status, "completed", completed.reason)
        self.assertTrue(captured["verified"])
        self.assertEqual(tools.sessions, {})
        events = service.events(task.id).events
        self.assertIn("agent.session.restored_for_verification", [event.event_type for event in events])

    async def test_dead_blocked_connection_owner_preserves_grant_and_explicit_resume(self):
        service = self.service(self.production_actions())
        self.world["license_blocked"] = True
        task = service.prepare(PrepareAgentTask(goal="Cube to Unity"))
        self.authorize(service, task)
        blocked = await self.settled(service, task)
        grant, calls, writes = blocked.grant.model_dump(), service.provider.calls, list(self.world["writes"])
        service.records.update(task.id, lambda current: setattr(current, "owner_pid", 12345), "fixture.connection_check_crashed")
        with patch("sceneops_ai_agents.task_service.os.kill", side_effect=ProcessLookupError):
            service.recover_interrupted()
        recovered = service.get(task.id)
        self.assertEqual(recovered.status, "blocked")
        self.assertIsNone(recovered.owner_pid)
        self.assertEqual(recovered.grant.model_dump(), grant)
        self.assertEqual(service.provider.calls, calls)
        self.assertEqual(self.world["writes"], writes)
        self.world["license_blocked"] = False
        await service.resume(task.id)
        self.assertEqual((await self.settled(service, task)).status, "completed")

    async def test_execution_status_tracks_local_lifecycle_without_tool_probes(self):
        service = self.service(self.production_actions())
        self.assertEqual(service.execution_status(), "idle")
        task = service.prepare(PrepareAgentTask(goal="Cube"))
        self.assertEqual(service.execution_status(), "idle")
        self.authorize(service, task)
        self.assertEqual(service.execution_status(), "running")
        await self.settled(service, task)
        self.assertEqual(service.execution_status(), "idle")
        self.assertEqual(service.tools[task.id].sessions, {})
        self.assertCountEqual(self.world["stops"], ["blender", "unity"])
        starts, calls = list(self.world["starts"]), service.provider.calls
        service.execution_status()
        self.assertEqual(self.world["starts"], starts)
        self.assertEqual(service.provider.calls, calls)
        await service.close()
        self.assertEqual(service.execution_status(), "idle")
