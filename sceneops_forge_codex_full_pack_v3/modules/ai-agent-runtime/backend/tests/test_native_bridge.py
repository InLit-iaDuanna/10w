"""Local transport and authorization checks; no model, browser or build execution."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from sceneops_ai_agents.native_bridge import NativeToolBridge, native_tool_capabilities
from sceneops_ai_agents.native_skills import SKILL_NAMES, stage_native_skills
from sceneops_harness import HarnessError


class BridgeFixture:
    def __init__(self):
        self.events = []
        self.task = SimpleNamespace(id='task_one', project_id='project_one', cancel_requested=False,
            grant=SimpleNamespace(capability_ids=['project.assets.list'], workspace_id='workspace_one'),
            authorization_card=SimpleNamespace(task_profile='project-demo-agent'))
        self.project_assets = SimpleNamespace(list=lambda project: [])
        self.records = SimpleNamespace(update=lambda task, mutate, event, payload: self.events.append((event, payload)))

    def get(self, task):
        return self.task

    def check_grant(self, task, capability=None):
        if self.task.cancel_requested or (capability and capability not in self.task.grant.capability_ids):
            raise HarnessError('TASK_SCOPE_DENIED', 'Task is not authorized')
        return self.task


class NativeBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_domain_dispatch_and_stdio_transport(self):
        service = BridgeFixture()
        async with NativeToolBridge(service, 'task_one') as bridge:
            import os
            config = bridge.mcp_servers['sceneops']
            process = await asyncio.create_subprocess_exec(config['command'], *config['args'],
                env={**os.environ, **config['env']}, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                         'params': {'name': 'project.assets.list', 'arguments': {}}}]
            stdout, stderr = await asyncio.wait_for(process.communicate(
                ('\n'.join(json.dumps(message) for message in requests) + '\n').encode()), 15)
            self.assertEqual(process.returncode, 0, stderr.decode())
            responses = [json.loads(line) for line in stdout.splitlines()]
            self.assertEqual(responses[1]['result']['tools'][0]['name'], 'project.assets.list')
            self.assertFalse(responses[2]['result']['isError'])
            evidence = json.loads(responses[2]['result']['content'][0]['text'])
            self.assertEqual(evidence['workspace_id'], 'workspace_one')
            self.assertEqual(service.events[-1][0], 'agent.native.tool.completed')
        self.assertEqual(bridge.token, '')

    async def test_scope_fields_unlisted_tools_revocation_and_token(self):
        service = BridgeFixture()
        async with NativeToolBridge(service, 'task_one') as bridge:
            for name, arguments in [('project.assets.list', {'project_id': 'other'}),
                                    ('code.file.write', {'path': 'a', 'content': 'b'}),
                                    ('environment.object.remove', {'expected_version': 1, 'object_id': 'other'})]:
                with self.assertRaises((HarnessError, ValueError)):
                    await bridge.call_tool(name, arguments)
            def unauthorized():
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(bridge.url, data=b'{}', method='POST'))
                self.assertEqual(caught.exception.code, 403)
            await asyncio.to_thread(unauthorized)
            service.task.cancel_requested = True
            with self.assertRaises(HarnessError):
                await bridge.call_tool('project.assets.list', {})

    async def test_browser_tool_returns_pixels_in_mcp_content(self):
        import base64
        from unittest.mock import Mock
        service = BridgeFixture()
        service.task.authorization_card.allow_model_image_input = True
        service.task.grant.allow_model_image_input = True
        service.task.grant.capability_ids = ['code.browser.observe']
        with TemporaryDirectory() as directory:
            image = Path(directory) / 'screenshot.png'
            pixels = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aT1sAAAAASUVORK5CYII=')
            image.write_bytes(pixels)
            service.production = SimpleNamespace(model_image_path=Mock(return_value=image))
            evidence = {'run': {'id': 'run-one', 'status': 'succeeded', 'source_stale': False,
                'observation': {'screenshot_artifact': {'id': 'artifact-one', 'version': 1}}}}
            async with NativeToolBridge(service, 'task_one') as bridge:
                bridge.tools.dispatch = AsyncMock(return_value=SimpleNamespace(outputs={'evidence': evidence}))
                result = await bridge.rpc({'method': 'tools/call', 'params': {'name': 'code.browser.observe', 'arguments': {}}})
                transported = json.loads(json.dumps(result))
                self.assertFalse(transported['isError'])
                self.assertEqual(transported['content'][1]['mimeType'], 'image/png')
                self.assertEqual(base64.b64decode(transported['content'][1]['data']), pixels)
                self.assertNotIn('data', service.events[-1][1]['evidence']['model_image_input'])

    def test_permissions_are_independent(self):
        card = SimpleNamespace(allow_game_execution=True, allow_dependency_install=False,
            allow_browser_observation=True, allow_browser_interaction=False, include_demo_assets=True,allow_blender_edit=False)
        names = native_tool_capabilities(card)
        self.assertIn('code.browser.observe', names)
        self.assertNotIn('code.browser.interact', names)
        self.assertNotIn('code.dependencies.prepare', names)
        self.assertIn('code.demo_assets.install', names)
        card.include_demo_assets = False
        self.assertNotIn('code.demo_assets.install', native_tool_capabilities(card))
        card.allow_game_execution = False
        self.assertNotIn('code.project.build', native_tool_capabilities(card))
        self.assertIn('environment.object.place', native_tool_capabilities(card))
        self.assertNotIn('blender.asset.edit',native_tool_capabilities(card))
        card.allow_blender_edit=True
        self.assertIn('blender.asset.edit',native_tool_capabilities(card))

    async def test_saved_production_document_is_project_scoped_data(self):
        service=BridgeFixture()
        service.task.grant.capability_ids=['production.document.read','blender.asset.edit']
        def read(project,module):
            self.assertEqual(project,'project_one');self.assertEqual(module,'ui-audio-vfx')
            return SimpleNamespace(model_dump=lambda **kwargs:{'revision':3,'sample_id':None,'payload':{'event':'weapon.fire'}})
        service.workspace=SimpleNamespace(get_document=read)
        bridge=NativeToolBridge(service,'task_one')
        self.assertIn('blender.asset.edit',[item['name'] for item in bridge.list_tools()])
        result=await bridge.call_tool('production.document.read',{'module_id':'ui-audio-vfx'})
        self.assertEqual(json.loads(result['content'][0]['text'])['document']['revision'],3)
        with self.assertRaises(HarnessError):
            await bridge.call_tool('production.document.read',{'module_id':'ui-audio-vfx','project_id':'other'})

    async def test_entity_reader_uses_task_scope_and_generated_inputs(self):
        service=BridgeFixture()
        service.task.grant.capability_ids=['production.entities.read','production.entity.adopt']
        bridge=NativeToolBridge(service,'task_one')
        names={tool['name'] for tool in bridge.list_tools()}
        self.assertEqual(names,{'production.entities.read','production.entity.adopt'})
        with patch('sceneops_ai_agents.entity_production.list_entities',return_value=[]) as read:
            result=await bridge.call_tool('production.entities.read',{})
            self.assertEqual(json.loads(result['content'][0]['text'])['entities'],[])
            read.assert_called_once_with(service,'task_one')
        with self.assertRaises(HarnessError):
            await bridge.call_tool('production.entities.read',{'project_id':'other'})
        with self.assertRaises(ValueError):
            await bridge.call_tool('production.entity.adopt',{'entity_id':'entity','asset_version':1,'expected_revision':0,'request_id':'adopt'})

    def test_skill_staging_preserves_unrelated_and_rejects_links(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated = root / '.agents/skills/personal/SKILL.md'
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text('personal')
            for executor, prefix in [('codex', '.agents'), ('codebuddy', '.codebuddy')]:
                staged = stage_native_skills(root, executor)
                self.assertEqual(len(staged), 5)
                self.assertTrue(all((root / item).is_file() for item in staged))
                self.assertTrue((root / prefix / 'skills/sceneops-threejs-gameplay/references/time-and-state.md').is_file())
                self.assertEqual(stage_native_skills(root, executor), staged)
            self.assertEqual(unrelated.read_text(), 'personal')
            target = root / '.agents/skills' / SKILL_NAMES[0]
            (target / '.sceneops-owned').unlink()
            with self.assertRaises(ValueError):
                stage_native_skills(root, 'codex')


import test_project_demo_task as project_fixture
from sceneops_ai_agents import AuthorizeAgentTask
from unittest.mock import patch


class NativeBridgeDomainTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = project_fixture.ProjectDemoTaskSmoke.asyncSetUp
    asyncTearDown = project_fixture.ProjectDemoTaskSmoke.asyncTearDown

    async def test_actual_asset_instance_version_roundtrip(self):
        request = project_fixture.ProjectDemoTaskSmoke.request(self).model_copy(update={
            'task_profile': 'project-demo-agent', 'execution_mode': 'agent-full-access',
            'native_production': True, 'permission_mode': 'scoped'})
        task = self.service.prepare(request)
        with patch.object(self.service, '_run', new=AsyncMock()):
            self.service.authorize(task.id, AuthorizeAgentTask(
                authorization_card_id=task.authorization_card.id, accept_unknown_cost=True,
                creation_brief_version=1))
            await asyncio.gather(*list(self.service.jobs.values()))
        root = Path(self.service.get(task.id).grant.workspace_root)
        import asset_library
        source = Path(asset_library.__file__).parent / 'builtin_assets/glb/crate.glb'
        (root / 'crate.glb').write_bytes(source.read_bytes())
        async with NativeToolBridge(self.service, task.id) as bridge:
            async def call(name, args):
                result = await bridge.call_tool(name, args)
                return json.loads(result['content'][0]['text'])
            with self.assertRaises(HarnessError):
                await call('project.asset.register', {'path': '../outside.glb', 'title': 'Denied'})
            (root / 'invalid.glb').write_bytes(b'not a model')
            with self.assertRaises(ValueError):
                await call('project.asset.register', {'path': 'invalid.glb', 'title': 'Invalid'})
            created = await call('project.asset.register', {'path': 'crate.glb', 'title': 'Crate'})
            asset = created['asset']
            self.assertEqual(asset['versions'][0]['source_kind'], 'glb')
            self.assertGreater(asset['versions'][0]['vertex_count'], 0)
            scene = self.scenes.get(task.project_id)
            placed = await call('environment.object.place', {'expected_version': scene.version,
                'asset_id': asset['id'], 'asset_version': 1, 'position_m': [0, 0, 0]})
            instance = placed['affected_object_ids'][0]
            changed = await call('environment.demo_object.transform', {
                'expected_version': placed['scene_version'], 'object_id': instance,
                'position_m': [1, 0, 2], 'rotation_y_deg': 45, 'scale': 1})
            with self.assertRaises(HarnessError):
                await call('environment.demo_object.transform', {
                    'expected_version': placed['scene_version'], 'object_id': instance,
                    'position_m': [5, 0, 0], 'rotation_y_deg': 0, 'scale': 1})
            updated = await call('project.asset.register', {'path': 'crate.glb', 'title': 'Crate',
                'asset_id': asset['id'], 'expected_version': 1})
            self.assertEqual(updated['asset']['id'], asset['id'])
            self.assertEqual(updated['asset']['current_version'], 2)
            with self.assertRaises(HarnessError):
                await call('project.asset.register', {'path': 'crate.glb', 'title': 'Stale',
                    'asset_id': asset['id'], 'expected_version': 1})
            rebound = await call('environment.asset.rebind', {'asset_id': asset['id'],
                'expected_version': changed['scene_version'], 'from_asset_version': 1, 'to_asset_version': 2})
            await call('code.demo_content.materialize', {})
            self.assertEqual(self.scenes.get(task.project_id).objects[0].asset_version, 2)
            await call('environment.object.remove', {'expected_version': rebound['scene_version'],
                                                    'object_id': instance})
            self.assertEqual(self.scenes.get(task.project_id).objects, [])
        self.assertEqual(self.service.get(task.id).actions, [])
