"""Server-bound export sessions using the ordinary native task lifecycle."""
import asyncio
from pathlib import Path

from sceneops_harness import HarnessError
from .export_knowledge import load_export_knowledge
from .task_models import AgentTaskRecord, AuthorizationCard, AuthorizeAgentTask

EXPORT_SCOPE = ('仅此项目已登记导出工作区的打包和验证；允许从官方或可信包管理源安装所需本机工具、SDK、'
    '项目依赖并配置构建环境，补齐后继续。保留既有安全措施。只改独立导出工作区的构建配置；'
    '不得修改玩法源码、用户其他项目或私自接受法律许可，不得读取或输出凭据、绕过权限、公开发布或上传商店。'
    '提权、账号登录、许可和公开发布需要对应的明确用户授权。')
MANIFEST_INSTRUCTIONS = '''在工作区写入 sceneops-export-result.json，只登记本轮实际完成的产物。
JSON 格式：{"artifacts":[{"platform":"mac-arm64","path":"dist/game.zip"}],
"platforms":[{"platform":"mac-arm64","status":"succeeded","message":"构建完成，设备待验证"}]}。
platform 只能使用本次目标平台；path 必须是工作区内真实文件的相对路径。
没有产物时 artifacts 为空；失败平台 status 为 failed 并说明问题。不得凭自述声称设备验证通过。
每轮先核查已有环境、文件和前轮执行记录，再增量执行，不能盲目重放未知结果的安装或构建。
旧 manifest 仅是历史证据，结束时仅写本轮结果。
fixed_build_dependency_download_allowed 和历史平台日志只描述固定构建流程，不能取代本次
服务端原生授权。当前原生授权包含导出所需工具与依赖补齐时，不为旧开关再次请求安装授权。'''


def resolve_export_context(service, project_id, export_id):
    service.workspace.get_project(project_id)
    if not export_id or service.export_context is None:
        raise HarnessError('EXPORT_CONTEXT_REQUIRED', '导出任务必须绑定服务端登记的导出工作区。')
    context = service.export_context(project_id, export_id)
    if not isinstance(context, dict) or not context.get('workspace_root'):
        raise HarnessError('EXPORT_CONTEXT_REQUIRED', '没有可执行的导出工作区。')
    root = Path(context['workspace_root'])
    if not root.is_absolute() or not root.is_dir() or root.resolve() != root:
        raise HarnessError('TASK_SCOPE_DENIED', '导出工作区必须是服务端登记的实际绝对目录。')
    load_export_knowledge(context.get('platforms', []), native=True)
    return context


def prepare_export_task(service, project_id, export_id, goal):
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 8000:
        raise HarnessError('TASK_GOAL_REQUIRED', '请输入导出任务目标。')
    settings = service.provider.settings()
    if settings.provider not in ('codexcli', 'codebuddycli', 'openai-compatible'):
        raise HarnessError('CLI_PROVIDER_REQUIRED', '电脑操作需要在模型设置中选择 Codex 或 CodeBuddy CLI。')
    context = resolve_export_context(service, project_id, export_id)
    knowledge = load_export_knowledge(context.get('platforms', []), native=True)
    timeout_minutes = getattr(settings, 'agent_timeout_minutes', None)
    duration_notice = '不设总运行时限' if timeout_minutes is None else f'最长 {timeout_minutes} 分钟'
    card = AuthorizationCard(export_id=export_id, workspace_id=export_id,
        workspace_root=context['workspace_root'], task_profile='project-export-agent',
        execution_mode='agent-full-access', allow_game_execution=True, allow_dependency_install=True,
        capability_ids=['agent.task.execute'], max_model_calls=None, max_cli_invocations=1,
        max_duration_seconds=None if timeout_minutes is None else timeout_minutes * 60, max_attempts_per_action=1, max_repair_rounds=0,
        scope=EXPORT_SCOPE, cost_notice=f'本轮一次原生 CLI 会话，{duration_notice}；内部模型请求和动作次数不限，费用可能未知。')
    task = AgentTaskRecord(project_id=project_id, goal=goal.strip(), authorization_card=card,
        provider_id=settings.provider, provider_model=settings.model,
        observations={'export_context': context, 'export_loaded_skills': list(knowledge.loaded_skills),
                      'native_system_instructions': knowledge.instructions + '\n' + MANIFEST_INSTRUCTIONS})
    if settings.provider == 'openai-compatible':
        task.observations['native_api_route'] = {'base_url': settings.base_url, 'wire_api': 'responses'}
    return service.records.create(task)


def export_workspace(service, task):
    context = resolve_export_context(service, task.project_id, task.authorization_card.export_id)
    if context['workspace_root'] != task.authorization_card.workspace_root:
        raise HarnessError('TASK_SCOPE_DENIED', '导出工作区已改变，需要新任务。')
    return Path(context['workspace_root'])


def validate_export_grant(service, task):
    card, grant = task.authorization_card, task.grant
    if (grant.export_id != card.export_id or grant.workspace_id != card.export_id
            or grant.workspace_root != card.workspace_root or grant.execution_mode != 'agent-full-access'
            or card.capability_ids != ['agent.task.execute'] or grant.capability_ids != card.capability_ids
            or not grant.allow_dependency_install or not grant.allow_game_execution
            or grant.allow_image_generation or grant.allow_blender_edit or grant.card_id or grant.branch):
        raise HarnessError('TASK_SCOPE_DENIED', '导出任务授权与登记范围不一致。')
    export_workspace(service, task)


def export_instructions(task):
    return load_export_knowledge(task.observations['export_context']['platforms'], native=True).instructions + '\n' + MANIFEST_INSTRUCTIONS


async def run_export_task(service, task_id, *, on_event=None, cancel_event=None):
    task = service.get(task_id)
    if task.authorization_card.task_profile != 'project-export-agent':
        raise HarnessError('TASK_SCOPE_DENIED', '此入口只执行已准备的导出任务。')
    if task.status != 'awaiting_authorization':
        raise HarnessError('TASK_REQUIRES_NEW_AUTHORIZATION', '已启动的原生导出不能自动重放，请创建新轮次。')
    service.authorize(task_id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
        accept_unknown_cost=True, accept_full_access=True))
    job = service.jobs.get(task_id)
    cursor = 0
    cancellation_sent = False

    def cancel_active():
        # A completed CLI still owns its worker while cleanup runs. Cancellation must
        # never interrupt that cleanup or turn the completed result into an error.
        if service.get(task_id).status in ('queued', 'running', 'blocked'):
            service.cancel(task_id)

    try:
        await asyncio.sleep(0)
        while job is not None and not job.done():
            if not cancellation_sent and cancel_event is not None and cancel_event.is_set():
                cancel_active()
                cancellation_sent = True
            events = service.events(task_id, after=cursor)
            cursor = events.next_cursor
            if on_event:
                for event in events.events:
                    on_event(event.model_dump(mode='json'))
            await asyncio.wait({job}, timeout=0.1)
        if job is not None:
            await job
        if on_event:
            for event in service.events(task_id, after=cursor).events:
                on_event(event.model_dump(mode='json'))
    except BaseException:
        if job is not None and not job.done():
            cancel_active()
            await asyncio.shield(job)
        raise
    return service.get(task_id)
