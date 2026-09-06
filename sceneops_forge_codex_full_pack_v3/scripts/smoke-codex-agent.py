"""User-authorized one-file Codex/low smoke in a new independent task directory."""
import asyncio
import json
from pathlib import Path
from sceneops_ai_provider import ProviderService
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask
from sceneops_project_workspace import SqliteWorkspaceRepository


async def main():
    root = Path(__file__).resolve().parents[1] / '.local/codex-agent-validation'
    database = root / 'sceneops.sqlite3'
    provider = ProviderService(database)
    provider.update_settings(provider='codexcli', model='gpt-5.6-sol')
    service = AgentTaskService(database, SqliteWorkspaceRepository(database), root, provider=provider)
    try:
        task = service.prepare(PrepareAgentTask(execution_mode='codex-full-access', goal=(
            '仅做一次最小连接烟测：在当前独立任务目录使用 apply_patch 新建 smoke.txt，'
            '内容严格为 SceneOps Codex CLI OK 加一个换行，再读取此文件确认内容。'
            '不访问当前目录外的文件，不联网，不安装，不启动 Blender/Unity，不构建，不运行其他测试。'
            '最终只回复实际文件名和核验结果。')))
        service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
            accept_unknown_cost=True, accept_full_access=True))
        await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())), timeout=90)
        result = service.get(task.id)
        artifact = Path(result.authorization_card.workspace_root) / 'smoke.txt'
        verified = artifact.is_file() and not artifact.is_symlink() and artifact.read_text() == 'SceneOps Codex CLI OK\n'
        print(json.dumps({'task_id': task.id, 'status': result.status, 'reason': result.reason,
            'model': result.provider_model, 'reasoning_effort': 'low',
            'cli_invocations': result.cli_invocations_used, 'file_verified': verified,
            'workspace': result.authorization_card.workspace_root,
            'observation': result.observations.get('codex')}, ensure_ascii=False))
        if result.status != 'review_required' or not verified:
            raise SystemExit('Codex smoke did not pass; inspect the retained task record.')
    finally:
        await service.close()


if __name__ == '__main__':
    asyncio.run(main())
