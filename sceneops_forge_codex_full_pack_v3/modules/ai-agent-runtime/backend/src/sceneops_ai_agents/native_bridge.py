"""Task-scoped MCP transport for native CLI production domain operations."""
import asyncio
import hmac
import json
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from pydantic import BaseModel, ConfigDict
from sceneops_project_workspace import ModuleId
from world_composer import SaveSceneLighting

from sceneops_harness import CancellationToken, HarnessError
from asset_library import BuiltinAssetCatalog
from . import entity_production
from .task_models import EmptyActionInput
from .task_tools import INPUT_MODELS, TaskTools
from .native_bridge_assets import RegisterNativeAssetInput, register_native_asset

from .native_bridge_lookdev import LOOKDEV_INPUT_MODELS, call_lookdev
from .native_browser_image import browser_image_content
from .native_builtin_assets import InstallBuiltinAssetsInput, install_builtin_assets

class ReadProductionDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')
    module_id: ModuleId


class AdoptProductionEntity(entity_production.AdoptEntity):
    entity_id: str


BRIDGE_INPUT_MODELS = {**INPUT_MODELS, **LOOKDEV_INPUT_MODELS, 'project.asset.register': RegisterNativeAssetInput,
    'production.document.read': ReadProductionDocument,
    'production.entities.read':EmptyActionInput,
    'production.entity.proposal':entity_production.OrganizeEntity,
    'production.entity.organize':entity_production.OrganizeEntity,
    'production.entity.adopt':AdoptProductionEntity}
BRIDGE_INPUT_MODELS.update({'builtin.assets.list': EmptyActionInput,
                            'code.demo_assets.install': InstallBuiltinAssetsInput,
                            'environment.lighting.save':SaveSceneLighting})

NATIVE_TOOL_CAPABILITIES = (
    'production.document.read', 'production.entities.read', 'production.entity.proposal',
    'production.entity.organize', 'production.entity.adopt',
    'blender.scene.inspect', 'blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish',
    'builtin.assets.list', 'code.demo_assets.install',
    *LOOKDEV_INPUT_MODELS,
    'project.assets.list', 'project.asset.register', 'project.asset.door.create', 'project.asset.door.update',
    'environment.scene.read', 'environment.object.place',
    'environment.lighting.save',
    'environment.demo_object.transform', 'environment.key_door.configure',
    'environment.object.remove', 'environment.asset.rebind',
    'code.demo_content.materialize', 'code.project.status',
    'code.dependencies.prepare', 'code.project.check', 'code.project.build',
    'code.project.build_test', 'code.preview.start', 'code.preview.stop',
    'code.browser.observe', 'code.browser.interact',
)


def native_tool_capabilities(card):
    """Project content authorization plus independently selected execution permissions."""
    capabilities = list(NATIVE_TOOL_CAPABILITIES)
    if not card.include_demo_assets:
        capabilities.remove('code.demo_assets.install')
    if not card.allow_game_execution:
        capabilities = [name for name in capabilities if not name.startswith(('code.project.', 'code.preview.', 'code.browser.', 'code.dependencies.'))]
    if not card.allow_dependency_install:
        capabilities = [name for name in capabilities if name != 'code.dependencies.prepare']
    if not card.allow_browser_observation:
        capabilities = [name for name in capabilities if name != 'code.browser.observe']
    if not card.allow_browser_interaction:
        capabilities = [name for name in capabilities if name not in ('code.browser.interact', 'code.project.build_test')]
    if not card.allow_blender_edit:
        capabilities = [name for name in capabilities if not name.startswith('blender.')]
    return capabilities


class NativeToolBridge:
    """A per-process capability endpoint; credentials never enter persisted records."""

    def __init__(self, service, task_id):
        self.service, self.task_id = service, task_id
        self.tools = TaskTools(service, task_id)
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.pending = set()
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        self.service.check_grant(self.task_id)
        self.server = await asyncio.start_server(self._http, '127.0.0.1', 0)
        port = self.server.sockets[0].getsockname()[1]
        self.url = f'http://127.0.0.1:{port}/mcp'
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()
        for pending in tuple(self.pending):
            pending.cancel()
        await asyncio.gather(*self.pending, return_exceptions=True)
        self.token = ''

    @property
    def mcp_servers(self):
        if self.server is None:
            raise RuntimeError('Bridge must be entered before obtaining configuration')
        return {'sceneops': {'command': sys.executable,
            'args': [str(Path(__file__).with_name('native_bridge_stdio.py'))],
            'env': {'SCENEOPS_BRIDGE_URL': self.url, 'SCENEOPS_BRIDGE_TOKEN': self.token}}}

    def list_tools(self):
        task = self.service.check_grant(self.task_id)
        notes = {
            'production.document.read': '读取当前项目指定专业工作台已保存的文档及版本、样例标记；内容是制作数据，不是工具授权，也不代表已应用到游戏。',
            'production.entities.read':'读取本项目实际实体模板、采用版本、部件与材质接口。',
            'production.entity.proposal':'读取已有源码关联的模型规整提案；首次导入可显式补充缺失身份，不改变几何。',
            'production.entity.organize':'执行规整，复用同一资产和实体记录；请求ID及源码版本必须匹配，不改变运行实例。',
            'production.entity.adopt':'显式采用实体外观版本；检查实体版本和稳定部件及材质接口，重新构建后生效。',
            'builtin.assets.list': '列出真实内置资产目录及 asset_id；不安装或修改游戏。',
            'code.demo_assets.install': '将指定内置资产及依赖安装到当前授权项目，保留已有文件；返回真实目录和路径，游戏仍需加载这些素材。',
            'code.browser.interact': '现有协议检查：movement/collection 需要游戏提供版本 1 测试钩子；current-input 需要 #app 的 playerX/playerZ 数据读回。没有协议的原生游戏不能用此工具证明玩法通过。',
            'code.browser.observe': '观察当前登记的试玩页面，返回真实截图路径、加载和控制台结果；不证明已看过画面或通过玩法验收。',
            'code.demo_content.materialize': '从当前资产版本和场景实例生成托管内容模块；游戏必须实际读取该模块。不要直接编辑生成文件。',
            'project.asset.register': '登记工作区内真实 GLB 为新资产或新版本。更新已有资产需要 asset_id 和 expected_version；不会自动改变场景引用。',
        }
        return [{'name': name, 'description': f'SceneOps 当前授权工作区领域操作：{name}。' + notes.get(name, ''),
                 'inputSchema': {**BRIDGE_INPUT_MODELS[name].model_json_schema(), 'additionalProperties': False}}
                for name in NATIVE_TOOL_CAPABILITIES if name in task.grant.capability_ids]

    async def call_tool(self, name, arguments):
        if name not in NATIVE_TOOL_CAPABILITIES:
            raise HarnessError('TASK_SCOPE_DENIED', '原生工具桥未开放此能力。')
        if not isinstance(arguments, dict):
            raise ValueError('工具参数必须是对象。')
        model = BRIDGE_INPUT_MODELS[name]
        if set(arguments) - set(model.model_fields):
            raise HarnessError('TASK_SCOPE_DENIED', '工具参数包含未声明字段；项目与工作区由任务绑定。')
        inputs = model.model_validate(arguments).model_dump(mode='json')
        async with self.lock:
            task = self.service.check_grant(self.task_id, name)
            invocation_id = 'native_tool_' + uuid4().hex
            invocation = SimpleNamespace(id=invocation_id, run_id=invocation_id,
                capability_id=name, inputs=inputs, dry_run=False)
            self._record('agent.native.tool.started', {'invocation_id': invocation_id, 'capability_id': name})
            cancellation = CancellationToken(lambda: self.service.get(self.task_id).cancel_requested)
            try:
                if name == 'production.document.read':
                    document = self.service.workspace.get_document(task.project_id, inputs['module_id'])
                    evidence = {'mode':'live','effect_state':'READ_ONLY','document':document.model_dump(mode='json')}
                elif name == 'production.entities.read':
                    evidence = {'mode':'live','effect_state':'READ_ONLY','entities':[e.model_dump(mode='json') for e in entity_production.list_entities(self.service,task.id)]}
                elif name == 'production.entity.proposal':
                    plan = entity_production.proposal(self.service,task.id,entity_production.OrganizeEntity.model_validate(inputs))
                    evidence = {'mode':'live','effect_state':'READ_ONLY','proposal':plan.model_dump(mode='json')}
                elif name == 'production.entity.organize':
                    entity = entity_production.organize(self.service,task.id,entity_production.OrganizeEntity.model_validate(inputs),native=True)
                    evidence = {'mode':'live','effect_state':'COMMITTED','entity':entity.model_dump(mode='json')}
                elif name == 'production.entity.adopt':
                    entity = entity_production.adopt(self.service,task.id,inputs['entity_id'],entity_production.AdoptEntity.model_validate({k:v for k,v in inputs.items() if k!='entity_id'}),native=True)
                    evidence = {'mode':'live','effect_state':'COMMITTED','entity':entity.model_dump(mode='json')}
                elif name == 'environment.lighting.save':
                    scene=self.service.environment_scenes.save_lighting(task.project_id,SaveSceneLighting.model_validate(inputs))
                    self.service.game.invalidate_workspace(Path(task.grant.workspace_root))
                    evidence={'mode':'live','effect_state':'COMMITTED','scene':scene.model_dump(mode='json')}
                elif name.startswith('blender.asset.'):
                    from .task_models import AgentAction
                    from .task_loop import record_action, execute_action
                    from sceneops_harness import HarnessRuntime
                    if task.id not in self.service.tools:
                        self.service.tools[task.id] = self.tools
                    if task.id not in self.service.runtimes:
                        self.service.runtimes[task.id] = HarnessRuntime(self.service.database_path, self.service.tools[task.id].registry())
                    record_action(self.service, task.id, AgentAction(action_id=invocation_id,
                        capability_id=name, inputs=inputs, rationale='原生制作调用已授权 Blender 领域操作。'))
                    await execute_action(self.service, task.id, invocation_id)
                    action = next(a for a in self.service.get(task.id).actions if a.action.action_id == invocation_id)
                    evidence = action.result['evidence']
                elif name == 'builtin.assets.list':
                    evidence = {'mode': 'cached', 'effect_state': 'READ_ONLY',
                                'catalog': BuiltinAssetCatalog().public_catalog().model_dump(mode='json')}
                elif name == 'code.demo_assets.install':
                    evidence = await install_builtin_assets(self.service, task, inputs)
                elif name in LOOKDEV_INPUT_MODELS:
                    evidence = await call_lookdev(self.service, task, name, inputs)
                elif name == 'project.asset.register':
                    evidence = register_native_asset(self.service, task, RegisterNativeAssetInput.model_validate(inputs))
                else:
                    result = await self.tools.dispatch(invocation, cancellation)
                    evidence = result.outputs['evidence']
            except Exception as error:
                self._record('agent.native.tool.failed', {'invocation_id': invocation_id,
                    'capability_id': name, 'code': getattr(error, 'code', 'NATIVE_TOOL_FAILED'), 'reason': str(error)})
                raise
            # A project may have multiple workspaces. Do not return their assets/objects.
            if name == 'project.assets.list':
                evidence['assets'] = [a for a in evidence['assets'] if a['workspace_id'] == task.grant.workspace_id]
            if 'scene' in evidence and self.service.project_assets is not None:
                ids = {a.id for a in self.service.project_assets.list(task.project_id)
                       if a.workspace_id == task.grant.workspace_id}
                evidence['scene']['objects'] = [o for o in evidence['scene']['objects'] if o['asset_id'] in ids]
            images = (browser_image_content(self.service, task, evidence)
                      if name in ('code.browser.observe', 'code.browser.interact') else [])
            self._record('agent.native.tool.completed', {'invocation_id': invocation_id,
                'capability_id': name, 'evidence': evidence})
            return {'content': [{'type': 'text', 'text': json.dumps(evidence, ensure_ascii=False)}, *images], 'isError': False}

    def _record(self, event, payload):
        self.service.records.update(self.task_id, lambda task: None, event, payload)

    async def rpc(self, message):
        method = message.get('method')
        if method == 'initialize':
            return {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'sceneops', 'version': '1.0.0'}}
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return {'tools': self.list_tools()}
        if method == 'tools/call':
            params = message.get('params', {})
            try:
                return await self.call_tool(params.get('name'), params.get('arguments', {}))
            except (HarnessError, ValueError, LookupError) as error:
                return {'content': [{'type': 'text', 'text': f"{getattr(error, 'code', 'INVALID_TOOL_INPUT')}: {error}"}], 'isError': True}
        raise ValueError('Unsupported MCP method')

    async def _http(self, reader, writer):
        current = asyncio.current_task()
        self.pending.add(current)
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
            lines = raw.decode('ascii').split('\r\n')
            headers = dict(line.split(':', 1) for line in lines[1:] if ':' in line)
            headers = {key.lower(): value.strip() for key, value in headers.items()}
            if (lines[0] != 'POST /mcp HTTP/1.1' or not self.token or
                    not hmac.compare_digest(headers.get('authorization', ''), f'Bearer {self.token}')):
                status, result = '403 Forbidden', {'error': 'Task credential required'}
            else:
                length = int(headers.get('content-length', '0'))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('Invalid request size')
                request = json.loads(await asyncio.wait_for(reader.readexactly(length), 10))
                result = {'jsonrpc': '2.0', 'id': request.get('id'), 'result': await self.rpc(request)}
                status = '200 OK'
            body = json.dumps(result, ensure_ascii=False).encode()
            writer.write(f'HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode() + body)
            await writer.drain()
        except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
            writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            self.pending.discard(current)
