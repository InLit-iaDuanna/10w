"""P0 real deterministic Unity verification. No model invocation, build or publishing."""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import time
from uuid import uuid4
from engine_unity import UnityAgentSessionError
from sceneops_ai_provider import ProviderService
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask, AuthorizeAgentTask, AgentAction


async def main():
    root = Path('.local/mc-zombie-p0').resolve()
    root.mkdir(parents=True, exist_ok=True)
    database = root / 'sceneops.sqlite3'
    service = AgentTaskService(database, SqliteWorkspaceRepository(database), root)
    task = service.prepare(PrepareAgentTask(goal='P0 确定性验证：方块防线正式输入、版本、运行与证据。不调用模型。', task_profile='survival-prototype', allow_playtest=True))
    spec = dict(prototype_id='sobj_voxel_p0', title='方块防线', seed=42, arena_size=24, enemy_count=3,
        enemy_speed=1.2, player_health=100, weapon_damage=25, enemy_health=40, enemy_damage=10,
        player_speed=5, fire_interval=.25, goal_kills=4)
    actions = [AgentAction(action_id='compose_v1', capability_id='unity.prototype.compose', rationale='P0 固定验收规格组装正式场景', inputs=spec),
        AgentAction(action_id='verify_v1', capability_id='unity.prototype.verify', rationale='P0 正式共享输入链与真实帧检查', inputs={'composition_action_id': 'compose_v1'}),
        AgentAction(action_id='finish_v1', capability_id='agent.finish', rationale='只接受当前版本完整证据', inputs={'summary': 'P0 确定性结果'})]
    def plan():
        yield actions[0]
        current = service.get(task.id)
        compose = current.actions[0]
        tools = service.tools[task.id]
        session = tools.sessions['unity']
        auth = tools.authorization(SimpleNamespace(capability_id='unity.prototype.compose', run_id=compose.run_ids[-1]), 'unity')
        scene = session.project_root / 'Assets/SceneOpsPrototype.unity'
        before = scene.stat().st_mtime_ns
        duplicate = session.compose_prototype(request_id=compose.request_id, spec=spec, authorization=auth)
        assert duplicate['mode'] == 'cached' and scene.stat().st_mtime_ns == before
        try:
            session.compose_prototype(request_id=compose.request_id, spec={**spec, 'enemy_health': 41}, authorization=auth)
            raise AssertionError('Changed payload accepted for same request ID')
        except UnityAgentSessionError as error:
            assert error.code == 'UNITY_IDEMPOTENCY_CONFLICT'
        receipt = session.mailbox / (compose.request_id + '.result.json')
        receipt.rename(receipt.with_name(compose.request_id + '.transport-hidden.json'))
        reconciled = session.compose_prototype(request_id=compose.request_id, spec=spec, authorization=auth)
        assert reconciled['mode'] == 'cached' and reconciled['effects_reused'] and scene.stat().st_mtime_ns == before
        assert reconciled['project_revision'] == duplicate['project_revision']
        invalid_id = 'invalid_' + uuid4().hex
        original = json.loads((session.mailbox / (compose.request_id + '.request.json')).read_text())
        original['request_id'] = invalid_id; original['batch']['requestId'] = invalid_id
        original['authorization']['grant_id'] = 'retired_grant'
        invalid = session.mailbox / (invalid_id + '.request.json')
        invalid.write_text(json.dumps(original)); invalid.chmod(0o600)
        result_path = session.mailbox / (invalid_id + '.result.json')
        deadline = time.monotonic() + 10
        while not result_path.exists() and time.monotonic() < deadline: time.sleep(.1)
        rejected = json.loads(result_path.read_text())
        assert rejected['error_code'] == 'UNITY_AGENT_AUTH_DENIED' and scene.stat().st_mtime_ns == before
        protocol = {'mode': 'live', 'duplicate_request_no_effect': True, 'payload_conflict_rejected': True,
            'missing_receipt_reconciled_no_effect': True, 'retired_grant_rejected': True,
            'revision': duplicate['project_revision'], 'request_id': compose.request_id}
        (root / (task.id + '.protocol.json')).write_text(json.dumps(protocol, indent=2))
        print(json.dumps(protocol), flush=True)
        yield from actions[1:]
    task = service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=True), actions=plan())
    (root / 'current-task.json').write_text(json.dumps({'task_id': task.id, 'project_id': task.project_id,
        'workspace_root': task.grant.workspace_root}, indent=2))
    print(json.dumps({'task_id': task.id, 'project_id': task.project_id, 'driver': 'deterministic', 'model_calls': 0}), flush=True)
    previous = None
    try:
        while service.jobs:
            current = service.get(task.id)
            summary = {'status': current.status, 'reason': current.reason,
                'actions': [(a.action.capability_id, a.state, a.reason) for a in current.actions]}
            if summary != previous:
                print(json.dumps(summary, ensure_ascii=False), flush=True); previous = summary
            await asyncio.sleep(2)
        current = service.get(task.id)
        (root / (task.id + '.json')).write_text(current.model_dump_json(indent=2))
        print(json.dumps({'status': current.status, 'reason': current.reason,
            'checks': current.observations.get('prototype_verification', {}).get('checks', [])}, ensure_ascii=False), flush=True)
    finally:
        await service.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-live-game', action='store_true')
    if not parser.parse_args().confirm_live_game: parser.error('Explicit live demo authorization required')
    asyncio.run(main())
