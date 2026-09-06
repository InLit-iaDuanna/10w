"""Authorized physical gameplay checks through the public Unity session API."""
import json
import math
import time
import asyncio
from pathlib import Path
from sceneops_harness import HarnessError
from engine_unity import PrototypeSpec, inspect_png
from .task_models import now


async def dispatch_prototype(tools, invocation, cancellation):
    service, task = tools.service, tools.service.get(tools.task_id)
    session = await tools.session('unity')
    entry = next(item for item in service.get(task.id).actions if invocation.run_id in item.run_ids)
    cap = invocation.capability_id
    if cap == 'unity.prototype.inspect':
        result = await tools.sync(session, 'inspect_prototype')
    else:
        authorization = tools.authorization(invocation, 'unity')
        if cap == 'unity.prototype.compose':
            result = await tools.sync(session, 'compose_prototype', request_id=entry.request_id,
                spec=invocation.inputs, authorization=authorization)
        elif cap == 'unity.prototype.verify':
            return await verify_prototype(tools, session, invocation, entry, authorization, cancellation)
        else:
            operation = 'capture' if cap == 'unity.prototype.capture' else invocation.inputs['operation']
            result = await tools.sync(session, 'play_prototype', request_id=entry.request_id,
                operation=operation, input=invocation.inputs.get('input', {}), authorization=authorization)
    readback = await tools.sync(session, 'inspect')
    tools.validate_readback(task, 'unity', readback)
    for key in ('scene_path', 'artifact_path'):
        path = result.get(key)
        if path:
            path = Path(path) if Path(path).is_absolute() else session.project_root / path
            tools.register_artifacts(task, invocation, [str(path)])
    return {'tool': 'prototype', 'mode': 'live', 'result': result, 'readback': readback}


def distance(a, b):
    return math.sqrt(sum((a[key] - b[key]) ** 2 for key in ('x', 'y', 'z')))


async def verify_prototype(tools, session, invocation, entry, authorization, cancellation):
    context = {}
    try:
        return await _verify_prototype(tools, session, invocation, entry, authorization, cancellation, context)
    except (Exception, asyncio.CancelledError) as error:
        revision = context.get('revision')
        if not revision:
            raise
        task = tools.service.get(tools.task_id)
        record = {'project_revision': revision, 'run_id': (context['run_ids'] or [f'{entry.request_id}_1'])[0],
            'run_ids': context['run_ids'], 'suite_id': 'voxel-survival-core', 'suite_version': 3,
            'checker_version': 'shared-input-3', 'execution_status': 'CANCELLED' if isinstance(error, asyncio.CancelledError) else 'INTERRUPTED',
            'verdict': 'INCONCLUSIVE', 'assertions': context['checks'], 'artifact_refs': []}
        evidence = {'tool': 'prototype_verification', 'mode': 'live', 'effect_state': 'UNKNOWN',
            'verified': False, 'verification': record, 'error_code': getattr(error, 'code', type(error).__name__),
            'composition_action_id': invocation.inputs['composition_action_id'], 'frames': context['frames']}
        path = session.project_root / 'Artifacts' / f'{entry.request_id}.inconclusive.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        artifacts = tools.register_artifacts(task, invocation, [str(path), *context['captures']])
        record['artifact_refs'] = [{'artifact_id': item.id, 'version': item.version} for item in artifacts]
        evidence.pop('frames')
        tools.service.records.update(task.id, lambda current: current.observations.update({'prototype_verification': evidence}), 'prototype.check.inconclusive', {'code': evidence['error_code']})
        if isinstance(error, asyncio.CancelledError): raise
        return evidence


async def _verify_prototype(tools, session, invocation, entry, authorization, cancellation, context):
    task = tools.service.get(tools.task_id)
    compose = next((action for action in reversed(task.actions)
                   if action.action.capability_id == 'unity.prototype.compose' and action.state == 'succeeded'), None)
    if not compose or invocation.inputs.get('composition_action_id') != compose.action.action_id:
        raise HarnessError('PROTOTYPE_REVISION_REQUIRED', '验证必须绑定当前实际组装动作 ID。')
    spec = PrototypeSpec.model_validate(compose.action.inputs)
    revision = (compose.result or {}).get('evidence', {}).get('result', {}).get('project_revision')
    if not revision or revision == 'empty':
        raise HarnessError('PROTOTYPE_REVISION_REQUIRED', '组装没有返回已提交工程版本。')
    checks, frames, captures = [], [], []
    run_ids = []
    context.update(revision=revision, checks=checks, frames=frames, captures=captures, run_ids=run_ids)
    counter = 0
    deadline = time.monotonic() + 180

    async def play(operation='act', **inputs):
        nonlocal counter
        cancellation.raise_if_cancelled()
        tools.service.check_grant(task.id, 'unity.prototype.verify')
        if time.monotonic() > deadline:
            raise HarnessError('PROTOTYPE_CHECK_TIMEOUT', '实际游戏检查达到 180 秒，不伪造剩余结果。')
        counter += 1
        cap = 'unity.prototype.capture' if operation == 'capture' else 'unity.prototype.play'
        result = await tools.sync(session, 'play_prototype', request_id=f'{entry.request_id}_{counter}',
            operation=operation, input=inputs, authorization={**authorization, 'capability_id': cap})
        state = result.get('readback', {})
        if result.get('project_revision') != revision or result.get('revision_drift') or result.get('mode') != 'live':
            raise HarnessError('PROTOTYPE_REVISION_DRIFT', '运行或观测不属于当前版本，不能复用历史结果。')
        if operation == 'enter':
            run_ids.append(result['run_id'])
        if operation in ('act', 'reset'):
            receipt = state.get('input_receipt') or {}
            if (receipt.get('request_id') != f'{entry.request_id}_{counter}' or receipt.get('run_id') != run_ids[-1]
                    or not receipt.get('release_confirmed') or receipt.get('cancelled')
                    or receipt.get('completed_frames') != (1 if operation == 'reset' else inputs.get('duration_frames', 1))):
                raise HarnessError('INPUT_NOT_CONFIRMED', '正式输入消费或释放没有确认，此检查只能是不确定。')
        frames.append({'index': counter, 'operation': operation, 'input': inputs,
                       'readback': state, 'observed_at': now().isoformat()})
        tools.service.records.update(task.id, lambda current: None, 'prototype.check.observed',
            {'operation': operation, 'index': counter, 'state': state})
        if result.get('artifact_path'):
            path = Path(result['artifact_path'])
            captures.append(str(path if path.is_absolute() else session.project_root / path))
        if result.get('errors'):
            raise HarnessError('UNITY_CONSOLE_ERRORS', 'Unity 运行出现实际错误，请查看本任务控制台证据。')
        return state

    def check(name, passed, detail):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})

    await play('enter')
    initial = await play('reset')
    initial = await play(duration_frames=10)
    await play('capture')
    moved = await play(move_x=1, duration_frames=30)
    check('movement', distance(initial['player_position'], moved['player_position']) > .3,
          {'before': initial['player_position'], 'after': moved['player_position']})
    released = await play(duration_frames=12)
    check('movement_release', math.hypot(released['player_position']['x'] - moved['player_position']['x'], released['player_position']['z'] - moved['player_position']['z']) < .05,
          {'before': moved['player_position'], 'after': released['player_position']})
    jumped = await play(jump=True, duration_frames=6)
    check('jump', jumped['player_position']['y'] > moved['player_position']['y'] + .3,
          {'before_y': moved['player_position']['y'], 'after_y': jumped['player_position']['y']})
    landed = await play(duration_frames=90)
    check('landing', landed['grounded'] and abs(landed['player_position']['y'] - moved['player_position']['y']) < .15,
          {'grounded': landed['grounded'], 'position': landed['player_position']})
    wall = await play('reset')
    wall = await play(yaw_delta=90, duration_frames=1)
    for _ in range(12):
        wall = await play(move_z=1, duration_frames=120)
        if wall['state'] != 'playing' or (wall.get('input_receipt', {}).get('collided_side') and wall['player_position']['x'] > spec.arena_size / 2 - 1.5):
            break
    check('arena_collision', wall.get('input_receipt', {}).get('collided_side') and spec.arena_size / 2 - 1.5 < wall['player_position']['x'] < spec.arena_size / 2,
          {'position': wall['player_position'], 'arena_size': spec.arena_size})
    before_chase = await play('reset')
    after_chase = await play(duration_frames=120)
    first_id = before_chase['enemies'][0]['sceneops_id']
    before_enemy = next(item for item in before_chase['enemies'] if item['sceneops_id'] == first_id)
    after_enemy = next(item for item in after_chase['enemies'] if item['sceneops_id'] == first_id)
    check('zombie_chase', distance(after_enemy['position'], after_chase['player_position']) < distance(before_enemy['position'], before_chase['player_position']) - .3,
          {'before': before_enemy['position'], 'after': after_enemy['position']})
    await play('exit')
    state = await play('enter')
    missed = await play(pitch_delta=-75, fire=True, duration_frames=20)
    check('shot_miss', missed['shots'] > 0 and missed['hits'] == 0 and all(enemy['health'] == spec.enemy_health for enemy in missed['enemies']),
          {'shots': missed['shots'], 'hits': missed['hits']})
    state = missed
    for _ in range(min(60, spec.goal_kills * 4 + 4)):
        if state.get('state') != 'playing' or not state['enemies']:
            break
        target = min(state['enemies'], key=lambda enemy: distance(enemy['position'], state['player_position']))
        delta = {axis: target['position'][axis] - state['player_position'][axis] for axis in ('x', 'y', 'z')}
        yaw = math.degrees(math.atan2(delta['x'], delta['z']))
        pitch = -math.degrees(math.atan2(delta['y'] - .6, math.hypot(delta['x'], delta['z'])))
        turn = (yaw - state['yaw'] + 180) % 360 - 180
        state = await play(yaw_delta=turn, pitch_delta=pitch - state['pitch'], fire=True, duration_frames=30)
    check('raycast_shooting', state['shots'] > 0 and state['hits'] > 0 and state['kills'] > 0,
          {'shots': state['shots'], 'hits': state['hits'], 'kills': state['kills']})
    damage_events = [event for event in state.get('events', []) if event['type'] == 'DamageApplied' and event['run_id'] == run_ids[-1]]
    check('hit_damage_chain', damage_events and all(event['after'] == max(0, event['before'] - spec.weapon_damage) for event in damage_events), damage_events)
    check('victory', state['state'] == 'won' and state['kills'] >= spec.goal_kills,
          {'state': state['state'], 'kills': state['kills']})
    await play('capture')
    await play('exit')
    state = await play('enter')
    for _ in range(40):
        if state.get('state') == 'lost':
            break
        state = await play(duration_frames=120)
    check('damage_and_defeat', state['state'] == 'lost' and state['health'] == 0,
          {'state': state['state'], 'health': state['health']})
    await play('capture')
    restarted = await play('reset')
    check('restart', restarted['state'] == 'playing' and restarted['health'] == spec.player_health and restarted['kills'] == 0,
          {'state': restarted['state'], 'health': restarted['health'], 'kills': restarted['kills']})
    await play('exit')
    readback = await tools.sync(session, 'inspect')
    tools.validate_readback(task, 'unity', readback)
    check('console', 'errors' in readback and not readback['errors'], {'errors': readback.get('errors')})
    decoded = [inspect_png(Path(path)) for path in captures]
    check('camera_evidence', len(decoded) == 3 and all(item['width'] == 1280 and item['height'] == 720 for item in decoded), decoded)
    capture_artifacts = tools.register_artifacts(task, invocation, captures)
    verification = {'project_revision': revision, 'run_id': run_ids[0], 'run_ids': run_ids,
        'suite_id': 'voxel-survival-core', 'suite_version': 3, 'checker_version': 'shared-input-3',
        'execution_status': 'COMPLETED', 'verdict': 'PASS' if all(item['passed'] for item in checks) else 'FAIL',
        'assertions': checks, 'artifact_refs': [{'artifact_id': item.id, 'version': item.version} for item in capture_artifacts]}
    evidence = {'tool': 'prototype_verification', 'mode': 'live', 'effect_state': 'COMMITTED',
        'verified': verification['verdict'] == 'PASS', 'verification': verification,
        'composition_action_id': compose.action.action_id, 'checks': checks, 'frames': frames,
        'captures': captures, 'readback': readback}
    path = session.project_root / 'Artifacts' / f'{entry.request_id}.checks.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    # Application-produced evidence, not model output; fixed location under owned session.
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    reports = tools.register_artifacts(task, invocation, [str(path)])
    verification['artifact_refs'].extend({'artifact_id': item.id, 'version': item.version} for item in reports)
    evidence.pop('frames')
    evidence['observed_segments'] = len(frames)
    return evidence


async def finish_prototype(tools, task):
    compose = next((item for item in reversed(task.actions) if item.action.capability_id == 'unity.prototype.compose' and item.state == 'succeeded'), None)
    verified = next((item for item in reversed(task.actions) if item.action.capability_id == 'unity.prototype.verify' and item.state == 'succeeded'), None)
    evidence = (verified.result or {}).get('evidence', {}) if verified else {}
    if not compose:
        raise HarnessError('PRODUCTION_INCOMPLETE', '尚无已保存的原型制作结果。')
    playtest_required = task.authorization_card.allow_playtest
    if playtest_required and (not evidence.get('verified') or not verified.verification_result or verified.verification_result.verdict != 'PASS' or evidence.get('composition_action_id') != compose.action.action_id):
        raise HarnessError('VERIFICATION_INCOMPLETE', '当前原型尚未通过实际玩法检查，不能根据模型总结完成。')
    session = await tools.session('unity')
    current = await tools.sync(session, 'inspect')
    prototype = await tools.sync(session, 'inspect_prototype')
    revision = compose.result['evidence']['result']['project_revision']
    if prototype.get('revision_drift') or prototype.get('compiling') or prototype.get('project_revision') != revision:
        raise HarnessError('PROTOTYPE_REVISION_DRIFT', '现有场景版本与已通过检查不一致，必须新运行重新验证。')
    committed_spec = compose.result['evidence']['result']['spec']
    if PrototypeSpec.model_validate(prototype['spec']) != PrototypeSpec.model_validate(committed_spec):
        raise HarnessError('PROTOTYPE_REVISION_DRIFT', '当前场景参数存在未保存或未登记修改，不能沿用旧检查。')
    artifacts = tools.service.production.snapshot(task.project_id).artifacts
    scene_versions = [artifact for artifact in artifacts if artifact.step_id == f'{task.id}:{compose.action.action_id}'
                      and artifact.source_path == 'unity/Assets/SceneOpsPrototype.unity']
    if len(scene_versions) != 1:
        raise HarnessError('PROTOTYPE_SOURCE_VERSION_REQUIRED', '验收缺少唯一绑定的正式场景产物版本。')
    artifact = scene_versions[0]
    saved, _ = tools.service.production.artifact_content(task.project_id, artifact.id, artifact.version)
    current_file, metadata = tools.service.production._open_regular(session.project_root / 'Assets/SceneOpsPrototype.unity')
    with saved, current_file:
        if metadata.st_size != artifact.size_bytes or current_file.read(artifact.size_bytes + 1) != saved.read():
            raise HarnessError('PROTOTYPE_REVISION_DRIFT', '正式场景文件与被测试版本不一致，不能复用检查。')
    tools.validate_readback(task, 'unity', current)
    if 'errors' not in current or current['errors']:
        raise HarnessError('UNITY_CONSOLE_ERRORS', '当前 Unity 控制台未通过检查。')
    if not playtest_required:
        return {'tool': 'prototype', 'mode': 'live', 'verified': False,
            'delivery_status': 'production_ready', 'gameplay_verified': False,
            'project_revision': revision, 'readback': current,
            'checks': {'saved_scene': True, 'registered_artifact': True, 'compile_and_console': True},
            'summary': '场景制作、版本保存、编译与控制台检查完成；未执行自动游测，待用户手动试玩。'}
    if verified.verification_result.project_revision != revision:
        raise HarnessError('PROTOTYPE_REVISION_DRIFT', '玩法检查不属于当前制作版本。')
    return {'tool': 'prototype', 'mode': 'live', 'verified': True,
        'verification': evidence['verification'],
        'checks': evidence['checks'], 'captures': evidence['captures'], 'readback': current,
        'summary': '真实 Play Mode 移动、跳跃、碰撞、追击、射击、胜负、重开及控制台检查通过；非完整游戏品质验收。'}
