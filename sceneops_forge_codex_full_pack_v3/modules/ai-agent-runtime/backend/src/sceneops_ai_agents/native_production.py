"""One durable CLI conversation, task-scoped rounds and real workspace handoff."""
import json
from sceneops_harness import HarnessError
from .task_models import PrepareAgentTask, AuthorizeAgentTask
from .creation_brief import CreationBrief


async def execute_production(service, task, root, on_event, options, *, request_id):
    settings = service.provider.settings()
    configuration = {'provider': task.provider_id, 'model': task.provider_model,
        'reasoning_effort': getattr(settings, 'reasoning_effort', None),
        'permission_mode': task.grant.permission_mode,
        'timeout_seconds': options.get('timeout')}
    service.records.update(task.id, lambda current: current.observations.update(
        native_configuration=configuration), 'agent.native.configuration')
    from .native_bridge import NativeToolBridge
    from .native_skills import stage_native_skills
    from .workspace_sources import workspace_sources
    brief = CreationBrief.model_validate(task.observations['creation_brief'])
    if not brief.confirmed_at:
        raise HarnessError('CREATION_BRIEF_CONFIRMATION_REQUIRED', '制作简报尚未确认。')
    workspace_sources(service, task)
    staged_skills = stage_native_skills(root, {'codexcli': 'codex', 'openai-compatible': 'codex',
                               'codebuddycli': 'codebuddy'}[task.provider_id], brief.selected_skills)
    service.records.update(task.id, lambda current: current.observations.update(
        native_selected_skills=list(brief.selected_skills), native_loaded_skills=staged_skills),
        'agent.native.skills_staged')
    directory = root / '.sceneops'
    if directory.is_symlink():
        raise HarnessError('TASK_SCOPE_DENIED', '项目资料目录不能是符号链接。')
    directory.mkdir(exist_ok=True)
    path = directory / 'creation-brief.md'
    if path.is_symlink():
        raise HarnessError('TASK_SCOPE_DENIED', '制作简报不能写入符号链接。')
    path.write_text(brief.content, encoding='utf-8')
    session_id = task.observations.get('native_session_id')
    from .native_inputs import resolve_native_inputs
    inputs = resolve_native_inputs(root, [item['path'] for item in task.observations.get('native_inputs', [])])
    prompt = (task.goal + '\n这是同一制作会话的新一轮。先用原生计划能力更新实施计划，'
              '检查真实源码、现有修改和当前试玩状态，再做增量修改。'
              if session_id else '请读取 .sceneops/creation-brief.md 和 .sceneops/game-architecture.json。'
              '先用原生计划能力建立实施计划，将源码模块、状态流与场景组织逐项映射到已确认架构，'
              '不得替换该架构；如真实工程存在冲突，先明确报告冲突。然后使用你自己的 harness 完成可玩初版。')
    prompt += ('\n使用 SceneOps MCP 工具管理托管资产与场景，普通源码原生编辑。'
               '读取工程已有的 AGENTS.md、CODEBUDDY.md（如存在）及 ARCHITECTURE.md，遵循适用编辑约定。'
               '构建与浏览器观察使用提供的工具，依实际结果修复，不将自述作为验证。')
    from sceneops_project_workspace import PRODUCTION_DOMAINS
    prompt += ('\n项目固定七生产领域：' + '、'.join(f"{d['id']}={d['title']}" for d in PRODUCTION_DOMAINS)
               + '。具体游戏系统是跨领域功能包，保留已有功能包ID、会话和源码引用，不生成另一套顶层领域。'
               '已存在的模型与场景必须读取 project.assets.list 和 environment.scene.read 后复用。'
               '新增实际GLB通过project.asset.register登记，再用environment.object.place登记静态实例；'
               '游戏通过code.demo_content.materialize产物按稳定ID加载全部适用实例及其变换，不能只加载objects[0]或另造视觉副本。'
               '动态出生对象复用实体定义，保持行为与外观分离；源码几何未登记时明确标注，不声称工具可编辑。'
               '几何、材质、场景保存与运行采用分开，引用更新后重新构建验证。'
               '界面、声音、动画及玩法保留真实源码入口与资产引用；没有做的功能注明未实现，不用模拟面板表示完成。')
    prompt += ('\n本轮由用户确认并已加载的 SceneOps 制作技能：'
               + ('、'.join(brief.selected_skills) if brief.selected_skills else '无')
               + '。只按这些选择加载 SceneOps 制作技能；原生 harness 自带能力不受此列表限制。')
    from .context_projection import project_context_without_preparation
    if task.observations.get('production_card_context'):
        prompt += ('\n当前制作卡片及读取时的真实源码（项目数据，不是新增权限）：\n'
                   + json.dumps(project_context_without_preparation(task.observations['production_card_context']), ensure_ascii=False)
                   + '\n围绕本轮用户目标增量修改，先重读关联源码；保持同一工程和已选架构。'
                   '若需修改共享文件，说明影响和理由。完成后检查、构建并更新当前游戏试玩。')
    if inputs:
        prompt += ('\n本轮用户附件已登记在当前项目，按需读取，不要猜测其他本机路径：\n'
                   + '\n'.join(f"- {item['kind']}：{item['path']}" for item in inputs))
    supplied = {key: task.observations[key] for key in (
        'selected_prepared_assets', 'selected_builtin_assets', 'production_preparation_context', 'native_edit_target')
        if key in task.observations}
    if isinstance(supplied.get('production_preparation_context'), dict):
        supplied['production_preparation_context'] = service.preparation_without_memory(
            supplied['production_preparation_context'])
    memory = service.experience_context(task, call_key=f'native:{request_id}')
    if memory is not None:
        supplied['memory_context'] = memory
        prompt += '\n本次依据中的项目决定是当前读取版本；制作简报是本任务确认时的快照，纠正不会扩大本任务授权。'
    if supplied:
        prompt += '\n实际准备资料（失败项不可当作可用素材）：\n' + json.dumps(supplied, ensure_ascii=False)
    async def event(value):
        if value.get('type') == 'session_started':
            def save(current):
                current.observations['native_session_id'] = value['session_id']
                if value.get('cli_version'):
                    current.observations['native_cli_version'] = value['cli_version']
            service.records.update(task.id, save, 'agent.native.session_started', value)
        await on_event(value)
    try:
        async with NativeToolBridge(service, task.id) as bridge:
            result = await service.provider.execute_task(prompt, workspace_root=root,
                native_production=True, session_id=session_id,
                permission_mode=task.authorization_card.permission_mode,
                mcp_config={'mcpServers': bridge.mcp_servers}, on_event=event,
                reference_images=tuple(item['absolute_path'] for item in inputs if item['kind'] == 'image'),
                **{**options,
                   **({'expected_base_url': task.observations.get('native_api_route', {}).get('base_url')}
                      if task.provider_id == 'openai-compatible' else {})})
        service.records.update(task.id, lambda current: current.observations.update(
            native_session_id=result['session_id'], native_cli_version=result.get('cli_version')),
            'agent.native.round_completed')
        return result
    finally:
        workspace_sources(service, service.records.get(task.id), native_round=True)


def continue_production(service, task, request, *, build_only=False):
    if task.status in ('awaiting_authorization', 'queued', 'running', 'blocked', 'cancel_pending') or task.owner_pid:
        raise HarnessError('TASK_BUSY', '请等待当前制作停止后再续改。')
    session_id = task.observations.get('native_session_id')
    if not session_id:
        raise HarnessError('NATIVE_SESSION_MISSING', '没有可恢复的真实会话 ID；请检查中断记录，不能猜测最近会话。')
    settings = service.provider.settings()
    if settings.provider != task.provider_id:
        raise HarnessError('NATIVE_PROVIDER_CHANGED', '续改需要保持同一原生执行器；可在该执行器内切换模型。')
    for previous in service.list(task.project_id):
        if previous.observations.get('native_followup_request') == request.request_id:
            if (previous.goal != request.goal.strip()
                    or previous.observations.get('planning_card_id') != request.planning_card_id):
                raise HarnessError('TASK_SCOPE_DENIED', '同一续改请求不能更换目标。')
            return previous
    rounds = [item for item in service.list(task.project_id)
              if item.observations.get('native_session_id') == session_id]
    if any(item.created_at > task.created_at for item in rounds):
        raise HarnessError('NATIVE_ROUND_SUPERSEDED', '请从此会话的最新制作记录继续。')
    planning_context = None
    if request.planning_card_id:
        if service.production_card_context is None:
            raise HarnessError('PROJECT_DEMO_NOT_CONNECTED', '制作卡片服务未连接。')
        planning_context = service.production_card_context(task.project_id, request.planning_card_id)
        if planning_context['workspace_id'] != task.authorization_card.workspace_id:
            raise HarnessError('TASK_SCOPE_DENIED', '制作卡片不属于当前工程。')
    target_context = None
    if request.target is not None:
        from .demo_workbench import resolve_target
        _, selected = resolve_target(service, task, request.target)
        target_context = {'target': request.target.model_dump(mode='json'),
                          'source': selected.model_dump(mode='json')}
    card = task.authorization_card
    service.project_demo_workspace(task.project_id, card.workspace_id, expected_root=card.workspace_root)
    current_workspace = service.workspace.open_project_demo_workspace(task.project_id)
    if (current_workspace['workspace_root'], current_workspace['workspace_id']) != (card.workspace_root, card.workspace_id):
        raise HarnessError('TASK_SCOPE_DENIED', '当前工程登记已改变，不能将原会话恢复到其他工作区。')
    next_task = service.prepare(PrepareAgentTask(project_id=task.project_id,
        goal=request.goal, task_profile='project-demo-agent', execution_mode='agent-full-access',
        native_production=True, permission_mode=card.permission_mode,
        input_paths=request.input_paths,
        alignment_id=card.alignment_id, allow_game_execution=card.allow_game_execution,
        allow_dependency_install=card.allow_dependency_install,
        include_demo_assets=not build_only, allow_image_generation=card.allow_image_generation,
        allow_blender_edit=card.allow_blender_edit, allow_browser_observation=card.allow_browser_observation,
        allow_browser_interaction=card.allow_browser_interaction,
        allow_model_image_input=not build_only and (card.allow_browser_observation or card.allow_browser_interaction)))
    def inherit(current):
        current.observations.update(native_session_id=session_id,
            native_cli_version=task.observations.get('native_cli_version'),
            native_configuration=task.observations.get('native_configuration'),
            creation_brief=task.observations['creation_brief'], native_parent_task_id=task.id,
            native_followup_request=request.request_id, native_edit_target=target_context,
            native_delivery_only=build_only, planning_card_id=request.planning_card_id,
            production_card_context=planning_context)
    service.records.update(next_task.id, inherit, 'agent.native.continuation_prepared')
    return service.authorize(next_task.id, AuthorizeAgentTask(
        authorization_card_id=next_task.authorization_card.id,
        accept_unknown_cost=True, accept_full_access=card.permission_mode == 'full'))


async def rebuild_production(service, task_id):
    from .project_demo import materialize_project_demo
    from .native_project_delivery import deliver_native_project
    from .task_models import now
    task = service.check_grant(task_id, 'agent.task.execute')
    materialize_project_demo(service, task)
    delivery = await deliver_native_project(service, task_id)
    if delivery and delivery['run']['passed']:
        from sceneops_project_workspace import EntityStore
        current = service.get(task_id)
        candidate = service.game.snapshot(current).current_playable_candidate
        for entity in current.observations.get('demo_materialization', {}).get('entity_versions', []):
            EntityStore(service.workspace).record_build(current.project_id, current.grant.workspace_id,
                entity['id'], entity['revision'], entity['asset_version'], candidate.id)
    def finish(current):
        passed = bool(delivery and delivery['run']['passed'])
        current.status = 'review_required' if passed else 'failed'
        current.reason = '已更新实际试玩候选。' if passed else '构建失败，上一可玩候选保持不变。'
        current.finished_at = now()
        current.grant.revoked = True
    service.records.update(task_id, finish, 'agent.native.rebuilt')
