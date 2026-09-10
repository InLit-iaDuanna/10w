"""Task-owned typed capability bindings; no model-provided paths or programs."""
import asyncio
import json
import math
from pathlib import Path
from uuid import uuid4
from sceneops_harness import CapabilityDefinition, CapabilityRegistry, CapabilityResult, HarnessError, RetryPolicy
from .task_models import (AgentAction, AssetInput, CreateCubeInput, CodexTaskInput, EmptyActionInput,
                          FinishInput, NextActionInput, ToolResult, now, PrototypeVerifyInput, CapabilityGapInput,
                          CodeReadInput, CodeWriteInput, HistoryReadInput, SceneTransformInput, BrowserInteractionRequest,
                          CreateDoorAssetInput, UpdateDoorAssetInput, PlaceDemoObjectInput,
                          ConfigureKeyDoorInput, RemoveDemoObjectInput, RebindDemoAssetInput)
from .production_catalog import module_for
from .output_manifest import OUTPUT_MANIFEST_INSTRUCTION, register_output_manifest
from engine_unity import PrototypeSpec, PrototypePlayPayload


MUTATIONS = {"blender.asset.create", "blender.asset.export", "unity.asset.import", "codex.task.execute", "agent.task.execute"}
MUTATIONS.update({'unity.prototype.compose', 'unity.prototype.play', 'unity.prototype.capture', 'unity.prototype.verify'})
MUTATIONS.update({'code.file.write', 'code.demo_assets.install', 'code.demo_content.materialize'})
MUTATIONS.update({'code.dependencies.prepare', 'code.project.check', 'code.project.build',
                  'code.preview.start', 'code.preview.stop'})
MUTATIONS.add('environment.object.transform')
MUTATIONS.add('code.browser.observe')
MUTATIONS.update({'code.browser.interact', 'code.project.build_test'})
MUTATIONS.update({'project.asset.door.create', 'project.asset.door.update',
                  'environment.object.place', 'environment.demo_object.transform',
                  'environment.key_door.configure', 'environment.object.remove', 'environment.asset.rebind'})
INPUT_MODELS = {"blender.asset.create": CreateCubeInput, "blender.asset.export": AssetInput,
    "unity.asset.import": AssetInput, "blender.scene.inspect": EmptyActionInput,
    "unity.scene.inspect": EmptyActionInput, "agent.finish": FinishInput,
    "codex.task.execute": CodexTaskInput, "agent.task.execute": CodexTaskInput}
INPUT_MODELS.update({'unity.prototype.compose': PrototypeSpec, 'unity.prototype.inspect': EmptyActionInput,
    'unity.prototype.play': PrototypePlayPayload, 'unity.prototype.capture': EmptyActionInput,
    'unity.prototype.verify': PrototypeVerifyInput})
INPUT_MODELS['agent.report_blocked'] = CapabilityGapInput
INPUT_MODELS['agent.history.read'] = HistoryReadInput
INPUT_MODELS['code.browser.observe'] = EmptyActionInput
INPUT_MODELS['code.browser.interact'] = BrowserInteractionRequest
INPUT_MODELS['code.project.build_test'] = EmptyActionInput
INPUT_MODELS['code.demo_assets.install'] = EmptyActionInput
INPUT_MODELS['code.demo_content.materialize'] = EmptyActionInput
INPUT_MODELS.update({'code.workspace.inspect': EmptyActionInput,
                     'code.file.read': CodeReadInput, 'code.file.write': CodeWriteInput})
INPUT_MODELS.update({capability: EmptyActionInput for capability in
    ('code.dependencies.prepare', 'code.project.status', 'code.project.check', 'code.project.build',
     'code.preview.start', 'code.preview.stop')})
INPUT_MODELS.update({'project.assets.list': EmptyActionInput,
                     'environment.scene.read': EmptyActionInput,
                     'environment.object.transform': SceneTransformInput})
INPUT_MODELS.update({
    'project.asset.door.create': CreateDoorAssetInput,
    'project.asset.door.update': UpdateDoorAssetInput,
    'environment.object.place': PlaceDemoObjectInput,
    'environment.demo_object.transform': SceneTransformInput,
    'environment.key_door.configure': ConfigureKeyDoorInput,
    'environment.object.remove': RemoveDemoObjectInput,
    'environment.asset.rebind': RebindDemoAssetInput,
})


from .blender_content_models import BlenderBeginInput, BlenderEditInput, BlenderPublishInput
INPUT_MODELS.update({'blender.asset.begin': BlenderBeginInput, 'blender.asset.edit': BlenderEditInput,
                     'blender.asset.publish': BlenderPublishInput})
MUTATIONS.update({'blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish', 'code.demo_runtime.upgrade'})
from .demo_runtime_upgrade import DemoRuntimeUpgradeInput
INPUT_MODELS['code.demo_runtime.preview'] = EmptyActionInput
INPUT_MODELS['code.demo_runtime.upgrade'] = DemoRuntimeUpgradeInput


def contained(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root) or path.resolve() != path:
        raise HarnessError("TASK_SCOPE_DENIED", "路径超出任务工作区或包含符号链接，需要重新授权。")
    return path


from .unity_content_models import (UnitySourceInput, UnityImportInput, UnityEditInput,
    UnityFocusInput, UnitySaveInput, UnityPlayInput)
INPUT_MODELS.update({'blender.asset.derive_unity': UnitySourceInput,
    'unity.content.import': UnityImportInput, 'unity.content.inspect': EmptyActionInput,
    'unity.content.edit': UnityEditInput, 'unity.content.focus': UnityFocusInput,
    'unity.content.save': UnitySaveInput, 'unity.content.play': UnityPlayInput})
MUTATIONS.update({'blender.asset.derive_unity','unity.content.import','unity.content.edit',
    'unity.content.focus','unity.content.save','unity.content.play'})


class TaskTools:
    def __init__(self, service, task_id):
        self.service, self.task_id = service, task_id
        self.sessions = {}
        self.session_states = {}
        self.blocked_tool = None
        self.safe_failures = {}

    def registry(self):
        registry = CapabilityRegistry()
        task = self.service.get(self.task_id)
        registry.register(CapabilityDefinition(id="agent.next_action", provider_module_id="ai-agent-runtime",
            title="选择下一动作", mode="plan", execution_mode="live", timeout_seconds=125,
            metered=True, retry_policy=RetryPolicy(max_attempts=2)), self.service.agents.next_action,
            input_model=NextActionInput, output_model=AgentAction)
        for capability_id, model in INPUT_MODELS.items():
            if capability_id not in task.authorization_card.capability_ids:
                continue
            if capability_id in ("codex.task.execute", "agent.task.execute") and task.authorization_card.execution_mode not in ("codex-full-access", "agent-full-access"):
                continue
            registry.register(CapabilityDefinition(id=capability_id, provider_module_id="ai-agent-runtime",
                title=capability_id, mode="mutate" if capability_id in MUTATIONS else "read",
                execution_mode="live", metered=capability_id in ("codex.task.execute", "agent.task.execute"), estimated_cost_usd=None if capability_id in ("codex.task.execute", "agent.task.execute") else 0, risk="high" if capability_id in ("codex.task.execute", "agent.task.execute") else "low",
                supports_dry_run=capability_id in MUTATIONS,
                timeout_seconds=task.authorization_card.max_duration_seconds if capability_id in ("codex.task.execute", "agent.task.execute") else 240,
                cross_system=capability_id != "agent.finish", retry_policy=RetryPolicy(max_attempts=1 if capability_id in ("codex.task.execute", "agent.task.execute") else 2)),
                self.dispatch, input_model=model, output_model=ToolResult)
        return registry

    async def sync(self, session, method, **kwargs):
        work = asyncio.create_task(asyncio.to_thread(getattr(session, method), **kwargs))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            # A cancelled thread does not stop a DCC. Stop the owned session, then join work.
            await asyncio.to_thread(session.stop)
            await asyncio.gather(work, return_exceptions=True)
            raise

    async def session(self, tool, *, headless=False, read_only=False):
        # Receipt inspection does not acquire project write ownership. The session
        # still validates its exact grant, workspace and expiry when binding.
        task = self.service.get(self.task_id) if read_only else self.service.check_grant(self.task_id)
        if (tool == 'blender' and tool in self.sessions
                and getattr(self.sessions[tool], 'headless', False) != headless):
            await self.sync(self.sessions[tool], 'stop')
            self.sessions.pop(tool)
            self.session_states.pop(tool, None)
        if tool not in self.sessions:
            factory = self.service.blender_factory if tool == "blender" else self.service.unity_factory
            configured_factory = factory is not None
            if factory is None:
                if tool == "blender":
                    from sceneops_blender import BlenderAgentSession
                    factory = BlenderAgentSession
                else:
                    from engine_unity import UnityAgentSession
                    factory = UnityAgentSession
            root = (Path(self.service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                expected_root=task.grant.workspace_root)['workspace_root'])
                if task.authorization_card.task_profile in ('project-demo', 'project-demo-agent')
                else contained(task.grant.workspace_root, self.service.workspace_base))
            grant_scoped_blender = (tool == 'blender' and task.authorization_card.task_profile in
                                    ('project-demo', 'project-demo-agent', 'unity-asset-edit'))
            state_root = self.service.state_base / task.id / tool
            if grant_scoped_blender:
                state_root = state_root / task.grant.id
            session = (factory(root, state_root, headless=headless, grant_content=grant_scoped_blender)
                if tool == 'blender' and not configured_factory else
                factory(root, state_root))
            session.bind_authorization(self.binding(task))
            self.sessions[tool] = session
            try:
                self.session_states[tool] = await self.sync(session, "start")
            except Exception as error:
                self.sessions.pop(tool, None)
                try:
                    await asyncio.to_thread(session.stop)
                except Exception as cleanup:
                    raise HarnessError("ACTION_UNCERTAIN", f"{error}; 会话清理失败：{cleanup}") from error
                code = getattr(error, "code", "")
                if "SCOPE" in code or "AUTH" in code:
                    raise HarnessError("TASK_SCOPE_DENIED", str(error)) from error
                self.blocked_tool = tool
                raise HarnessError("TOOL_BLOCKED", str(error)) from error
            self.blocked_tool = None
            if not read_only:
                self.service.check_grant(self.task_id)
        elif tool == 'unity':
            try:
                self.session_states[tool] = await self.sync(self.sessions[tool], 'start')
            except Exception as error:
                code = getattr(error, 'code', '')
                if 'SCOPE' in code or 'AUTH' in code:
                    raise HarnessError('TASK_SCOPE_DENIED', str(error)) from error
                self.blocked_tool = tool
                raise HarnessError('TOOL_BLOCKED', str(error)) from error
            self.blocked_tool = None
            self.service.check_grant(self.task_id)
        return self.sessions[tool]

    def validate_readback(self, task, tool, readback):
        if readback.get("mode") != "live":
            raise HarnessError("LIVE_READBACK_REQUIRED", "工具未返回当前 Live 读回。")
        if (readback.get("workspace_root") != task.grant.workspace_root
                or readback.get("session_id") != self.session_states[tool].get("session_id")
                or not readback.get("session_id")):
            raise HarnessError("TASK_SCOPE_DENIED", "工具读回不属于当前任务工作区或会话。")

    @staticmethod
    def binding(task):
        grant = task.grant
        return {"task_id": task.id, "grant_id": grant.id, "project_id": task.project_id,
            "workspace_root": grant.workspace_root, "allowed_capabilities": grant.capability_ids,
            "expires_at": grant.expires_at.isoformat() if grant.expires_at is not None else task.observations.get("native_blender_expires_at")}

    def authorization(self, invocation, tool):
        task = self.service.check_grant(self.task_id, invocation.capability_id)
        entry = next(item for item in task.actions if invocation.run_id in item.run_ids)
        if entry.change_set is None or not entry.approval_id:
            raise HarnessError("ACTION_APPROVAL_REQUIRED", "动作缺少由任务授权派生的 ChangeSet 或审批引用。")
        return {**self.binding(task), "action_id": entry.action.action_id,
            "capability_id": invocation.capability_id, "change_set_id": entry.change_set.change_set_id,
            "approval_id": entry.approval_id, "session_id": self.session_states[tool]["session_id"]}

    async def dispatch(self, invocation, cancellation):
        task = self.service.check_grant(self.task_id, invocation.capability_id)
        cancellation.raise_if_cancelled()
        if invocation.dry_run:
            evidence = {"dry_run": True, "proposed_values": invocation.inputs, "workspace_root": task.grant.workspace_root}
        elif invocation.capability_id.startswith('unity.content.') or invocation.capability_id=='blender.asset.derive_unity':
            from .unity_content import dispatch_content
            evidence = await dispatch_content(self, invocation, cancellation)
        elif invocation.capability_id == 'code.demo_runtime.preview':
            from .demo_runtime_upgrade import preview_runtime_upgrade
            evidence = preview_runtime_upgrade(self.service, task)
        elif invocation.capability_id == 'code.demo_runtime.upgrade':
            from .demo_runtime_upgrade import apply_runtime_upgrade
            evidence = apply_runtime_upgrade(self.service, task, invocation.inputs['preview_id'])
        elif invocation.capability_id in ('blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish'):
            from .blender_content import dispatch
            from sceneops_blender import BlenderCommandRejected
            try:
                evidence = await dispatch(self, invocation, cancellation)
            except BlenderCommandRejected as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'blender', 'mode': 'live', 'effect_state': 'NONE',
                    'outcome': 'not_dispatched', 'reason': str(error),
                }
                raise
        elif invocation.capability_id == 'agent.history.read':
            from .context_projection import read_history_reference
            reference = invocation.inputs['reference']
            evidence = {'tool': 'history', 'mode': 'live', 'effect_state': 'NONE',
                        'reference': reference, 'value': read_history_reference(task, reference)}
        elif invocation.capability_id == "agent.finish":
            evidence = await self.finish(task)
        elif invocation.capability_id == 'agent.report_blocked':
            evidence = {'tool': 'capability_gap', 'code': 'BLOCKED_CAPABILITY_GAP', **invocation.inputs}
        elif invocation.capability_id == 'project.assets.list':
            if self.service.project_assets is None:
                raise HarnessError('PROJECT_ASSETS_NOT_CONNECTED', '项目资产查询服务尚未连接。')
            assets = self.service.project_assets.list(task.project_id)
            if task.authorization_card.task_profile == 'project-demo-agent':
                assets = [item for item in assets if item.workspace_id == task.grant.workspace_id]
            evidence = {'tool': 'project_assets', 'mode': 'live', 'effect_state': 'NONE',
                        'project_id': task.project_id,
                        'workspace_id': task.grant.workspace_id,
                        'assets': [item.model_dump(mode='json') for item in assets]}
        elif invocation.capability_id in ('project.asset.door.create', 'project.asset.door.update'):
            if self.service.project_assets is None:
                raise HarnessError('PROJECT_ASSETS_NOT_CONNECTED', '项目资产服务尚未连接。')
            from asset_library import (DoorRecipe, ProjectAssetRegistration,
                                       ProjectAssetVersion, UpdateProjectAssetRecipeRequest)
            try:
                if invocation.capability_id == 'project.asset.door.create':
                    data = CreateDoorAssetInput.model_validate(invocation.inputs)
                    recipe = DoorRecipe(**data.recipe.model_dump(mode='python'))
                    existing = next((item for item in self.service.project_assets.list(task.project_id)
                                     if item.source_asset_id == data.source_asset_id), None)
                    if existing is not None:
                        latest = next(item for item in existing.versions
                                      if item.source_version == existing.current_version)
                        if existing.workspace_id != task.grant.workspace_id or latest.recipe != recipe:
                            raise HarnessError('ASSET_SOURCE_CONFLICT',
                                '同名源资产已存在且内容或工作区不同；请读取现有资产并明确更新。')
                        entry, created = existing, False
                    else:
                        version = ProjectAssetVersion(
                            source_version=1, asset_version_id='aver_' + uuid4().hex,
                            source_kind='procedural', dimensions_m=recipe.dimensions_m,
                            vertex_count=24, triangle_count=12, recipe=recipe,
                            operation='recipe-create')
                        saved = self.service.project_assets.register_version(ProjectAssetRegistration(
                            project_id=task.project_id, workspace_id=task.grant.workspace_id,
                            source_asset_id=data.source_asset_id, title=data.title,
                            source_type='generated', version=version))
                        entry, created = saved.entry, saved.version_created
                    evidence = {'tool': 'project_asset_source', 'mode': 'live',
                        'effect_state': 'COMMITTED' if created else 'NONE',
                        'operation': 'door-create', 'outcome': 'created' if created else 'already_present',
                        'project_id': task.project_id, 'workspace_id': task.grant.workspace_id,
                        'asset': entry.model_dump(mode='json'),
                        'source_locator': {'kind': 'asset-recipe', 'asset_id': entry.id,
                                           'source_version': entry.current_version}}
                else:
                    data = UpdateDoorAssetInput.model_validate(invocation.inputs)
                    current = self.service.project_assets.get(task.project_id, data.asset_id)
                    if current.workspace_id != task.grant.workspace_id:
                        raise HarnessError('TASK_SCOPE_DENIED', '资产不属于当前登记 Demo 工作区。')
                    recipe = DoorRecipe(**data.recipe.model_dump(mode='python'))
                    saved = self.service.project_assets.update_recipe(task.project_id, data.asset_id,
                        UpdateProjectAssetRecipeRequest(expected_version=data.expected_version,
                                                        recipe=recipe))
                    evidence = {'tool': 'project_asset_source', 'mode': 'live',
                        'effect_state': 'COMMITTED' if saved.version_created else 'NONE',
                        'operation': 'door-update',
                        'outcome': 'updated' if saved.version_created else 'already_present',
                        'project_id': task.project_id, 'workspace_id': task.grant.workspace_id,
                        'asset': saved.entry.model_dump(mode='json'),
                        'source_locator': {'kind': 'asset-recipe', 'asset_id': saved.entry.id,
                                           'source_version': saved.entry.current_version}}
            except HarnessError as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'project_asset_source', 'mode': 'live', 'effect_state': 'NONE',
                    'code': error.code, 'reason': str(error),
                    'project_id': task.project_id, 'workspace_id': task.grant.workspace_id}
                raise
            except (LookupError, ValueError) as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'project_asset_source', 'mode': 'live', 'effect_state': 'NONE',
                    'code': 'ASSET_SOURCE_CONFLICT', 'reason': str(error),
                    'project_id': task.project_id, 'workspace_id': task.grant.workspace_id}
                raise HarnessError('ASSET_SOURCE_CONFLICT', str(error)) from error
        elif invocation.capability_id == 'code.browser.observe':
            evidence = await self.service.observe_game(task.id, active_agent=True)
        elif invocation.capability_id == 'code.browser.interact':
            evidence = await self.service.observe_game(task.id, active_agent=True,
                interaction=BrowserInteractionRequest.model_validate(invocation.inputs))
        elif invocation.capability_id == 'environment.scene.read':
            if self.service.environment_scenes is None:
                raise HarnessError('ENVIRONMENT_SCENE_NOT_CONNECTED', '项目环境场景服务尚未连接。')
            try:
                scene = self.service.environment_scenes.get(task.project_id)
            except Exception as error:
                from world_composer import EnvironmentSceneError
                if isinstance(error, EnvironmentSceneError):
                    raise HarnessError(error.code, str(error)) from error
                raise
            evidence = {'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                        'scene': scene.model_dump(mode='json'),
                        'notice': '这是项目场景数据，不代表运行中的游戏状态。'}
        elif invocation.capability_id == 'environment.object.transform':
            if self.service.environment_scenes is None:
                raise HarnessError('ENVIRONMENT_SCENE_NOT_CONNECTED', '项目环境场景服务尚未连接。')
            from world_composer import (EnvironmentSceneError, EnvironmentTransform,
                                        TransformObjectRequest)
            data = SceneTransformInput.model_validate(invocation.inputs)
            try:
                before_scene = self.service.environment_scenes.get(task.project_id)
                before_object = next((item for item in before_scene.objects
                                      if item.id == data.object_id), None)
                if before_object is None:
                    raise EnvironmentSceneError('SCENE_OBJECT_NOT_FOUND', '场景对象不存在。', status_code=404)
                request = TransformObjectRequest(expected_version=data.expected_version,
                    transform=EnvironmentTransform(position_m=data.position_m,
                        rotation_y_deg=data.rotation_y_deg, scale=data.scale))
                self.service.environment_scenes.transform_object(task.project_id, data.object_id, request)
                readback = self.service.environment_scenes.get(task.project_id)
                changed = next((item for item in readback.objects if item.id == data.object_id), None)
                if changed is None or changed.transform != request.transform:
                    raise HarnessError('ACTION_UNCERTAIN', '场景写入后读回与请求不一致，需要人工核查。')
            except EnvironmentSceneError as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                    'code': error.code, 'reason': str(error), 'project_id': task.project_id,
                }
                raise HarnessError(error.code, str(error)) from error
            evidence = {'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'COMMITTED',
                        'operation': 'transform', 'project_id': task.project_id,
                        'before_version': before_scene.version, 'scene_version': readback.version,
                        'before_object': before_object.model_dump(mode='json'),
                        'object': changed.model_dump(mode='json'),
                        'notice': ('本任务唯一一次对象变换已写入并即时读回；下一步读取最新场景核对，'
                                   '不要再次执行相对变换。没有验证运行中的游戏。')}
        elif invocation.capability_id in ('environment.object.place',
                                           'environment.demo_object.transform',
                                           'environment.key_door.configure',
                                           'environment.object.remove', 'environment.asset.rebind'):
            if self.service.environment_scenes is None or self.service.project_assets is None:
                raise HarnessError('PROJECT_DEMO_NOT_CONNECTED', '项目资产或场景服务尚未连接。')
            from world_composer import (EnvironmentSceneError, EnvironmentTransform,
                ManualPlacementRequest, RemoveObjectRequest, TransformObjectRequest,
                UpdateKeyDoorBehaviorRequest, RebindAssetVersionRequest)
            try:
                before = self.service.environment_scenes.get(task.project_id)
                if invocation.capability_id == 'environment.asset.rebind':
                    data = RebindDemoAssetInput.model_validate(invocation.inputs)
                    asset = self.service.project_assets.get(task.project_id, data.asset_id)
                    if asset.workspace_id != task.grant.workspace_id:
                        raise HarnessError('TASK_SCOPE_DENIED', '共享资产不属于当前作品。')
                    rebound = self.service.environment_scenes.rebind_asset_version(task.project_id,
                        data.asset_id, RebindAssetVersionRequest(expected_version=data.expected_version,
                            from_asset_version=data.from_asset_version, to_asset_version=data.to_asset_version))
                    after, affected = rebound.scene, rebound.affected_object_ids
                    operation = 'rebind-asset'
                elif invocation.capability_id == 'environment.object.place':
                    data = PlaceDemoObjectInput.model_validate(invocation.inputs)
                    asset = self.service.project_assets.get(task.project_id, data.asset_id)
                    if asset.workspace_id != task.grant.workspace_id:
                        raise HarnessError('TASK_SCOPE_DENIED', '场景实例只能引用当前登记 Demo 工作区的资产。')
                    after = self.service.environment_scenes.add_object(task.project_id,
                        ManualPlacementRequest(expected_version=data.expected_version,
                            asset_id=data.asset_id, asset_version=data.asset_version,
                            position_m=data.position_m))
                    prior_ids = {item.id for item in before.objects}
                    changed = next(item for item in after.objects if item.id not in prior_ids)
                    operation, affected = 'place', [changed.id]
                elif invocation.capability_id == 'environment.demo_object.transform':
                    data = SceneTransformInput.model_validate(invocation.inputs)
                    current = next((item for item in before.objects if item.id == data.object_id), None)
                    if current is None:
                        raise EnvironmentSceneError('SCENE_OBJECT_NOT_FOUND', '场景对象不存在。')
                    asset = self.service.project_assets.get(task.project_id, current.asset_id)
                    if asset.workspace_id != task.grant.workspace_id:
                        raise HarnessError('TASK_SCOPE_DENIED', '场景对象不属于当前登记 Demo 工作区。')
                    after = self.service.environment_scenes.transform_object(task.project_id, data.object_id,
                        TransformObjectRequest(expected_version=data.expected_version,
                            transform=EnvironmentTransform(position_m=data.position_m,
                                rotation_y_deg=data.rotation_y_deg, scale=data.scale)))
                    operation, affected = 'transform', [data.object_id]
                elif invocation.capability_id == 'environment.key_door.configure':
                    data = ConfigureKeyDoorInput.model_validate(invocation.inputs)
                    current = next((item for item in before.objects if item.id == data.object_id), None)
                    if current is None:
                        raise EnvironmentSceneError('SCENE_OBJECT_NOT_FOUND', '场景对象不存在。')
                    object_asset = self.service.project_assets.get(task.project_id, current.asset_id)
                    key_asset = self.service.project_assets.get(task.project_id, data.required_key_asset_id)
                    if (object_asset.workspace_id != task.grant.workspace_id
                            or key_asset.workspace_id != task.grant.workspace_id):
                        raise HarnessError('TASK_SCOPE_DENIED', '门实例和钥匙资产必须属于当前登记 Demo 工作区。')
                    after = self.service.environment_scenes.update_key_door_behavior(task.project_id,
                        data.object_id, UpdateKeyDoorBehaviorRequest(
                            expected_version=data.expected_version,
                            required_key_asset_id=data.required_key_asset_id,
                            interaction_distance_m=data.interaction_distance_m,
                            open_angle_deg=data.open_angle_deg))
                    operation, affected = 'configure-key-door', [data.object_id]
                else:
                    data = RemoveDemoObjectInput.model_validate(invocation.inputs)
                    current = next((item for item in before.objects if item.id == data.object_id), None)
                    if current is None:
                        raise EnvironmentSceneError('SCENE_OBJECT_NOT_FOUND', '场景对象不存在。')
                    asset = self.service.project_assets.get(task.project_id, current.asset_id)
                    if asset.workspace_id != task.grant.workspace_id:
                        raise HarnessError('TASK_SCOPE_DENIED', '场景对象不属于当前登记 Demo 工作区。')
                    after = self.service.environment_scenes.remove_object(task.project_id, data.object_id,
                        RemoveObjectRequest(expected_version=data.expected_version))
                    operation, affected = 'remove', [data.object_id]
            except HarnessError as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                    'code': error.code, 'reason': str(error), 'project_id': task.project_id,
                    'workspace_id': task.grant.workspace_id}
                raise
            except EnvironmentSceneError as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                    'code': error.code, 'reason': str(error), 'project_id': task.project_id,
                    'workspace_id': task.grant.workspace_id}
                raise HarnessError(error.code, str(error)) from error
            except (LookupError, ValueError) as error:
                self.safe_failures[invocation.run_id] = {
                    'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                    'code': 'SCENE_SOURCE_CONFLICT', 'reason': str(error),
                    'project_id': task.project_id, 'workspace_id': task.grant.workspace_id}
                raise HarnessError('SCENE_SOURCE_CONFLICT', str(error)) from error
            evidence = {'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'COMMITTED',
                'operation': operation, 'project_id': task.project_id,
                'workspace_id': task.grant.workspace_id, 'before_version': before.version,
                'scene_version': after.version, 'affected_object_ids': affected,
                'scene': after.model_dump(mode='json'),
                'source_locator': {'kind': 'scene', 'scene_id': after.scene_id,
                                   'scene_version': after.version}}
        elif invocation.capability_id == 'code.demo_assets.install':
            report = self.service.workspace.install_demo_assets(task.project_id, task.grant.card_id)
            preparation = (task.observations.get('production_preparation_context') or
                           task.observations.get('production_preparation'))
            recommendation = preparation.get('recommendation') if isinstance(preparation, dict) else None
            selected = []
            if isinstance(recommendation, dict) and isinstance(recommendation.get('assets'), list):
                for item in recommendation['assets']:
                    candidate_id = item.get('candidate_id') if isinstance(item, dict) else None
                    if isinstance(candidate_id, str) and candidate_id.startswith('builtin:'):
                        selected.append({'asset_id': candidate_id.removeprefix('builtin:'),
                                         'purpose': item.get('purpose'), 'reason': item.get('reason')})
            if isinstance(preparation, dict) and self.service.builtin_asset_install_selected is not None:
                pack = self.service.builtin_asset_install_selected(
                    task.project_id, task.grant.card_id, selected)
                report['installed_files'] += pack['installed_files']
                report['preserved_files'] += pack['preserved_files']
                report['selected_builtin_assets'] = pack
                if task.authorization_card.task_profile == 'card-development':
                    def record_selected_assets(current):
                        aggregate = current.observations.get('selected_prepared_assets')
                        if not isinstance(aggregate, dict):
                            aggregate = {'sources': {}, 'entries': [], 'materialization': [],
                                'installed_files': [], 'preserved_files': [], 'catalog_paths': [],
                                'provision_failures': []}
                        sources = aggregate.setdefault('sources', {})
                        sources['builtin'] = pack
                        aggregate['entries'] = [
                            *[item for item in aggregate.get('entries', [])
                              if item.get('project_asset_id')],
                            *pack.get('catalog', {}).get('entries', []),
                        ]
                        aggregate['materialization'] = [
                            *[item for item in aggregate.get('materialization', [])
                              if str(item.get('candidate_id', '')).startswith('project:')],
                            *pack.get('materialization', []),
                        ]
                        aggregate['installed_files'] = list(dict.fromkeys([
                            *aggregate.get('installed_files', []), *pack.get('installed_files', [])]))
                        aggregate['preserved_files'] = list(dict.fromkeys([
                            *aggregate.get('preserved_files', []), *pack.get('preserved_files', [])]))
                        if pack.get('catalog_path'):
                            aggregate['catalog_paths'] = list(dict.fromkeys([
                                *aggregate.get('catalog_paths', []), pack['catalog_path']]))
                        current.observations['selected_prepared_assets'] = aggregate
                        current.observations['selected_builtin_assets'] = pack
                        for key in ('production_preparation', 'production_preparation_context'):
                            prepared = current.observations.get(key)
                            if isinstance(prepared, dict):
                                prepared['materialization'] = aggregate['materialization']
                    self.service.records.update(task.id, record_selected_assets,
                        'agent.production_assets.provided',
                        {'catalog_paths': [pack.get('catalog_path')],
                         'installed_count': len(pack.get('installed_files', [])),
                         'selected_count': len(selected), 'failure_count': 0})
            elif self.service.builtin_asset_install is not None:
                # Compatibility for tasks created before production preparation.
                pack = self.service.builtin_asset_install(task.project_id, task.grant.card_id)
                report['installed_files'] += pack['installed_files']
                report['preserved_files'] += pack['preserved_files']
                report['builtin_scenes'] = pack
            evidence = {'tool': 'demo_assets', 'mode': 'live', **report,
                        'effect_state': 'COMMITTED' if report['installed_files'] else 'NONE',
                        'outcome': 'installed' if report['installed_files'] else 'already_present'}
        elif invocation.capability_id == 'code.demo_content.materialize':
            from .project_demo import materialize_project_demo
            evidence = materialize_project_demo(self.service, task)
        elif invocation.capability_id == 'code.project.status':
            snapshot = self.service.game.snapshot(task)
            evidence = {'tool': 'game_project', 'mode': 'live', 'effect_state': 'NONE',
                        'project': snapshot.model_dump(mode='json')}
        elif invocation.capability_id in ('code.dependencies.prepare', 'code.project.check', 'code.project.build', 'code.project.build_test',
                                          'code.preview.start', 'code.preview.stop'):
            if invocation.capability_id == 'code.dependencies.prepare' and not task.grant.allow_dependency_install:
                raise HarnessError('DEPENDENCY_INSTALL_NOT_AUTHORIZED', '此任务未授权准备工程依赖。')
            if invocation.capability_id == 'code.project.build_test':
                self.service.browser_task(task.id, interaction=True)
            operation = {'code.dependencies.prepare': 'prepare', 'code.project.check': 'check',
                         'code.project.build': 'build', 'code.project.build_test': 'build_test', 'code.preview.start': 'preview_start',
                         'code.preview.stop': 'preview_stop'}[invocation.capability_id]
            evidence = await self.service.game.execute(task, operation)
        elif invocation.capability_id.startswith('code.'):
            from .code_workspace import read_source, task_source_path
            if invocation.capability_id == 'code.workspace.inspect':
                evidence = self.service.code.inspect(task)
            elif invocation.capability_id == 'code.file.read':
                task_source_path(task, invocation.inputs['path'])
                content = read_source(task.grant.workspace_root, invocation.inputs['path'])
                evidence = {'tool': 'code', 'mode': 'live', 'path': invocation.inputs['path'],
                            'content': content, 'exists': content is not None,
                            'project_id': task.project_id,
                            'workspace_id': task.grant.workspace_id}
            else:
                entry = next(item for item in task.actions if invocation.run_id in item.run_ids)
                evidence = self.service.code.write(task, entry)
        elif invocation.capability_id.startswith('unity.prototype.'):
            from .prototype_execution import dispatch_prototype
            evidence = await dispatch_prototype(self, invocation, cancellation)
        elif invocation.capability_id in ("codex.task.execute", "agent.task.execute"):
            if task.grant.execution_mode not in ("codex-full-access", "agent-full-access") or invocation.inputs["goal"] != task.goal:
                raise HarnessError("TASK_SCOPE_DENIED", "Codex 完全权限仅接受已授权原目标。")
            card_work = task.authorization_card.task_profile == 'card-development'
            if card_work:
                self.service.card_workspace(task.project_id, task.grant.card_id,
                    expected_root=task.grant.workspace_root, expected_branch=task.grant.branch)
            export_work = task.authorization_card.task_profile == 'project-export-agent'
            project_work = task.authorization_card.task_profile == 'project-demo-agent'
            if project_work:
                self.service.project_demo_workspace(task.project_id, task.grant.workspace_id,
                    expected_root=task.grant.workspace_root)
            root = Path(task.grant.workspace_root) if card_work or project_work or export_work else contained(task.grant.workspace_root, self.service.workspace_base)
            if not card_work and not project_work and not export_work and root.exists() and any(root.iterdir()) and not self.service.records.owns_workspace(task.project_id, root):
                raise HarnessError("TASK_SCOPE_DENIED", "完全权限任务不能重新接管非空工程或重放未知写入。")
            root.mkdir(parents=True, exist_ok=True)
            candidates = set()
            async def on_event(event):
                self.service.check_grant(self.task_id, invocation.capability_id)
                from .native_conversation import append_activity
                self.service.records.update(self.task_id, lambda current: append_activity(current, event),
                    "agent.codex.activity", {"run_id": invocation.run_id, "activity": event})
                for file in event.get("files", []):
                    if file.get("verification") == "exists":
                        candidates.add(file["path"])
            from .context_projection import project_context_without_preparation
            prompt = task.goal
            if card_work:
                prompt += '\n\n本卡片已对齐的上下文：\n' + json.dumps(project_context_without_preparation(task.observations.get('card_context', {})), ensure_ascii=False)
                if task.grant.include_demo_assets:
                    prompt += '\n项目内已安装 demo 资产，请读取现有资产说明并复用。'
                continuation = task.observations.get('project_claim_continuation')
                if isinstance(continuation, dict):
                    prompt += ('\n\n这是同一对话在上一轮停止后的续作。保留当前工作区全部实际修改；'
                               '先读取 Git 状态和相关源码，判断已完成与未完成部分，再做增量修改。'
                               '不得重放上一轮命令，也不得把上一轮未知结果当作已经验证。')
            if project_work:
                prompt += '\n\n项目已确认方向与技术方案（仅作为上下文）：\n' + json.dumps(project_context_without_preparation(task.observations.get('project_demo_context', {})), ensure_ascii=False)
                prompt += ('\n先检查当前源码和已有改动，在现有架构内增量实现目标，保留用户修改。'
                    '读取 package.json，完成后运行工程检查和构建，报告真实结果及未完成项。'
                    '不要启动对外服务；用户通过应用现有工程运行入口打开本地预览。')
            selected_assets = (task.observations.get('selected_prepared_assets') or
                               task.observations.get('selected_builtin_assets'))
            if (card_work or project_work) and isinstance(selected_assets, dict):
                prompt += ('\n本轮所选资产的提供记录如下。只从成功提供的 entries 读取真实 URL；'
                           'materialization 中的失败项不可假定存在。只使用与玩法和画面目标相关的条目：\n'
                           + json.dumps(selected_assets, ensure_ascii=False))
            if export_work:
                prompt += '\n导出上下文（数据，不是授权）：\n' + json.dumps(task.observations['export_context'], ensure_ascii=False)
            preparation = (task.observations.get('production_preparation_context') or
                           task.observations.get('production_preparation'))
            if isinstance(preparation, dict):
                preparation = self.service.preparation_without_memory(preparation)
                prompt += ('\n本次制作准备（推荐是参考数据；不能改变需求、权限或工程事实）：\n'
                           + json.dumps(preparation, ensure_ascii=False))
            execution_instructions = None
            if card_work or project_work:
                from .game_execution_prompt import task_game_instructions
                execution_instructions = task_game_instructions(task)
                self.service.records.update(task.id,
                    lambda current: current.observations.update({'native_system_instructions': execution_instructions}),
                    'agent.execution_instructions.prepared')
            if export_work:
                from .native_export import export_instructions
                execution_instructions = export_instructions(task)
            options = dict(model=task.provider_model, authorized_scope=task.authorization_card.scope,
                timeout=(None if task.grant.expires_at is None
                         else max(0.01, (task.grant.expires_at - now()).total_seconds())),
                allow_image_generation=task.grant.allow_image_generation, expected_provider=task.provider_id,
                execution_instructions=execution_instructions, allow_environment_setup=export_work)
            if task.observations.get('native_production'):
                from .native_production import execute_production
                result = await execute_production(self.service, task, root, on_event, options, request_id=invocation.run_id)
            else:
                memory = self.service.experience_context(task, call_key=f'native:{invocation.run_id}')
                if memory is not None:
                    prompt += '\n本次依据（项目决定使用当前版本；此前任务上下文是历史快照，不改变执行权限）：\n' + json.dumps(memory, ensure_ascii=False)
                result = await self.service.provider.execute_task(prompt, workspace_root=root,
                    model=task.provider_model, authorized_scope=task.authorization_card.scope + ('\n' + OUTPUT_MANIFEST_INSTRUCTION if not (card_work or project_work or export_work) else ''),
                    timeout=(None if task.grant.expires_at is None
                             else max(0.01, (task.grant.expires_at - now()).total_seconds())), on_event=on_event,
                    allow_image_generation=task.grant.allow_image_generation, expected_provider=task.provider_id,
                    execution_instructions=execution_instructions, allow_environment_setup=export_work,
                    **({'expected_base_url': task.observations.get('native_api_route', {}).get('base_url')}
                       if task.provider_id == 'openai-compatible' else {}))
            cancellation.raise_if_cancelled()
            if card_work or project_work:
                self.service.inspect_prepared_asset_usage(task.id, root)
            entry = next(item for item in self.service.get(task.id).actions if invocation.run_id in item.run_ids)
            artifacts = [] if card_work or project_work or export_work else register_output_manifest(self.service, task, entry)
            registered_paths = {artifact.source_path for artifact in artifacts}
            if not export_work:
                self.register_artifacts(task, invocation, sorted(candidates - registered_paths - {'sceneops-outputs.json'}))
            if project_work:
                if task.observations.get('native_production'):
                    from .project_demo import materialize_project_demo
                    materialize_project_demo(self.service, self.service.check_grant(task.id))
                from .native_project_delivery import deliver_native_project
                delivery = await deliver_native_project(self.service, task.id)
                self.service.record_prepared_asset_runtime_status(task.id, delivery)
            evidence = {"tool": "codex", "mode": "live", "verified": False,
                "workspace_root": str(root), "result": result,
                "notice": "CLI 已结束；这些是模型自述和执行事件摘要，未独立验收业务结果。"}
        else:
            tool = invocation.capability_id.split(".")[0]
            session = await self.session(tool)
            self.service.check_grant(self.task_id, invocation.capability_id)
            if invocation.capability_id.endswith(".inspect"):
                readback = await self.sync(session, "inspect")
                evidence = {"tool": tool, "readback": readback}
            else:
                entry = next(item for item in task.actions if invocation.run_id in item.run_ids)
                auth = self.authorization(invocation, tool)
                if invocation.capability_id == "blender.asset.create":
                    result = await self.sync(session, "create_asset", request_id=entry.request_id,
                                            **invocation.inputs, authorization=auth)
                elif invocation.capability_id == "blender.asset.export":
                    result = await self.sync(session, "export_asset", request_id=entry.request_id,
                                            **invocation.inputs, authorization=auth)
                else:
                    exported = self.export_for(task, invocation.inputs["asset_id"])
                    spec = self.spec_for(task, invocation.inputs["asset_id"])
                    result = await self.sync(session, "import_asset", request_id=entry.request_id,
                        asset_id=spec.asset_id, sceneops_id=spec.sceneops_id,
                        fbx_path=str(contained(exported["fbx_path"], task.grant.workspace_root)),
                        manifest_path=str(contained(exported["manifest_path"], task.grant.workspace_root)), authorization=auth)
                readback = await self.sync(session, "inspect")
                evidence = {"tool": tool, "result": result, "readback": readback}
            self.validate_readback(task, tool, readback)
            if invocation.capability_id in MUTATIONS:
                paths = [value for key, value in evidence.get("result", {}).items()
                         if key in ("blend_path", "fbx_path", "glb_path", "manifest_path", "scene_path") and isinstance(value, str)]
                self.register_artifacts(task, invocation, paths)
        return CapabilityResult(execution_mode="live", outputs={"evidence": evidence},
            evidence_refs=[f"task-action:{invocation.id}"],
            tokens=None if invocation.capability_id in ("codex.task.execute", "agent.task.execute") else 0,
            cost_usd=None if invocation.capability_id in ("codex.task.execute", "agent.task.execute") else 0)

    def register_artifacts(self, task, invocation, paths):
        entry = next(item for item in self.service.get(task.id).actions if invocation.run_id in item.run_ids)
        artifacts = []
        for path in paths:
            try:
                artifacts.append(self.service.production.record_artifact(task, f"{task.id}:{entry.action.action_id}",
                    module_for(invocation.capability_id), Path(path)))
            except HarnessError as error:
                # File registration is not the write itself: retain its real result,
                # and expose failed registration without retrying the external action.
                self.service.records.update(task.id, lambda current: None, "production.artifact.rejected",
                    {"run_id": invocation.run_id, "code": error.code})
        return artifacts

    @staticmethod
    def spec_for(task, asset_id):
        matches = [item for item in task.actions if item.action.capability_id == "blender.asset.create"
                   and item.action.inputs.get("asset_id") == asset_id and item.state == "succeeded"]
        if len(matches) != 1:
            raise HarnessError("ASSET_NOT_CREATED", "需要先在此任务成功创建唯一对应资产。")
        return CreateCubeInput.model_validate(matches[0].action.inputs)

    @staticmethod
    def export_for(task, asset_id):
        matches = [item for item in task.actions if item.action.capability_id == "blender.asset.export"
                   and item.action.inputs.get("asset_id") == asset_id and item.state == "succeeded"]
        if not matches:
            raise HarnessError("ASSET_NOT_EXPORTED", "此资产还没有本任务成功导出的 FBX。")
        return matches[-1].result["evidence"]["result"]

    async def finish(self, task):
        task = self.service.check_grant(self.task_id, "agent.finish")
        if task.authorization_card.task_profile == 'unity-asset-edit':
            from .unity_content import finish_content
            return await finish_content(self, task)
        if task.authorization_card.task_profile == 'environment-scene':
            if self.service.environment_scenes is None:
                raise HarnessError('ENVIRONMENT_SCENE_NOT_CONNECTED', '项目环境场景服务尚未连接。')
            transforms = [entry for entry in task.actions
                if entry.action.capability_id == 'environment.object.transform'
                and entry.state == 'succeeded']
            if not transforms:
                raise HarnessError('VERIFICATION_INCOMPLETE', '当前任务还没有成功修改已授权场景对象。')
            latest = transforms[-1]
            latest_index = task.actions.index(latest)
            readbacks = [entry for entry in task.actions[latest_index + 1:]
                if entry.action.capability_id == 'environment.scene.read'
                and entry.state == 'succeeded']
            if not readbacks:
                raise HarnessError('VERIFICATION_INCOMPLETE', '场景修改后必须再次读取最新场景再完成。')
            scene = self.service.environment_scenes.get(task.project_id)
            data = SceneTransformInput.model_validate(latest.action.inputs)
            changed = next((item for item in scene.objects if item.id == data.object_id), None)
            expected = (tuple(data.position_m), data.rotation_y_deg, data.scale)
            actual = ((tuple(changed.transform.position_m), changed.transform.rotation_y_deg,
                       changed.transform.scale) if changed else None)
            if actual != expected:
                raise HarnessError('VERIFICATION_INCOMPLETE',
                    '当前场景已变化或对象不存在；历史结果不能代替最新场景状态。')
            return {'tool': 'environment_scene', 'mode': 'live', 'effect_state': 'NONE',
                'delivery_status': 'scene_updated', 'project_id': task.project_id,
                'scene_version': scene.version, 'object': changed.model_dump(mode='json'),
                'verified': True, 'game_runtime_updated': False,
                'summary': '项目场景对象变换已写入并从最新场景回读；未验证运行中的游戏。'}
        if task.authorization_card.task_profile == 'card-development':
            code = self.service.code.finish(task)
            if not task.authorization_card.allow_game_execution:
                return code
            return {**code, **self.service.finish_game(task)}
        if task.authorization_card.task_profile == 'project-demo-agent':
            start = task.observations.get('active_goal_action_start', 0)
            if not isinstance(start, int) or start < 0 or start > len(task.actions):
                raise HarnessError('VERIFICATION_INCOMPLETE', '当前追加目标的动作边界不可读取。')
            current_actions = task.actions[start:]
            content_capabilities = {'code.demo_runtime.upgrade', 'blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish', 'project.asset.door.create', 'project.asset.door.update',
                'environment.object.place', 'environment.demo_object.transform',
                'environment.key_door.configure', 'environment.object.remove', 'environment.asset.rebind'}
            source_actions = [entry for entry in current_actions
                if entry.state == 'succeeded' and entry.action.capability_id in
                   (content_capabilities | {'code.file.write'})
                and (entry.effect_state == 'COMMITTED')]
            if not source_actions:
                raise HarnessError('VERIFICATION_INCOMPLETE',
                    '当前目标还没有保存并回读任何真实内容源或普通游戏源码。')
            materializations = [entry for entry in current_actions
                if entry.state == 'succeeded'
                and entry.action.capability_id == 'code.demo_content.materialize']
            last_content = max((task.actions.index(entry) for entry in source_actions
                                if entry.action.capability_id in content_capabilities), default=-1)
            if not materializations or task.actions.index(materializations[-1]) < last_content:
                raise HarnessError('VERIFICATION_INCOMPLETE',
                    '当前资产或场景源改变后尚未重新物化 Demo 内容。')
            if task.authorization_card.allow_browser_observation:
                from .context_projection import project_game_diagnostics
                if project_game_diagnostics(task)['latest'].get('evidence_status') != 'pass':
                    raise HarnessError('VERIFICATION_INCOMPLETE',
                        '当前构建还没有成功的浏览器加载或受控输入证据。')
            code_writes = [entry for entry in current_actions
                           if entry.action.capability_id == 'code.file.write'
                           and entry.state == 'succeeded']
            code = self.service.code.finish(task) if code_writes else {
                'tool': 'code', 'mode': 'live', 'content_verified': True,
                'changed_files': [], 'project_id': task.project_id,
                'workspace_id': task.grant.workspace_id}
            game = self.service.finish_game(task)
            locators = []
            for entry in source_actions:
                evidence = (entry.result or {}).get('evidence', {})
                locator = evidence.get('source_locator') if isinstance(evidence, dict) else None
                if isinstance(locator, dict):
                    locators.append(locator)
                elif entry.action.capability_id == 'code.file.write':
                    locators.append({'kind': 'project-source', 'path': entry.action.inputs['path']})
            return {**code, **game, 'editable_sources': locators,
                    'workspace_id': task.grant.workspace_id,
                    'summary': game['summary']}
        if task.authorization_card.task_profile == 'survival-prototype' or any(item.action.capability_id == 'unity.prototype.compose' for item in task.actions):
            from .prototype_execution import finish_prototype
            return await finish_prototype(self, task)
        for tool, required in (("blender", "blender.asset.export"), ("unity", "unity.asset.import")):
            if not any(entry.action.capability_id == required and entry.state == "succeeded" for entry in task.actions):
                raise HarnessError("VERIFICATION_INCOMPLETE", "完成任务需要本任务已成功导出和导入的持久记录。")
            if tool not in self.sessions:
                # Rebind the original unexpired grant. Adapter start reconnects its own
                # session or opens the saved task project; no production action is replayed.
                await self.session(tool)
                self.service.records.update(self.task_id, lambda current: None,
                    "agent.session.restored_for_verification", {"tool": tool, "grant_id": task.grant.id})
        blender = await self.sync(self.sessions["blender"], "inspect")
        unity = await self.sync(self.sessions["unity"], "inspect")
        self.validate_readback(task, "blender", blender)
        self.validate_readback(task, "unity", unity)
        if "errors" not in unity or unity["errors"]:
            raise HarnessError("UNITY_CONSOLE_NOT_VERIFIED", "Unity console 存在错误或未提供错误读回。")
        created = [item for item in task.actions if item.action.capability_id == "blender.asset.create" and item.state == "succeeded"]
        if not created:
            raise HarnessError("VERIFICATION_INCOMPLETE", "没有实际创建的资产。")
        for entry in created:
            spec = CreateCubeInput.model_validate(entry.action.inputs)
            self.export_for(task, spec.asset_id)
            for evidence, dimensions, key in ((blender, spec.dimensions_m, "dimensions_m"),
                (unity, (spec.dimensions_m[0], spec.dimensions_m[2], spec.dimensions_m[1]), "dimensions_meters")):
                objects = [obj for obj in evidence.get("objects", []) if obj.get("sceneops_id") == spec.sceneops_id
                           and obj.get("asset_id") == spec.asset_id]
                if len(objects) != 1 or len(objects[0].get(key, [])) != 3:
                    raise HarnessError("IDENTITY_READBACK_FAILED", "两端对象身份或尺寸读回不完整。")
                if any(not math.isclose(float(a), b, rel_tol=0.001, abs_tol=0.001) for a, b in zip(objects[0][key], dimensions)):
                    raise HarnessError("DIMENSIONS_READBACK_FAILED", "两端尺寸不符合米制坐标变换后的目标。")
                if evidence is blender and objects[0].get("name") != spec.name:
                    raise HarnessError("NAME_READBACK_FAILED", "Blender 名称与用户动作规格不一致。")
        return {"verified": True, "blender": blender, "unity": unity, "summary": "已读回两端身份、尺寸及 Unity console。"}

    async def stop(self):
        sessions = list(self.sessions.items())
        results = await asyncio.gather(*(asyncio.to_thread(session.stop) for _, session in sessions), return_exceptions=True)
        for (tool, session), result in zip(sessions, results):
            if not isinstance(result, BaseException) and self.sessions.get(tool) is session:
                self.sessions.pop(tool, None)
                self.session_states.pop(tool, None)
        return results

    def has_connected_sessions(self):
        return bool(self.sessions.keys() & self.session_states.keys())
