"""Task-owned typed capability bindings; no model-provided paths or programs."""
import asyncio
import math
from pathlib import Path
from sceneops_harness import CapabilityDefinition, CapabilityRegistry, CapabilityResult, HarnessError, RetryPolicy
from .task_models import (AgentAction, AssetInput, CreateCubeInput, CodexTaskInput, EmptyActionInput,
                          FinishInput, NextActionInput, ToolResult, now, PrototypeVerifyInput, CapabilityGapInput,
                          CodeReadInput, CodeWriteInput, HistoryReadInput, SceneTransformInput, BrowserInteractionRequest)
from .production_catalog import module_for
from .output_manifest import OUTPUT_MANIFEST_INSTRUCTION, register_output_manifest
from engine_unity import PrototypeSpec, PrototypePlayPayload


MUTATIONS = {"blender.asset.create", "blender.asset.export", "unity.asset.import", "codex.task.execute"}
MUTATIONS.update({'unity.prototype.compose', 'unity.prototype.play', 'unity.prototype.capture', 'unity.prototype.verify'})
MUTATIONS.add('code.file.write')
MUTATIONS.update({'code.dependencies.prepare', 'code.project.check', 'code.project.build',
                  'code.preview.start', 'code.preview.stop'})
MUTATIONS.add('environment.object.transform')
MUTATIONS.add('code.browser.observe')
MUTATIONS.update({'code.browser.interact', 'code.project.build_test'})
INPUT_MODELS = {"blender.asset.create": CreateCubeInput, "blender.asset.export": AssetInput,
    "unity.asset.import": AssetInput, "blender.scene.inspect": EmptyActionInput,
    "unity.scene.inspect": EmptyActionInput, "agent.finish": FinishInput,
    "codex.task.execute": CodexTaskInput}
INPUT_MODELS.update({'unity.prototype.compose': PrototypeSpec, 'unity.prototype.inspect': EmptyActionInput,
    'unity.prototype.play': PrototypePlayPayload, 'unity.prototype.capture': EmptyActionInput,
    'unity.prototype.verify': PrototypeVerifyInput})
INPUT_MODELS['agent.report_blocked'] = CapabilityGapInput
INPUT_MODELS['agent.history.read'] = HistoryReadInput
INPUT_MODELS['code.browser.observe'] = EmptyActionInput
INPUT_MODELS['code.browser.interact'] = BrowserInteractionRequest
INPUT_MODELS['code.project.build_test'] = EmptyActionInput
INPUT_MODELS.update({'code.workspace.inspect': EmptyActionInput,
                     'code.file.read': CodeReadInput, 'code.file.write': CodeWriteInput})
INPUT_MODELS.update({capability: EmptyActionInput for capability in
    ('code.dependencies.prepare', 'code.project.status', 'code.project.check', 'code.project.build',
     'code.preview.start', 'code.preview.stop')})
INPUT_MODELS.update({'project.assets.list': EmptyActionInput,
                     'environment.scene.read': EmptyActionInput,
                     'environment.object.transform': SceneTransformInput})


def contained(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root) or path.resolve() != path:
        raise HarnessError("TASK_SCOPE_DENIED", "路径超出任务工作区或包含符号链接，需要重新授权。")
    return path


class TaskTools:
    def __init__(self, service, task_id):
        self.service, self.task_id = service, task_id
        self.sessions = {}
        self.session_states = {}
        self.blocked_tool = None
        self.safe_failures = {}

    def registry(self):
        registry = CapabilityRegistry()
        registry.register(CapabilityDefinition(id="agent.next_action", provider_module_id="ai-agent-runtime",
            title="选择下一动作", mode="plan", execution_mode="live", timeout_seconds=125,
            metered=True, retry_policy=RetryPolicy(max_attempts=2)), self.service.agents.next_action,
            input_model=NextActionInput, output_model=AgentAction)
        for capability_id, model in INPUT_MODELS.items():
            if capability_id not in self.service.get(self.task_id).authorization_card.capability_ids:
                continue
            if capability_id == "codex.task.execute" and self.service.get(self.task_id).authorization_card.execution_mode != "codex-full-access":
                continue
            registry.register(CapabilityDefinition(id=capability_id, provider_module_id="ai-agent-runtime",
                title=capability_id, mode="mutate" if capability_id in MUTATIONS else "read",
                execution_mode="live", metered=capability_id == "codex.task.execute", estimated_cost_usd=None if capability_id == "codex.task.execute" else 0, risk="high" if capability_id == "codex.task.execute" else "low",
                supports_dry_run=capability_id in MUTATIONS, timeout_seconds=1200 if capability_id == "codex.task.execute" else 240,
                cross_system=capability_id != "agent.finish", retry_policy=RetryPolicy(max_attempts=1 if capability_id == "codex.task.execute" else 2)),
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

    async def session(self, tool):
        task = self.service.check_grant(self.task_id)
        if tool not in self.sessions:
            factory = self.service.blender_factory if tool == "blender" else self.service.unity_factory
            if factory is None:
                if tool == "blender":
                    from sceneops_blender import BlenderAgentSession
                    factory = BlenderAgentSession
                else:
                    from engine_unity import UnityAgentSession
                    factory = UnityAgentSession
            root = contained(task.grant.workspace_root, self.service.workspace_base)
            session = factory(root, self.service.state_base / task.id / tool)
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
            "expires_at": grant.expires_at.isoformat()}

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
            evidence = {'tool': 'project_assets', 'mode': 'live', 'effect_state': 'NONE',
                        'project_id': task.project_id,
                        'assets': [item.model_dump(mode='json') for item in assets]}
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
            from .code_workspace import read_source
            if invocation.capability_id == 'code.workspace.inspect':
                evidence = self.service.code.inspect(task)
            elif invocation.capability_id == 'code.file.read':
                content = read_source(task.grant.workspace_root, invocation.inputs['path'])
                evidence = {'tool': 'code', 'mode': 'live', 'path': invocation.inputs['path'],
                            'content': content, 'exists': content is not None}
            else:
                entry = next(item for item in task.actions if invocation.run_id in item.run_ids)
                evidence = self.service.code.write(task, entry)
        elif invocation.capability_id.startswith('unity.prototype.'):
            from .prototype_execution import dispatch_prototype
            evidence = await dispatch_prototype(self, invocation, cancellation)
        elif invocation.capability_id == "codex.task.execute":
            if task.grant.execution_mode != "codex-full-access" or invocation.inputs["goal"] != task.goal:
                raise HarnessError("TASK_SCOPE_DENIED", "Codex 完全权限仅接受已授权原目标。")
            root = contained(task.grant.workspace_root, self.service.workspace_base)
            if root.exists() and any(root.iterdir()) and not self.service.records.owns_workspace(task.project_id, root):
                raise HarnessError("TASK_SCOPE_DENIED", "完全权限任务不能重新接管非空工程或重放未知写入。")
            root.mkdir(parents=True, exist_ok=True)
            candidates = set()
            async def on_event(event):
                self.service.check_grant(self.task_id, invocation.capability_id)
                self.service.records.update(self.task_id, lambda current: current.observations.__setitem__('codex_activity', event),
                    "agent.codex.activity", {"run_id": invocation.run_id, "activity": event})
                for file in event.get("files", []):
                    if file.get("verification") == "exists":
                        candidates.add(file["path"])
            result = await self.service.provider.execute_task(task.goal, workspace_root=root,
                model=task.provider_model, authorized_scope=task.authorization_card.scope + '\n' + OUTPUT_MANIFEST_INSTRUCTION,
                timeout=max(0.01, (task.grant.expires_at - now()).total_seconds()), on_event=on_event,
                allow_image_generation=task.grant.allow_image_generation)
            cancellation.raise_if_cancelled()
            entry = next(item for item in self.service.get(task.id).actions if invocation.run_id in item.run_ids)
            artifacts = register_output_manifest(self.service, task, entry)
            registered_paths = {artifact.source_path for artifact in artifacts}
            self.register_artifacts(task, invocation, sorted(candidates - registered_paths - {'sceneops-outputs.json'}))
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
            tokens=None if invocation.capability_id == "codex.task.execute" else 0,
            cost_usd=None if invocation.capability_id == "codex.task.execute" else 0)

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
