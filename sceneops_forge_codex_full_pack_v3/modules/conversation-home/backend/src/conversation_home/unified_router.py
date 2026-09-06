import asyncio
import json
from pathlib import Path
from collections.abc import Callable
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sceneops_ai_provider import ProviderFailure, ProviderService
from .ai_repository import AIRepository
from .schemas import AdapterError
from .unified_schemas import (AIAdvice, AIAdviceRequest, AIChatRequest, AIChatStreamEvent,
    AIConnectionRequest, AIConnectionResult, AIConversation, AIModel, AIModels,
    AIProviderModels, AIProviderModelsRequest, AISettings, AISettingsUpdate)

ADVICE_PROMPTS = {
    'concept-lab': '你是游戏概念设计顾问。只提供人工评审的文字建议，不生成图片或批准资产。检查轮廓、尺寸、预算、材质及禁止元素。',
    'design-room': '请提出游戏功能设计建议，保留用户目标，说明目标、玩家价值及 Given/When/Then 验收建议。所有推断都是未确认假设。',
    'character-animation': '你是角色与动画顾问。评审角色规格、骨骼层级、蒙皮、重定向、动画片段和状态转换；说明预算与兼容约束，不运行绑定、导出或播放验证。',
    'world-logic': '你是关卡与玩法逻辑顾问。围绕场景空间、对象稳定 ID、交互条件、状态机、任务目标与失败恢复提出建议。区分场景对象和资产身份，不修改场景或执行脚本。',
    'ui-audio-vfx': '你是游戏界面、音频和特效顾问。检查界面流程、反馈一致性、无障碍、声音事件及混音、VFX与着色器参数预算。只建议人工评审方案，不生成资源、不播放或运行特效。',
    'render-ops': '你是渲染与视觉评审顾问。围绕镜头、光照、材质、AOV、渲染配方及可编辑参数映射分析问题，说明前后对比需要的证据。不启动渲染，不将文字建议当作真实图像结果。',
    'unity-build': '你是 Unity 集成与构建发布顾问。分析资产导入、Prefab与稳定 ID、构建矩阵、平台依赖和发布风险。只给操作建议与待人工确认项，不启动 Unity、构建、部署或发布。',
    'version-review': '你是版本与协作评审顾问。分析语义、结构、视觉、行为差异，指出可定位的评审问题及回滚影响。只提出评论和决策建议，不执行 Git、加锁、合并、审批或回滚。',
    'ai-playtest': '你是游戏测试设计顾问。提出目标、前置条件、允许动作、预期结果、证据与问题回指建议。未执行的测试一律标为 planned；不启动游戏、测试代理、案例、回归或任何试玩。',
    'integration-ops': '你是工具集成与运维顾问。分析连接状态、能力报告、权限、日志中的已提供信息和可观测性，给出分步人工排查建议。不读取凭据，不连接外部系统，不重启服务或执行命令。',
}
ADVICE_PROMPTS['concept-assets'] = ADVICE_PROMPTS['concept-lab'] + ' 同时评审资产规格、来源许可、验证项和交接要求；不生产或发布资产。'
ADVICE_PROMPTS['project-planning'] = ADVICE_PROMPTS['design-room'] + ' 同时明确项目目标、功能依赖、任务拆解、里程碑与风险，不自动创建任务或应用设计。'

async def while_connected(request: Request, operation):
    task = asyncio.create_task(operation)
    try:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                raise asyncio.CancelledError()
            await asyncio.wait({task}, timeout=0.2)
        return await task
    except ProviderFailure as error:
        return JSONResponse(status_code=error.status_code,
            content=AdapterError(code=error.code, message=str(error)).model_dump())
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

def create_ai_router(database_path: str | Path, *, project_exists: Callable[[str], bool] | None = None,
                     secrets_path: str | Path | None = None):
    provider_service = ProviderService(database_path, secrets_path)
    repository = AIRepository(database_path)
    router = APIRouter(prefix='/api/ai', tags=['unified-ai'])
    busy_scopes: set[str] = set()

    def validate_project(project_id):
        if project_id is not None and project_exists is not None and not project_exists(project_id):
            raise HTTPException(404, '项目不存在，请重新选择项目。')

    def chat_prompt(body: AIChatRequest) -> str:
        history = repository.conversation(body.project_id).messages
        payload = {'project_id': body.project_id, 'context': body.context,
            'history': [{'role': item.role, 'text': item.text} for item in history],
            'message': body.message}
        return json.dumps(payload, ensure_ascii=False)

    @router.get('/models', response_model=AIModels)
    def models():
        settings = provider_service.settings()
        available = provider_service.provider_available()
        if settings.provider in ('codebuddycli', 'codexcli'):
            cli = 'codebuddy' if settings.provider == 'codebuddycli' else 'codex'
            message = (f'{cli} CLI 已安装；登录、模型权限和额度将在发送时检查。' if available else
                       f'找不到 {cli}；请安装并在终端登录后重试。')
        else:
            message = ('兼容服务设置已保存；连接和模型权限将在发送时检查。' if available else
                       '请配置兼容服务地址和 API Key。')
        return AIModels(provider=settings.provider, available=available,
            mode='planned' if available else 'blocked',
            models=[AIModel(id=item.id, label=item.label, provider=item.provider)
                    for item in provider_service.models()], message=message)

    @router.get('/settings', response_model=AISettings)
    def settings():
        return AISettings(**provider_service.settings().__dict__)

    @router.put('/settings', response_model=AISettings,
                responses={422: {'model': AdapterError}, 503: {'model': AdapterError}})
    def save_settings(body: AISettingsUpdate):
        try:
            updated = provider_service.update_settings(
                provider=body.provider,
                model=body.model,
                base_url=body.base_url,
                api_key=body.api_key.get_secret_value() if body.api_key is not None else None,
                api_protocol=body.api_protocol,
                streaming=body.streaming,
                alignment_detail=body.alignment_detail,
            )
        except ProviderFailure as error:
            return JSONResponse(status_code=error.status_code,
                content=AdapterError(code=error.code, message=str(error)).model_dump())
        return AISettings(**updated.__dict__)

    @router.post('/provider/models', response_model=AIProviderModels,
                 responses={422: {'model': AdapterError}, 503: {'model': AdapterError}})
    async def provider_models(body: AIProviderModelsRequest, request: Request):
        async def discover():
            discovered = await provider_service.discover_models(provider=body.provider,
                base_url=body.base_url,
                api_key=body.api_key.get_secret_value() if body.api_key is not None else None)
            live = body.provider == 'openai-compatible'
            message = (f'已从兼容服务获取 {len(discovered)} 个模型。' if live else
                       f'已读取 {len(discovered)} 个本机候选模型；CLI 账户权限仍需连接检查。')
            return AIProviderModels(provider=body.provider,
                mode='live' if live else 'planned',
                models=[AIModel(id=item.id, label=item.label, provider=item.provider)
                        for item in discovered], message=message)
        return await while_connected(request, discover())

    @router.post('/provider/check', response_model=AIConnectionResult,
                 responses={422: {'model': AdapterError}, 503: {'model': AdapterError}})
    async def provider_check(body: AIConnectionRequest, request: Request):
        async def check():
            result = await provider_service.check_connection(provider=body.provider,
                model=body.model, base_url=body.base_url,
                api_key=body.api_key.get_secret_value() if body.api_key is not None else None,
                api_protocol=body.api_protocol, streaming=body.streaming)
            return AIConnectionResult(**result.__dict__)
        return await while_connected(request, check())

    @router.get('/conversation', response_model=AIConversation)
    def conversation(project_id: str | None = None):
        validate_project(project_id)
        return repository.conversation(project_id)

    @router.post('/chat', response_model=AIConversation,
                 responses={422: {'model': AdapterError}, 503: {'model': AdapterError}})
    async def chat(body: AIChatRequest, request: Request):
        validate_project(body.project_id)
        scope = repository.scope(body.project_id)
        if scope in busy_scopes:
            raise HTTPException(409, '此项目有回复正在生成，请等待或取消后再发送。')
        busy_scopes.add(scope)
        async def generate():
            result = await provider_service.generate(chat_prompt(body))
            repository.append_exchange(body.project_id, body.message, result.text,
                                       result.model, result.provider)
            return repository.conversation(body.project_id)
        try:
            return await while_connected(request, generate())
        finally:
            busy_scopes.discard(scope)

    @router.post('/chat/stream', response_model=AIChatStreamEvent,
                 response_class=StreamingResponse, responses={
        200: {'description': 'Server-sent JSON events.', 'content': {
            'text/event-stream': {'schema': {'$ref': '#/components/schemas/AIChatStreamEvent'}}}},
        422: {'model': AdapterError}, 503: {'model': AdapterError},
    })
    async def chat_stream(body: AIChatRequest):
        validate_project(body.project_id)
        scope = repository.scope(body.project_id)
        if scope in busy_scopes:
            raise HTTPException(409, '此项目有回复正在生成，请等待或取消后再发送。')
        busy_scopes.add(scope)

        async def events():
            queue: asyncio.Queue[AIChatStreamEvent] = asyncio.Queue(maxsize=256)

            async def forward(event: dict):
                if event.get('type') == 'text_delta' and isinstance(event.get('text'), str):
                    await queue.put(AIChatStreamEvent(type='text_delta', text=event['text']))
                elif event.get('type') == 'status' and isinstance(event.get('text'), str):
                    await queue.put(AIChatStreamEvent(type='status', text=event['text']))

            async def generate():
                try:
                    settings = provider_service.settings()
                    status = '正在接收流式回复…' if settings.streaming else '正在等待完整回复…'
                    await queue.put(AIChatStreamEvent(type='status', text=status))
                    result = await provider_service.generate(chat_prompt(body), on_event=forward)
                    repository.append_exchange(body.project_id, body.message, result.text,
                                               result.model, result.provider)
                    await queue.put(AIChatStreamEvent(type='complete',
                        conversation=repository.conversation(body.project_id)))
                except asyncio.CancelledError:
                    raise
                except ProviderFailure as error:
                    await queue.put(AIChatStreamEvent(type='error', code=error.code,
                                                     text=str(error)))
                except Exception:
                    await queue.put(AIChatStreamEvent(type='error', code='CHAT_STREAM_FAILED',
                        text='回复流中断，请重新读取对话后手动重试。'))

            pending = asyncio.create_task(generate())
            try:
                while True:
                    event = await queue.get()
                    yield 'data: ' + event.model_dump_json(exclude_none=True) + '\n\n'
                    if event.type in ('complete', 'error'):
                        break
            finally:
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                busy_scopes.discard(scope)

        return StreamingResponse(events(), media_type='text/event-stream', headers={
            'Cache-Control': 'no-cache, no-store',
            'X-Accel-Buffering': 'no',
        })

    @router.post('/advice', response_model=AIAdvice,
                 responses={422: {'model': AdapterError}, 503: {'model': AdapterError}})
    async def advice(body: AIAdviceRequest, request: Request):
        validate_project(body.project_id)
        async def generate():
            prompt = ADVICE_PROMPTS.get(body.module_id, '请围绕当前模块提供可供人工采用的建议，不执行建议。')
            result = await provider_service.generate(prompt + '\n' + body.model_dump_json(),
                                                     purpose='advice')
            return AIAdvice(project_id=body.project_id, module_id=body.module_id,
                            provider=result.provider, model=result.model, text=result.text)
        return await while_connected(request, generate())

    return router
