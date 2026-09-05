"""Opt-in real AI verification against the public API in an isolated workspace.

Run via scripts/python.mjs. Never imported by dev startup or the test suite.
Only text analysis is authorized here: no demos, assets or production tools.
"""
import argparse
import asyncio
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def verify(model: str, plan_only: bool = False):
    from services.api.app import create_app

    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix='sceneops-live-ai-api-') as directory:
        environment = {'SCENEOPS_DATA_DIR': directory, 'SCENEOPS_LOCAL_TOKEN': token,
                       'SCENEOPS_WEB_PORT': '4301', 'SCENEOPS_API_PORT': '8301',
                       'SCENEOPS_HARNESS_ENABLED': 'true'}
        previous = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        app = create_app()
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url='http://127.0.0.1:8301', timeout=130,
                    headers={'x-sceneops-token': token, 'origin': 'http://127.0.0.1:4301'}) as client:
                    async def request(method, path, body=None):
                        response = await client.request(method, path, json=body)
                        if response.is_error:
                            value = response.json()
                            raise RuntimeError(f'{path}: HTTP {response.status_code}, {value.get("code")}: {value.get("message")}')
                        return response.json()

                    await request('PUT', '/api/ai/settings', {'provider': 'codebuddycli', 'model': model})
                    project = await request('POST', '/api/workspace/projects', {'name': 'AI 接口连通验证（临时）'})
                    project_id = project['project_id']
                    if not plan_only:
                        chat = await request('POST', '/api/ai/chat', {'project_id': project_id,
                            'message': '本次为连接验证。请只回复：连接正常。不调用工具，不做制作任务。'})
                        reply = chat['messages'][-1]
                        assert reply['role'] == 'assistant' and reply['mode'] == 'live' and reply['model'] == model
                        saved = await request('GET', '/api/ai/conversation?project_id=' + project_id)
                        assert saved == chat
                        print(json.dumps({'check': 'chat_and_persistence', 'model': model, 'reply': reply['text']}, ensure_ascii=False), flush=True)

                        advice = await request('POST', '/api/ai/advice', {'project_id': project_id,
                            'module_id': 'integration-ops', 'prompt': '连接验证：用一句话说明模型候选目录不等于真实推理成功，不执行任何操作。'})
                        assert advice['mode'] == 'live' and advice['model'] == model and advice['text'].strip()
                        print(json.dumps({'check': 'module_advice', 'model': model, 'reply': advice['text']}, ensure_ascii=False), flush=True)

                    proposal = await request('POST', '/api/harness/proposals', {'project_id': project_id,
                        'goal': '仅为 AI 连通验证制定一个纯文字分析计划：由 producer 给出两条人工确认 AI 回复的方法。仅一个 ai.agent.assess 步骤，不需要读取项目或草稿，不做游戏案例。',
                        'constraints': ['只允许一个 ai.agent.assess 步骤', '不调用外部工具、不制作资产、不改文件、不跑案例'],
                        'budget': {'max_steps': 1, 'max_attempts_per_step': 1, 'max_metered_calls': 1,
                                   'usage_policy': 'bounded_calls', 'max_duration_seconds': 150}})
                    steps = [step for stage in proposal['definition']['stages'] for step in stage['steps']]
                    assert len(steps) == 1 and steps[0]['capability_id'] == 'ai.agent.assess', 'Only the authorized text-assessment step may run'
                    print(json.dumps({'check': 'structured_proposal', 'validation': proposal['validation'],
                                      'steps': [step['capability_id'] for step in steps]}, ensure_ascii=False), flush=True)
                    path = f'/api/harness/projects/{project_id}'
                    run = await request('POST', f'{path}/proposals/{proposal["id"]}/runs', {'request_id': 'live-ai-' + uuid4().hex})
                    async with asyncio.timeout(155):
                        while run['state'] in {'queued', 'running'}:
                            await asyncio.sleep(0.5)
                            run = await request('GET', f'{path}/runs/{run["id"]}')
                    print(json.dumps({'check': 'expert_run', 'state': run['state'],
                        'calls': run['metered_calls_used'], 'accounting_complete': run['budget_accounting_complete'],
                        'steps': [{'state': step['state'], 'reason': step.get('reason'),
                                   'mode': (step.get('result') or {}).get('execution_mode'),
                                   'logs': (step.get('result') or {}).get('logs')} for step in run['step_runs']]}, ensure_ascii=False), flush=True)
                    assert run['state'] == 'completed', 'Expert analysis did not complete'
                    events = await request('GET', f'{path}/runs/{run["id"]}/events')
                    assert events
                    print(json.dumps({'check': 'persisted_events', 'count': len(events),
                                      'production_operations': 0}), flush=True)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['glm-5.3-flash', 'hy4-preview'], required=True)
    parser.add_argument('--plan-only', action='store_true', help='Only planning and one expert step (three requests)')
    parser.add_argument('--confirm-live', action='store_true', help='Authorize up to five real model requests; no automatic retries')
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error('Real model requests require --confirm-live and current user authorization')
    asyncio.run(verify(args.model, args.plan_only))
