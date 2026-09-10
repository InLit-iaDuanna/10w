"""Bounded export conversation: one model decision, typed packaging actions only."""
import asyncio
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sceneops_ai_context import ProductionPreparationRequest
from .export_knowledge import VERSION, load_export_knowledge


class ExportConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    app_name: str | None = Field(default=None, min_length=1, max_length=120)
    orientation: Literal['landscape', 'portrait'] | None = None


class ExportAgentAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['continue', 'cancel', 'configure', 'request_development']
    platform: Literal['android', 'mac-arm64', 'mac-x64', 'win-x64'] | None = None
    settings: ExportConfiguration | None = None
    request: str | None = Field(default=None, max_length=8000)


class ExportAgentDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=16000)
    actions: list[ExportAgentAction] = Field(default_factory=list, max_length=8)


class ExportAgent:
    """Reuse the configured provider; the export service persists the returned audit."""

    def __init__(self, provider, *, redact=lambda text: text, production_preparation=None):
        self.provider = provider
        self.redact = redact
        self.production_preparation = production_preparation

    def __call__(self, task, content, provider_id=None, model=None):
        return asyncio.run(self.respond(task, content, provider_id, model))

    async def respond(self, task, content, provider_id=None, model=None):
        selected = self.provider.settings()
        if provider_id is not None and provider_id != selected.provider:
            raise ValueError('导出对话使用当前已配置的提供方，请先在模型设置中切换。')
        if model is not None and model != selected.model:
            raise ValueError('模型已变化，请使用当前模型重新发送。')
        runs = []
        for run in task['platforms']:
            latest = run['attempts'][-1] if run['attempts'] else None
            runs.append({'platform': run['platform'], 'status': run['status'],
                'verification': run['verification'], 'latest_attempt': None if latest is None else {
                    **{key: latest.get(key) for key in ('id', 'status', 'stage', 'error')},
                    'logs': latest['logs'][-80:]}})
        context = {'task_id': task['id'], 'project_id': task['project_id'],
            'source_version': task['source_version'], 'settings': task['settings'],
            'platforms': runs, 'messages': [{key: message[key] for key in ('role', 'content')}
                for message in task['messages'][-20:]], 'request': content}
        preparation_record = None
        preparation_context = None
        if self.production_preparation is not None:
            latest_user = next((message for message in reversed(task['messages'])
                                if message.get('role') == 'user'), {})
            platforms = [run['platform'] for run in task['platforms']]
            request_identity = latest_user.get('id') or uuid4().hex
            preparation_request = ProductionPreparationRequest(
                project_id=task['project_id'],
                request_key=f"export:{task['id']}:{request_identity}",
                production_kind='export', requirement=content[:20000],
                confirmed_direction=json.dumps(task.get('settings', {}), ensure_ascii=False)[:10000],
                target_platform=platforms[0] if len(platforms) == 1 else None,
                current_state={'task_id': task['id'], 'platforms': platforms,
                               'source_version': task['source_version']},
                available_capability_ids=['export.package', 'export.environment.inspect'],
                model_call_allowed=True, remaining_model_calls=1,
                remaining_time_seconds=30,
            )
            try:
                preparation = await self.production_preparation.prepare(preparation_request)
                preparation_record = preparation.model_dump(mode='json')
                preparation_context = await self.production_preparation.selected_context(
                    preparation_request, preparation)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                preparation_record = {'status': 'failed', 'recommendation': None,
                    'failure_code': getattr(error, 'code', type(error).__name__),
                    'failure_message': f'制作推荐不可用：{error}；继续按平台必需导出规则执行。'}
                preparation_context = preparation_record
        def redact_value(value):
            if isinstance(value, str):
                return self.redact(value)
            if isinstance(value, list):
                return [redact_value(item) for item in value]
            if isinstance(value, dict):
                return {key: redact_value(item) for key, item in value.items()}
            return value
        if preparation_context is not None:
            context['production_preparation'] = preparation_context
        prompt = json.dumps(redact_value(context), ensure_ascii=False)
        knowledge = load_export_knowledge(run['platform'] for run in task['platforms'])
        response = await self.provider.generate(prompt, model=selected.model,
            schema=ExportAgentDecision.model_json_schema(), purpose='agent-action',
            instructions=knowledge.instructions, timeout=120)
        if response.provider != selected.provider or response.model != selected.model:
            raise ValueError('实际模型与本次导出对话选择不一致。')
        decision = ExportAgentDecision.model_validate(response.structured or json.loads(response.text))
        platforms = {run['platform'] for run in task['platforms']}
        for action in decision.actions:
            if action.action in ('continue', 'cancel') and action.platform not in platforms:
                raise ValueError('Agent 选择了本次导出以外的平台。')
        result = decision.model_dump(exclude_none=True)
        usage = dict(response.usage or {})
        selector_usage = ((preparation_record.get('call') or {}).get('usage')
                          if isinstance(preparation_record, dict) else None)
        if isinstance(selector_usage, dict):
            usage['production_preparation'] = selector_usage
            if isinstance(usage.get('total_tokens'), int) and isinstance(selector_usage.get('total_tokens'), int):
                usage['total_tokens'] += selector_usage['total_tokens']
        result.update(agent_task_id=f"export-agent:{task['id']}", provider_id=response.provider,
            model=response.model, usage=usage,
            invocation={'input': json.loads(prompt), 'output': decision.model_dump(exclude_none=True),
                'latency_ms': response.latency_ms, 'skill_version': VERSION,
                'loaded_skills': list(knowledge.loaded_skills),
                'production_preparation': preparation_record})
        return result
