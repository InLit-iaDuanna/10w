"""D1/D2 public-service round trip for one deterministic key-door Demo."""
import asyncio
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from asset_library import (DoorRecipe, ProjectAssetCatalogService, SqliteProjectAssetRepository,
                           UpdateProjectAssetRecipeRequest)
from sceneops_ai_agents import AgentTaskService, AuthorizeAgentTask, PrepareAgentTask
from sceneops_harness import HarnessError
from sceneops_project_workspace import SqliteWorkspaceRepository
from world_composer import (EnvironmentSceneService, EnvironmentTransform,
                            RebindAssetVersionRequest, TransformObjectRequest,
                            UpdateKeyDoorBehaviorRequest)


class ProjectDemoTaskSmoke(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.database = self.root / 'state.sqlite3'
        self.workspace = SqliteWorkspaceRepository(self.database)
        self.project = self.workspace.create_folder_project(self.root, 'key-door')
        self.workspace.initialize_game_project(self.project.project_id, {
            'target_platform': 'web', 'engine': 'threejs',
            'code_architecture': 'object-component', 'architecture_label': '对象／组件式',
            'selection_method': 'manual', 'rationale': 'fixture', 'tradeoffs': [],
            'ecs_library': None,
        }, 1, commit_baseline=False)
        self.direction = {'value': 'direction_' + '1' * 32}
        self.provider = SimpleNamespace(database_path=self.database,
            settings=lambda: SimpleNamespace(provider='codebuddycli', model='fixture'),
            generate=AsyncMock(side_effect=AssertionError('project Demo must not call a model')))
        self.assets = ProjectAssetCatalogService(SqliteProjectAssetRepository(self.database))
        self.scenes = EnvironmentSceneService(self.database, self.workspace, self.assets, self.provider)
        self.pnpm = self.root / 'fixture-pnpm'
        self.pnpm.write_text(f'''#!{Path(sys.executable).resolve()}
import pathlib, sys, json
root=pathlib.Path.cwd()
if sys.argv[1]=='install':
 target=root/'node_modules/.bin';target.mkdir(parents=True,exist_ok=True);(target/'tsc').write_text('x');(target/'vite').write_text('x')
 manifest=json.loads((root/'package.json').read_text())
 for name in ('three','@types/three'):
  version=manifest.get('dependencies',{{}}).get(name) or manifest.get('devDependencies',{{}}).get(name)
  target=root/'node_modules'/name;target.mkdir(parents=True,exist_ok=True);(target/'package.json').write_text(json.dumps({{'version':version}}))
elif sys.argv[1:3]==['exec','tsc']:
 print('fixture check')
elif sys.argv[1:3]==['exec','vite']:
 if (root/'.fail-build').exists(): raise SystemExit(2)
 output=root/'dist';output.mkdir(exist_ok=True);(output/'index.html').write_text('<main>key door</main>')
else: raise SystemExit(64)
''', encoding='utf-8')
        self.pnpm.chmod(self.pnpm.stat().st_mode | stat.S_IXUSR)
        self.service = AgentTaskService(self.database, self.workspace, self.root / 'data',
            provider=self.provider, project_assets=self.assets, environment_scenes=self.scenes,
            project_demo_context=lambda project_id: {
                'direction_id': self.direction['value'], 'direction': {}, 'technical_plan': {}},
            pnpm_executable=str(self.pnpm))

    async def asyncTearDown(self):
        await self.service.close()
        self.temporary.cleanup()

    def request(self):
        return PrepareAgentTask(project_id=self.project.project_id, goal='制作钥匙门初版',
            task_profile='project-demo', execution_mode='typed-tools',
            allow_game_execution=True, allow_dependency_install=True, include_demo_assets=True,
            alignment_id=self.direction['value'])

    async def wait(self):
        await asyncio.wait_for(asyncio.gather(*list(self.service.jobs.values())), timeout=20)

    async def test_project_demo_reuses_task_updates_sources_and_preserves_playable(self):
        prepared = self.service.prepare(self.request())
        self.assertEqual(self.assets.list(self.project.project_id), [])
        self.assertEqual(self.scenes.get(self.project.project_id).version, 0)
        self.assertEqual(self.service.prepare(self.request()).id, prepared.id)
        self.assertIsNone(prepared.authorization_card.card_id)
        self.assertTrue(prepared.authorization_card.workspace_id.startswith('demo_ws_'))

        self.direction['value'] = 'direction_' + '2' * 32
        with self.assertRaisesRegex(HarnessError, '方向已改变'):
            self.service.authorize(prepared.id, AuthorizeAgentTask(
                authorization_card_id=prepared.authorization_card.id, accept_unknown_cost=True))
        self.direction['value'] = prepared.authorization_card.alignment_id
        self.service.authorize(prepared.id, AuthorizeAgentTask(
            authorization_card_id=prepared.authorization_card.id, accept_unknown_cost=True))
        await self.wait()

        finished = self.service.get(prepared.id)
        self.assertEqual(finished.status, 'review_required', finished.reason)
        self.assertEqual(finished.model_calls_used, 0)
        scene = self.scenes.get(self.project.project_id)
        self.assertEqual(len(scene.objects), 2)
        self.assertEqual(len({item.asset_id for item in scene.objects}), 1)
        self.assertTrue(all(item.behavior and item.behavior.definition_id == 'KeyDoor@1'
                            for item in scene.objects))
        first_position, second_position = scene.objects[0].transform.position_m, scene.objects[1].transform.position_m
        snapshot = self.service.game_status(prepared.id)
        first_candidate = snapshot.current_playable_candidate
        self.assertEqual(snapshot.update_state, 'updated')
        self.assertEqual(first_candidate.scene_version, scene.version)
        self.assertEqual(len(first_candidate.asset_versions), 1)

        door = self.assets.get(self.project.project_id, scene.objects[0].asset_id)
        saved = self.assets.update_recipe(self.project.project_id, door.id,
            UpdateProjectAssetRecipeRequest(expected_version=door.current_version,
                recipe=DoorRecipe(width_m=1.8, height_m=2.2, thickness_m=.15)))
        rebound = self.scenes.rebind_asset_version(self.project.project_id, door.id,
            RebindAssetVersionRequest(expected_version=scene.version,
                from_asset_version=door.current_version,
                to_asset_version=saved.entry.current_version))
        self.assertEqual(set(rebound.affected_object_ids), {item.id for item in scene.objects})
        moved = self.scenes.transform_object(self.project.project_id, scene.objects[0].id,
            TransformObjectRequest(expected_version=rebound.scene.version,
                transform=EnvironmentTransform(position_m=(0, 0, -1))))
        self.assertEqual(moved.objects[1].transform.position_m, second_position)
        changed = self.scenes.update_key_door_behavior(self.project.project_id, moved.objects[0].id,
            UpdateKeyDoorBehaviorRequest(expected_version=moved.version,
                required_key_asset_id=door.id, interaction_distance_m=1, open_angle_deg=90))
        self.assertEqual(changed.objects[0].behavior.interaction_distance_m, 1)

        fail = Path(self.project.root_path) / '.fail-build'
        fail.write_text('fixture', encoding='utf-8')
        self.service.update_project_demo(prepared.id)
        await self.wait()
        failed = self.service.game_status(prepared.id)
        self.assertEqual(failed.update_state, 'failed')
        self.assertEqual(failed.current_playable_candidate.id, first_candidate.id)
        self.assertEqual(failed.preview.status, 'running')

        fail.unlink()
        self.service.update_project_demo(prepared.id)
        await self.wait()
        repaired = self.service.game_status(prepared.id)
        self.assertEqual(repaired.update_state, 'updated')
        self.assertNotEqual(repaired.current_playable_candidate.id, first_candidate.id)
        content = (Path(self.project.root_path) / 'src/game/sceneops-demo-content.ts').read_text('utf-8')
        self.assertIn('"width_m": 1.8', content)
        self.assertIn('"interaction_distance_m": 1.0', content)
        self.assertIn('colliderDimensionsM', content)
        self.assertEqual(first_position, (-2.0, 0.0, -4.0))
        self.provider.generate.assert_not_awaited()

        await self.service.close()
        reopened_workspace = SqliteWorkspaceRepository(self.database)
        reopened_assets = ProjectAssetCatalogService(SqliteProjectAssetRepository(self.database))
        reopened_scenes = EnvironmentSceneService(
            self.database, reopened_workspace, reopened_assets, self.provider)
        self.service = AgentTaskService(
            self.database, reopened_workspace, self.root / 'data', provider=self.provider,
            project_assets=reopened_assets, environment_scenes=reopened_scenes,
            project_demo_context=lambda project_id: {
                'direction_id': self.direction['value'], 'direction': {}, 'technical_plan': {}},
            pnpm_executable=str(self.pnpm))
        reopened_task = self.service.get(prepared.id)
        reopened = self.service.game_status(prepared.id)
        self.assertEqual(reopened_task.authorization_card.workspace_id,
                         reopened_workspace.get_project_demo_workspace(
                             self.project.project_id)['workspace_id'])
        self.assertEqual(reopened.current_playable_candidate.id,
                         repaired.current_playable_candidate.id)
        self.assertEqual(reopened_scenes.get(self.project.project_id).version, changed.version)
        self.assertEqual(reopened_assets.get(self.project.project_id, door.id).current_version,
                         saved.entry.current_version)
