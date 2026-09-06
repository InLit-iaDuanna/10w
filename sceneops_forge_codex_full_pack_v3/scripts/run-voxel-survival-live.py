"""Explicitly authorized live survival demo through the application's public API."""
import argparse
import asyncio
import json
from pathlib import Path
import httpx


async def main(base):
    directory = Path('.local/mc-zombie-validation').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=base, headers={'Origin': base}, timeout=30) as client:
        async def request(method, path, body=None):
            response = await client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()
        await request('PUT', '/api/ai/settings', {'provider': 'codebuddycli', 'model': 'glm-5.3-flash'})
        task = await request('POST', '/api/agent/tasks', {
            'goal': '开发一个 MC 方块风格第一人称打僵尸的轻量可玩 Unity 单机原型，中文名方块防线。'
                '用真实方块世界、第一人称移动瞄准、射击、僵尸追击受击、生命值、胜负和重开。'
                '首个可玩版本采用小规模竞技场：4个总击杀目标、3个同时僵尸，玩家100血、敌人40血、子弹25伤害、'
                '僵尸伤害10、速度1.2、步速5、射击间隔0.25秒、24米场地。可调整有界参数修复已发现问题。'
                '在独立新工程中组装，必须实际运行 unity.prototype.verify 并通过检查才finish。'
                '不安装系统软件、不购买、不生产构建或发布。',
            'execution_mode': 'typed-tools', 'task_profile': 'survival-prototype', 'allow_image_generation': False})
        (directory / 'current-task.json').write_text(json.dumps({'task_id': task['id'], 'project_id': task['project_id'],
            'workspace_root': task['authorization_card']['workspace_root']}, indent=2))
        print(json.dumps({'prepared': task['id'], 'project': task['project_id'], 'scope': task['authorization_card']['scope']}, ensure_ascii=False), flush=True)
        task = await request('POST', f"/api/agent/tasks/{task['id']}/authorize", {
            'authorization_card_id': task['authorization_card']['id'], 'accept_unknown_cost': True})
        previous = None
        async with asyncio.timeout(1250):
            while task['status'] in ('queued', 'running'):
                task = await request('GET', '/api/agent/tasks/' + task['id'])
                state = {'status': task['status'], 'calls': task['model_calls_used'],
                    'actions': [(action['action']['capability_id'], action['state']) for action in task['actions']], 'reason': task['reason']}
                if state != previous:
                    print(json.dumps(state, ensure_ascii=False), flush=True)
                    previous = state
                await asyncio.sleep(2)
        (directory / (task['id'] + '.json')).write_text(json.dumps(task, ensure_ascii=False, indent=2))
        print(json.dumps({'final': task['status'], 'reason': task['reason'], 'task': task['id']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-live-game', action='store_true')
    parser.add_argument('--base', default='http://127.0.0.1:4301')
    args = parser.parse_args()
    if not args.confirm_live_game:
        parser.error('Requires current explicit user authorization and --confirm-live-game')
    asyncio.run(main(args.base))
