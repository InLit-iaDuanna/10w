"""Content operations use the existing authenticated, task-owned Unity mailbox."""
import json
import re
import shutil
import uuid
from pathlib import Path
from .content_contracts import ContentNodes, ContentEdit, ContentPlay


def inspect_content(session):
    return _observed(session, session._exchange('content_read_' + uuid.uuid4().hex, 'unity.content.inspect'))


def _observed(session, result):
    from .agent_session import UnityAgentSessionError
    if result.get('session_id') != session._config['session_id']:
        raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED', 'Content readback belongs to another session.')
    return {**result, 'project_root': str(session.project_root), 'workspace_root': str(session.workspace_root), 'mode': 'live'}


def _identifier(value):
    from .agent_session import UnityAgentSessionError
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value):
        raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'Invalid content identity.')
    return value


def _execute(session, request_id, command, payload, authorization):
    from .agent_session import UnityAgentSessionError, _inside
    session._validate_grant(authorization)
    if authorization.get('capability_id') != command or any(not authorization.get(k) for k in ('action_id', 'change_set_id', 'approval_id')):
        raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Content action needs its bound capability and action records.')
    if session._config is None:
        raise UnityAgentSessionError('UNITY_SESSION_OFFLINE', 'Start the registered Editor first.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', request_id):
        raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'Invalid request identity.')
    auth = {**authorization, 'session_id': session._config['session_id']}
    request_path = _inside(session.mailbox / (request_id + '.request.json'), session.workspace_root)
    if request_path.exists():
        previous = json.loads(request_path.read_text())
        original = json.loads(previous['batch']['payloadJson'])
        business = {k: v for k, v in original.items() if k not in ('base_revision', 'run_id')}
        if previous['command'] != command or previous['authorization'] != auth or business != payload:
            raise UnityAgentSessionError('UNITY_IDEMPOTENCY_CONFLICT', 'Request identity belongs to another content action.')
        batch = previous['batch']
    else:
        current = inspect_content(session)
        payload = {**payload, 'base_revision': current.get('revision', 'empty'), 'run_id': current.get('run_id', '')}
        serialized = json.dumps(payload, separators=(',', ':'))
        change = {'change_set_id': auth['change_set_id'], 'base_version': payload['base_revision'],
            'command': command, 'approval_state': 'approved', 'target_object_ids': [payload.get('instance_id') or payload.get('asset_id') or session.workspace_root.name],
            'proposed_payload_json': serialized, 'previous_values': payload.get('expected', {}), 'proposed_values': payload,
            'rationale': 'Authorized Unity asset editing roundtrip', 'expected_result': 'Saved Editor fields and source identity readback',
            'impact_scope': str(session.project_root), 'risk': 'low', 'validation_plan': ['Read authoritative Editor state'],
            'rollback_plan': ['Retain previous model version; inspect unknown writes before recovery']}
        batch = {'requestId': request_id, 'command': command, 'projectId': session.workspace_root.name,
            'projectRoot': str(session.project_root), 'baseVersion': payload['base_revision'], 'executionMode': 'live',
            'payloadJson': serialized, 'changeSetJson': json.dumps(change)}
    replay = (session.mailbox / (request_id + '.result.json')).exists()
    result = _observed(session, session._exchange(request_id, command, batch=batch, authorization=auth, timeout=90))
    result['mode'] = 'cached' if replay else 'live'
    result['change_set'] = json.loads(batch['changeSetJson'])
    if replay:
        result['readback'] = inspect_content(session)
        result['readback_mode'] = 'live'
    return result


def import_content(session, *, request_id, asset_id, source_version, expected_source_version, fbx_path, node_ids, instance_ids, authorization):
    from .agent_session import _inside, UnityAgentSessionError
    session._validate_grant(authorization)
    if authorization.get('capability_id') != 'unity.content.import' or any(not authorization.get(k) for k in ('action_id', 'change_set_id', 'approval_id')):
        raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Import needs its own authorization.')
    asset_id, source_version = _identifier(asset_id), _identifier(source_version)
    nodes = ContentNodes.model_validate(node_ids).model_dump()
    instances = [_identifier(i) for i in instance_ids]
    if len(instances) != 2 or len(set(instances)) != 2:
        raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'Initial content setup needs two distinct server-issued instance identities.')
    source = _inside(Path(fbx_path), session.workspace_root)
    if source.suffix.lower() != '.fbx' or not source.is_file():
        raise UnityAgentSessionError('UNITY_INVALID_PAYLOAD', 'A real FBX derived from the registered version is required.')
    staged = _inside(session.project_root / 'Staging/Content' / asset_id / source_version / 'model.fbx', session.workspace_root)
    if staged.exists() and staged.read_bytes() != source.read_bytes():
        raise UnityAgentSessionError('UNITY_VERSION_CONFLICT', 'The registered source version already has different FBX content.')
    staged.parent.mkdir(parents=True, exist_ok=True)
    if not staged.exists():
        shutil.copyfile(source, staged)
    return _execute(session, request_id, 'unity.content.import', {'asset_id': asset_id, 'source_version': source_version,
        'expected_source_version': expected_source_version, 'source_path': str(staged.relative_to(session.project_root)), 'nodes': nodes, 'instance_ids': instances}, authorization)


def edit_content(session, *, request_id, instance_id, expected, authorization, position=None, interaction_distance=None, requires_key=None):
    edit = ContentEdit(instance_id=instance_id, expected=expected, position=position,
        interaction_distance=interaction_distance, requires_key=requires_key).model_dump(mode='json')
    payload = {'instance_id': edit['instance_id'], 'expected': edit['expected'],
        'set_position': position is not None, 'set_distance': interaction_distance is not None, 'set_requires_key': requires_key is not None,
        'position': edit['position'] or [0, 0, 0], 'interaction_distance': interaction_distance or 0, 'requires_key': bool(requires_key)}
    return _execute(session, request_id, 'unity.content.edit', payload, authorization)


def focus_content(session, *, request_id, instance_id, authorization):
    return _execute(session, request_id, 'unity.content.focus', {'instance_id': _identifier(instance_id)}, authorization)


def save_content(session, *, request_id, reopen=False, authorization):
    return _execute(session, request_id, 'unity.content.save', {'reopen': bool(reopen)}, authorization)


def play_content(session, *, request_id, operation, input=None, authorization):
    payload = ContentPlay(operation=operation, input=input or {}).model_dump(mode='json')
    return _execute(session, request_id, 'unity.content.play', payload, authorization)


def content_rejection(workspace_root, *, request_id, task_id, grant_id, action_id):
    """Read a bound durable rejection; absence of a write marker proves no Editor mutation."""
    from .agent_session import _inside
    root=Path(workspace_root).absolute(); mailbox=_inside(root/'unity/.sceneops-agent',root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',request_id):
        return None
    paths=[_inside(mailbox/(request_id+suffix),root) for suffix in ('.request.json','.result.json','.content-started.json')]
    if not paths[0].is_file() or not paths[1].is_file() or paths[2].exists():
        return None
    request=json.loads(paths[0].read_text()); reply=json.loads(paths[1].read_text())
    auth=request.get('authorization') or {}
    if (auth.get('task_id')!=task_id or auth.get('grant_id')!=grant_id or auth.get('action_id')!=action_id
            or not request.get('command','').startswith('unity.content.') or reply.get('status')!='failed'):
        return None
    codes={'UNITY_SCENE_MISMATCH','UNITY_UNSAVED_SCENE','UNITY_VERSION_CONFLICT','UNITY_FIELD_CONFLICT',
           'UNITY_REVISION_CONFLICT','UNITY_PLAY_CONFLICT','UNITY_RUN_MISMATCH','UNITY_INVALID_PAYLOAD',
           'UNITY_COMMAND_NOT_ALLOWED','UNITY_AGENT_AUTH_DENIED','UNITY_MISSING_REFERENCE','UNITY_IDENTITY_CONFLICT'}
    if reply.get('error_code') not in codes:
        return None
    return {'tool':'unity_content_operation','mode':'cached','effect_state':'NONE','outcome':'rejected',
            'request_id':request_id,'code':reply['error_code'],'reason':reply.get('message',''),
            'evidence_basis':'bound durable Editor rejection before write marker'}


def confirm_content_editor_closed(workspace_root):
    from .agent_session import UnityAgentSession,_inside,_write,UnityAgentSessionError
    session=UnityAgentSession(Path(workspace_root),Path(workspace_root).parent/'state-readback')
    marker=_inside(session.mailbox/'session.json',session.workspace_root)
    if not marker.is_file():return True
    config=json.loads(marker.read_text())
    if config.get('created_by')!='sceneops-agent-v1' or config.get('project_root')!=str(session.project_root):
        raise UnityAgentSessionError('UNITY_AGENT_SCOPE_DENIED','Editor ownership marker differs from this target.')
    session._config=config
    if session._owned_pid_alive():return False
    config['closed']=True;_write(marker,config)
    return True


def content_dispatch_absent(workspace_root, *, request_id):
    """Confirm that this request identity never reached the task-owned Unity mailbox."""
    from .agent_session import _inside
    root=Path(workspace_root).absolute();mailbox=_inside(root/'unity/.sceneops-agent',root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',request_id):return False
    suffixes=('.request.json','.result.json','.content-started.json')
    return all(not _inside(mailbox/(request_id+suffix),root).exists() for suffix in suffixes)


def content_receipt(workspace_root, *, request_id, task_id, grant_id, action_id):
    rejected=content_rejection(workspace_root,request_id=request_id,task_id=task_id,grant_id=grant_id,action_id=action_id)
    if rejected:return rejected
    from .agent_session import _inside
    root=Path(workspace_root).absolute();mailbox=_inside(root/'unity/.sceneops-agent',root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',request_id):return None
    request_path=_inside(mailbox/(request_id+'.request.json'),root)
    reply_path=_inside(mailbox/(request_id+'.result.json'),root)
    if not request_path.is_file() or not reply_path.is_file():return None
    request=json.loads(request_path.read_text());reply=json.loads(reply_path.read_text());auth=request.get('authorization') or {}
    if (auth.get('task_id')!=task_id or auth.get('grant_id')!=grant_id or auth.get('action_id')!=action_id
            or not request.get('command','').startswith('unity.content.') or reply.get('status')!='succeeded'):
        return None
    readback=json.loads(reply['resultJson'])
    if readback.get('session_id')!=request.get('session_id'):return None
    return {'tool':'unity_content_operation','mode':'cached','effect_state':'COMMITTED','outcome':'saved_result',
        'request_id':request_id,'readback':readback,'reason':'原 Editor 操作已返回持久成功回执，未重放；当前场景需重新读取。'}
