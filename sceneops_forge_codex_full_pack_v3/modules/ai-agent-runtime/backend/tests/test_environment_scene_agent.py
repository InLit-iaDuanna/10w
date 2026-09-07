"""Deterministic project-scene Agent acceptance; no model, DCC, build, or playtest."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from asset_library import (ProjectAssetCatalogService, ProjectAssetRegistration,
    ProjectAssetVersion, SqliteProjectAssetRepository)
from sceneops_ai_agents import (AgentAction, AgentTaskService, AuthorizeAgentTask,
                                 PrepareAgentTask)
from sceneops_harness import HarnessError
from sceneops_project_workspace import SqliteWorkspaceRepository
from world_composer import (EnvironmentSceneService, EnvironmentTransform,
                            ManualPlacementRequest, TransformObjectRequest)


class ProviderFixture:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.actions = None

    def settings(self):
        return SimpleNamespace(provider="fixture", model="fixture-model")

    async def generate(self, *args, **kwargs):
        if self.actions is None:
            raise AssertionError("deterministic acceptance must not call a model")
        selected = self.actions.pop(0)
        return SimpleNamespace(provider='fixture', model='fixture-model',
            text='', structured=selected.model_dump(mode='json'), usage={}, latency_ms=1)


def action(action_id, capability_id, **inputs):
    return AgentAction(action_id=action_id, capability_id=capability_id,
        rationale=f"fixture {capability_id}", inputs=inputs)


class EnvironmentSceneAgentTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory(prefix="sceneops-environment-agent-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / "state.sqlite3"
        self.workspace = SqliteWorkspaceRepository(self.database)
        self.project = self.workspace.create_project("Scene Agent Fixture")
        self.other_project = self.workspace.create_project("Other Project Fixture")
        self.catalog = ProjectAssetCatalogService(SqliteProjectAssetRepository(self.database))
        self.asset = self.catalog.register_version(ProjectAssetRegistration(
            project_id=self.project.project_id, card_id="environment", source_asset_id="box_asset",
            title="箱子", source_type="generated", version=ProjectAssetVersion(
                source_version=1, dimensions_m=(1, 1, 1), vertex_count=8, triangle_count=12,
                blend_path="box/model.blend", preview_path="box/preview.glb",
                fbx_path="box/model.fbx", operation="generate"))).entry
        self.catalog.register_version(ProjectAssetRegistration(
            project_id=self.other_project.project_id, card_id="environment",
            source_asset_id="other_project_asset", title="其他项目资产",
            source_type="generated", version=ProjectAssetVersion(
                source_version=1, dimensions_m=(2, 2, 2), vertex_count=8, triangle_count=12,
                blend_path="other/model.blend", preview_path="other/preview.glb",
                fbx_path="other/model.fbx", operation="generate")))
        self.provider = ProviderFixture(self.database)
        self.environment = EnvironmentSceneService(
            self.database, self.workspace, self.catalog, self.provider)
        scene = self.environment.add_object(self.project.project_id, ManualPlacementRequest(
            expected_version=0, asset_id=self.asset.id, asset_version=1,
            position_m=(0, 2, 3)))
        self.object_id = scene.objects[0].id
        scene = self.environment.transform_object(self.project.project_id, self.object_id,
            TransformObjectRequest(expected_version=scene.version,
                transform=EnvironmentTransform(position_m=(0, 2, 3),
                    rotation_y_deg=25, scale=1.2)))
        self.initial_version = scene.version
        self.service = AgentTaskService(self.database, self.workspace, self.root,
            provider=self.provider, project_assets=self.catalog,
            environment_scenes=self.environment)
        self.addAsyncCleanup(self.service.close)

    async def settled(self, task):
        await asyncio.wait_for(asyncio.gather(*list(self.service.jobs.values())), timeout=5)
        return self.service.get(task.id)

    def prepare(self, goal, object_id=None):
        return self.service.prepare(PrepareAgentTask(project_id=self.project.project_id,
            goal=goal, task_profile="environment-scene", execution_mode="typed-tools",
            selected_scene_object_ids=[object_id or self.object_id]))

    def authorize(self, task, actions):
        return self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True),
            actions=actions)

    def sequence(self, prefix, version, position):
        return [
            action(prefix + "_assets", "project.assets.list"),
            action(prefix + "_read_before", "environment.scene.read"),
            action(prefix + "_transform", "environment.object.transform",
                object_id=self.object_id, expected_version=version, position_m=position,
                rotation_y_deg=25, scale=1.2),
            action(prefix + "_read_after", "environment.scene.read"),
            action(prefix + "_finish", "agent.finish", summary="Verify current scene"),
        ]

    async def test_two_authorized_rounds_modify_the_same_object_from_latest_scene(self):
        first = self.prepare("把当前选中箱子的世界坐标 X 增加 1 米，保持旋转和缩放不变")
        self.assertIsNone(first.grant)
        self.assertEqual(first.authorization_card.scene_write_object_ids, [self.object_id])
        self.assertIn(self.object_id, first.authorization_card.scope)
        self.assertIn("选择信息是任务上下文", first.observations["scene_selection"]["notice"])
        self.authorize(first, self.sequence("first", self.initial_version, [1, 2, 3]))
        first = await self.settled(first)

        after_first = self.environment.get(self.project.project_id)
        self.assertEqual(first.status, "completed")
        self.assertEqual(after_first.objects[0].transform.position_m, (1, 2, 3))
        self.assertEqual(after_first.objects[0].transform.rotation_y_deg, 25)
        self.assertEqual(after_first.objects[0].transform.scale, 1.2)
        self.assertFalse(first.observations["environment_scene"]["game_runtime_updated"])
        asset_evidence = first.actions[0].result["evidence"]
        self.assertEqual(asset_evidence["project_id"], self.project.project_id)
        self.assertEqual([item["id"] for item in asset_evidence["assets"]], [self.asset.id])
        transform_evidence = first.actions[2].result["evidence"]
        self.assertEqual(transform_evidence["before_object"]["id"], self.object_id)
        self.assertEqual(transform_evidence["object"]["transform"]["position_m"], [1, 2, 3])

        second = self.prepare("在刚才结果的基础上，再把 Z 增加 0.5 米")
        self.authorize(second, self.sequence("second", after_first.version, [1, 2, 3.5]))
        second = await self.settled(second)

        after_second = self.environment.get(self.project.project_id)
        self.assertEqual(second.status, "completed")
        self.assertEqual(after_second.objects[0].id, self.object_id)
        self.assertEqual(after_second.objects[0].transform.position_m, (1, 2, 3.5))
        self.assertEqual(after_second.objects[0].transform.rotation_y_deg, 25)
        self.assertEqual(after_second.objects[0].transform.scale, 1.2)
        self.assertEqual(len(after_second.objects), 1)
        self.assertGreater(after_second.version, after_first.version)
        self.assertEqual(second.observations["execution_driver"], "deterministic")

    async def test_scope_version_and_project_boundaries_do_not_write(self):
        task = self.prepare("移动选中箱子")
        other_id = "sobj_not_authorized"
        self.authorize(task, [action("wrong_object", "environment.object.transform",
            object_id=other_id, expected_version=self.initial_version,
            position_m=[9, 9, 9], rotation_y_deg=0, scale=1)])
        denied = await self.settled(task)
        self.assertEqual(denied.status, "needs_approval")
        self.assertEqual(self.environment.get(self.project.project_id).version, self.initial_version)

        conflict = self.prepare("移动选中箱子")
        self.authorize(conflict, [action("stale", "environment.object.transform",
            object_id=self.object_id, expected_version=self.initial_version - 1,
            position_m=[9, 9, 9], rotation_y_deg=25, scale=1.2)])
        conflicted = await self.settled(conflict)
        self.assertEqual(conflicted.actions[0].state, "failed")
        self.assertEqual(conflicted.actions[0].effect_state, "NONE")
        self.assertEqual(self.environment.get(self.project.project_id).version, self.initial_version)

        missing_context = self.prepare("移动选中箱子")
        self.authorize(missing_context, [action("write_without_reads",
            "environment.object.transform", object_id=self.object_id,
            expected_version=self.initial_version, position_m=[0, 2, 3.5],
            rotation_y_deg=25, scale=1.2)])
        missing_context = await self.settled(missing_context)
        self.assertEqual(missing_context.actions[0].state, "failed")
        self.assertIn("先读取当前项目资产", missing_context.actions[0].reason)
        self.assertEqual(self.environment.get(self.project.project_id).version, self.initial_version)

        duplicate = self.prepare("把 Z 增加 0.5 米")
        self.authorize(duplicate, [
            action("duplicate_assets", "project.assets.list"),
            action("duplicate_read", "environment.scene.read"),
            action("first_transform", "environment.object.transform",
                object_id=self.object_id, expected_version=self.initial_version,
                position_m=[0, 2, 3.5], rotation_y_deg=25, scale=1.2),
            action("duplicate_transform", "environment.object.transform",
                object_id=self.object_id, expected_version=self.initial_version + 1,
                position_m=[0, 2, 4], rotation_y_deg=25, scale=1.2),
        ])
        duplicate = await self.settled(duplicate)
        after_duplicate = self.environment.get(self.project.project_id)
        self.assertEqual(duplicate.status, "failed")
        self.assertEqual(duplicate.actions[3].state, "failed")
        self.assertEqual(duplicate.actions[3].effect_state, "NONE")
        self.assertIn("只允许一次成功对象变换", duplicate.reason)
        self.assertEqual(after_duplicate.version, self.initial_version + 1)
        self.assertEqual(after_duplicate.objects[0].transform.position_m, (0, 2, 3.5))

        with self.assertRaises(HarnessError) as missing:
            self.service.prepare(PrepareAgentTask(project_id=self.other_project.project_id,
                goal="移动另一个项目里的箱子", task_profile="environment-scene",
                selected_scene_object_ids=[self.object_id]))
        self.assertEqual(missing.exception.code, "SCENE_OBJECT_NOT_FOUND")

    async def test_live_loop_retries_after_read_context_and_finishes_from_readback(self):
        self.provider.actions = [
            action('live_read_before', 'environment.scene.read'),
            action('live_transform', 'environment.object.transform',
                object_id=self.object_id, expected_version=self.initial_version,
                position_m=[1, 2, 3], rotation_y_deg=25, scale=1.2),
            action('live_assets', 'project.assets.list'),
            AgentAction(action_id='live_transform',
                capability_id='environment.object.transform',
                rationale='retry after required project assets were read',
                inputs={'object_id': self.object_id,
                    'expected_version': self.initial_version,
                    'position_m': [1, 2, 3], 'rotation_y_deg': 25, 'scale': 1.2}),
            action('live_read_after', 'environment.scene.read'),
            action('must_not_run', 'environment.object.transform',
                object_id=self.object_id, expected_version=self.initial_version + 1,
                position_m=[2, 2, 3], rotation_y_deg=25, scale=1.2),
        ]
        task = self.prepare('把当前选中箱子的世界坐标 X 增加 1 米并回读')
        self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id,
            accept_unknown_cost=True))

        completed = await self.settled(task)

        self.assertEqual(completed.status, 'completed')
        self.assertEqual(completed.model_calls_used, 5)
        self.assertEqual(len(self.provider.actions), 1)
        self.assertEqual([item.action.capability_id for item in completed.actions], [
            'environment.scene.read', 'environment.object.transform',
            'project.assets.list', 'environment.scene.read', 'agent.finish'])
        self.assertEqual(completed.actions[1].state, 'succeeded')
        self.assertEqual(completed.actions[1].attempts, 1)
        self.assertEqual(self.environment.get(self.project.project_id).objects[0].transform.position_m,
                         (1, 2, 3))


if __name__ == "__main__":
    import unittest
    unittest.main()
