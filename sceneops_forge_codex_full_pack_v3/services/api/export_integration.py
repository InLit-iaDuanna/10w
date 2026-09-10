"""Compose native export tasks through the public, grant-owning AgentTaskService."""
import asyncio
import json


class NativeExportPort:
    def __init__(self, tasks):
        self.tasks = tasks
        self.loop = None

    async def start(self):
        self.loop = asyncio.get_running_loop()

    def prepare(self, context, content, provider_id=None, model=None):
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError('原生执行服务尚未启动。')
        selected = self.tasks.provider.settings()
        if provider_id is not None and selected.provider != provider_id:
            raise ValueError('提供方已变化，请重新选择后发送。')
        if model is not None and selected.model != model:
            raise ValueError('模型已变化，请重新选择后发送。')
        task = self.tasks.prepare_export_task(context['project_id'], context['export_id'], content)
        return task.id

    def run(self, task_id, emit, cancel_event):
        def on_event(event):
            kind = event['event_type']
            payload = event.get('payload', {})
            if kind == 'agent.codex.activity':
                activity = payload.get('activity', {})
                emit(activity.get('type', 'agent'), json.dumps(activity, ensure_ascii=False))
            elif kind in ('agent.task.started', 'agent.task.cancellation_requested',
                          'agent.task.cancelled', 'agent.task.failed', 'agent.task.needs_approval'):
                emit(kind, json.dumps(payload, ensure_ascii=False))
        # Native jobs share the application's existing lifecycle and background
        # services. A temporary event loop would strand learning/cleanup jobs.
        future = asyncio.run_coroutine_threadsafe(
            self.tasks.run_export_task(task_id, on_event=on_event, cancel_event=cancel_event),
            self.loop)
        task = future.result()
        messages = [item.get('text', '') for item in task.observations.get('native_conversation', [])
                    if item.get('type') == 'assistant' and item.get('complete') and item.get('text')]
        succeeded = task.status in ('completed', 'review_required')
        return {'status': 'succeeded' if succeeded else task.status,
                'content': messages[-1] if messages else task.reason or 'Agent 已结束；请查看执行记录。',
                'error': None if succeeded else task.reason}
