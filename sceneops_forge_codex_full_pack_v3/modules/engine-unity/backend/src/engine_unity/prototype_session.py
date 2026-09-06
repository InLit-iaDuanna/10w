"""Prototype commands over the same authenticated task-owned Editor session."""
import json
import uuid

from .prototype_contracts import PrototypeInput, PrototypePlayPayload, PrototypeSpec


def _decode(result):
    result['readback'] = json.loads(result.pop('state_json', '') or '{}')
    if result.get('spec_json'):
        result['spec'] = json.loads(result.pop('spec_json'))
    result['mode'] = 'live'
    return result


def inspect_prototype(session):
    session._validate_grant()
    return _decode(session._exchange('inspect_' + uuid.uuid4().hex, 'unity.prototype.inspect'))


def _execute(session, request_id, capability, payload, authorization, target):
    from .agent_session import UnityAgentSessionError
    session._validate_grant(authorization)
    if authorization.get('capability_id') != capability or any(not authorization.get(key) for key in
            ('action_id', 'change_set_id', 'approval_id')):
        raise UnityAgentSessionError('UNITY_AGENT_AUTH_DENIED', 'Prototype action requires its matching task capability and action/ChangeSet/approval records.')
    if session._config is None:
        raise UnityAgentSessionError('UNITY_SESSION_OFFLINE', 'Start the dedicated Editor session before prototype actions.')
    from .agent_session import _inside
    request_path = _inside(session.mailbox / (request_id + '.request.json'), session.workspace_root)
    bound_authorization = {**authorization, 'session_id': session._config['session_id']}
    if request_path.exists():
        prior = json.loads(request_path.read_text())
        original = json.loads(prior['batch']['payloadJson'])
        business = {key: value for key, value in original.items() if key not in ('expected_revision', 'run_id')}
        if prior.get('command') != capability or prior.get('authorization') != bound_authorization or business != payload:
            raise UnityAgentSessionError('UNITY_IDEMPOTENCY_CONFLICT', 'Same request ID has different frozen payload or authorization.')
        replay = (session.mailbox / (request_id + '.result.json')).exists()
        result = session._exchange(request_id, capability, batch=prior['batch'], authorization=bound_authorization, timeout=90)
        decoded = _decode(result)
        decoded['mode'] = 'cached' if replay or decoded.get('effects_reused') else 'live'
        decoded['change_set'] = json.loads(prior['batch']['changeSetJson'])
        return decoded
    payload_json = json.dumps(payload, separators=(',', ':'))
    current = inspect_prototype(session)
    base_revision = current.get('project_revision') or 'empty'
    if capability != 'unity.prototype.compose':
        payload['expected_revision'] = base_revision
        payload['run_id'] = request_id if payload.get('operation') == 'enter' else current.get('run_id')
        payload_json = json.dumps(payload, separators=(',', ':'))
    change = {'change_set_id': authorization['change_set_id'], 'base_version': base_revision,
        'target_integration': 'unity', 'command': capability, 'target_object_ids': [target],
        'approval_state': 'approved', 'previous_values': {}, 'proposed_values': payload,
        'proposed_payload_json': payload_json, 'rationale': 'Authorized bounded prototype action',
        'expected_result': 'Actual Editor/game state and evidence readback', 'impact_scope': str(session.project_root),
        'risk': 'low', 'validation_plan': ['Read actual state, errors and requested artifacts'],
        'rollback_plan': ['Exit Play Mode; retain saved scene and action evidence']}
    batch = {'requestId': request_id, 'command': capability, 'projectId': session.workspace_root.name,
        'projectRoot': str(session.project_root), 'baseVersion': base_revision, 'executionMode': 'live',
        'payloadJson': payload_json, 'changeSetJson': json.dumps(change)}
    replay = (session.mailbox / (request_id + '.result.json')).exists()
    result = session._exchange(request_id, capability, batch=batch,
        authorization={**authorization, 'session_id': session._config['session_id']}, timeout=90)
    decoded = _decode(result)
    decoded['mode'] = 'cached' if replay or decoded.get('effects_reused') else 'live'
    decoded['change_set'] = change
    return decoded


def compose_prototype(session, *, request_id, spec, authorization):
    normalized = PrototypeSpec.model_validate(spec).model_dump(mode='json')
    return _execute(session, request_id, 'unity.prototype.compose', normalized, authorization, normalized['prototype_id'])


def play_prototype(session, *, request_id, operation, input=None, authorization):
    payload = PrototypePlayPayload(operation=operation, input=PrototypeInput.model_validate(input or {})).model_dump(mode='json')
    capability = 'unity.prototype.capture' if operation == 'capture' else 'unity.prototype.play'
    return _execute(session, request_id, capability, payload, authorization, session.workspace_root.name)
