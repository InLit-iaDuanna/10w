"""Explicit negative-version -> GLM bounded repair -> new-revision recheck experiment."""
import argparse
import asyncio
import json
from pathlib import Path
from sceneops_ai_provider import ProviderService
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask, AgentAction


async def main():
    root = Path('.local/v5-preview').resolve()
    records = Path('.local/mc-zombie-validation').resolve()
    records.mkdir(parents=True, exist_ok=True)
    database = root / 'sceneops.sqlite3'
    provider = ProviderService(database)
    provider.update_settings(provider='codebuddycli', model='glm-5.3-flash')
    service = AgentTaskService(database, SqliteWorkspaceRepository(database), root, provider=provider)
    task = service.prepare(PrepareAgentTask(goal='方块防线：这是明确标记的负例版本与合法修复实验。先前固定配方故意使用低玩家生命和低武器伤害，'
        '请读取真实检查 FAIL 证据，在既有授权参数内修正战斗平衡。必须保留4个击杀目标、3个并发敌人、24米场地和种子42，'
        '不能修改源码、测试器、断言，不能直接修改运行中生命/死亡。允许调整玩家生命、枪伤害、敌人生命/伤害/速度等有界参数，'
        '每次修改生成新场景版本，运行完整unity.prototype.verify，只有当前版本全部通过才finish。最多两轮修复，最多8模型请求。',
        task_profile='survival-prototype', allow_playtest=True))
    spec = dict(prototype_id='sobj_voxel_p1', title='方块防线', seed=42, arena_size=24, enemy_count=3,
        enemy_speed=1.2, player_health=20, weapon_damage=5, enemy_health=150, enemy_damage=10,
        player_speed=5, fire_interval=.25, goal_kills=4)
    initial = [AgentAction(action_id='negative_v1', capability_id='unity.prototype.compose', rationale='明确负例：过低玩家生命与武器伤害；不作为交付版本', inputs=spec),
        AgentAction(action_id='negative_check_v1', capability_id='unity.prototype.verify', rationale='验证器必须实际识别无法完成战斗目标的负例', inputs={'composition_action_id':'negative_v1'})]
    task = service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=True),
        actions=initial, continue_with_agent=True)
    (records / 'p1-current-task.json').write_text(json.dumps({'task_id':task.id,'project_id':task.project_id,'workspace_root':task.grant.workspace_root},indent=2))
    print(json.dumps({'task':task.id,'project':task.project_id,'model':'glm-5.3-flash','initial_version':'intentional-negative'}),flush=True)
    previous = None
    try:
        while service.jobs:
            current = service.get(task.id)
            summary = {'status':current.status,'reason':current.reason,'model_calls':current.model_calls_used,'repair_rounds':current.repair_rounds_used,
                'actions':[(a.action.action_id,a.state,a.verification_result.verdict if a.verification_result else None) for a in current.actions]}
            if summary != previous: print(json.dumps(summary,ensure_ascii=False),flush=True); previous=summary
            await asyncio.sleep(2)
        current=service.get(task.id)
        (records/(task.id+'.p1.json')).write_text(current.model_dump_json(indent=2))
        print(json.dumps({'final':current.status,'reason':current.reason,'model_calls':current.model_calls_used,
            'verdicts':[(a.action.action_id,a.verification_result.verdict,a.verification_result.project_revision) for a in current.actions if a.verification_result]},ensure_ascii=False),flush=True)
    finally: await service.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-live-repair',action='store_true')
    if not parser.parse_args().confirm_live_repair: parser.error('Requires explicit live game/GLM repair authorization')
    asyncio.run(main())
