"""Durable workspace source identities from actual files, independent of action history."""
import json
from uuid import uuid4

from sceneops_harness import HarnessError
from .code_workspace import read_source, source_inventory, source_path, PROJECT_DEMO_DERIVED_PATHS
from .demo_workbench_models import DemoSourceEntry


def _table(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS agent_workspace_sources (
        project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, source_id TEXT NOT NULL,
        body TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id, source_id))''')


def _load(connection, project_id, workspace_id):
    _table(connection)
    return [json.loads(row[0]) for row in connection.execute(
        'SELECT body FROM agent_workspace_sources WHERE project_id=? AND workspace_id=?',
        (project_id, workspace_id))]


def _save(connection, project_id, workspace_id, entry):
    connection.execute('INSERT OR REPLACE INTO agent_workspace_sources VALUES(?,?,?,?)',
        (project_id, workspace_id, entry['id'], json.dumps(entry, ensure_ascii=False)))


def workspace_sources(service, task, *, native_round=False):
    """Observe real content; retain deleted identities without offering stale edit targets."""
    card = task.authorization_card
    service.project_demo_workspace(task.project_id, card.workspace_id, expected_root=card.workspace_root)
    files, truncated = source_inventory(card.workspace_root)
    native_round = native_round or bool(getattr(task, 'owner_pid', None)
        and getattr(task, 'observations', {}).get('native_production'))
    legacy = {}
    for number, action in enumerate(task.actions, 1):
        if (action.action.capability_id == 'code.file.write' and action.state == 'succeeded'
                and action.effect_state == 'COMMITTED'):
            path = action.action.inputs['path']
            first = legacy.get(path, {}).get('id', action.request_id)
            legacy[path] = {'id': first, 'latest_write_request_id': action.request_id,
                            'source_version': number}
    with service.records.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        previous = _load(connection, task.project_id, card.workspace_id)
        by_path = {entry['path']: entry for entry in previous if not entry.get('deleted')}
        seen, result = set(), []
        for file in files:
            path = file['path']
            if path in PROJECT_DEMO_DERIVED_PATHS:
                continue
            content = read_source(card.workspace_root, path)
            if content is None:
                continue
            seen.add(path)
            entry = by_path.get(path)
            provenance = legacy.get(path)
            changed = entry is None or entry['content'] != content
            if entry is None:
                entry = {'id': provenance['id'] if provenance else 'source_' + uuid4().hex,
                    'path': path, 'content': content, 'source_version': 1,
                    'latest_write_request_id': None, 'origin': 'workspace',
                    'source_task_id': None, 'deleted': False, 'history': []}
                if provenance:
                    entry.update(provenance, origin='typed-action', source_task_id=task.id)
            elif entry['content'] != content:
                entry['history'].append({key: entry[key] for key in
                    ('path', 'content', 'source_version', 'source_task_id', 'origin')})
                entry.update(content=content, source_version=entry['source_version'] + 1,
                             origin='workspace', source_task_id=None, latest_write_request_id=None)
            if native_round and changed:
                entry.update(origin='native-workspace', source_task_id=task.id)
            if provenance:
                action = next(item for item in reversed(task.actions)
                    if item.request_id == provenance['latest_write_request_id'])
                if action.action.inputs.get('content') == content:
                    entry.update(latest_write_request_id=provenance['latest_write_request_id'],
                                 origin='typed-action', source_task_id=task.id)
            _save(connection, task.project_id, card.workspace_id, entry)
            result.append(DemoSourceEntry.model_validate({key: value for key, value in entry.items()
                if key not in ('history', 'deleted')}))
        if not truncated:
            for entry in previous:
                if not entry.get('deleted') and entry['path'] not in seen:
                    entry.update(deleted=True, source_version=entry['source_version'] + 1)
                    _save(connection, task.project_id, card.workspace_id, entry)
    return result, truncated


def source_registrations(service, task):
    from .demo_workbench_models import DemoSourceRegistration
    workspace_sources(service, task)
    with service.records.connect() as connection:
        return [DemoSourceRegistration.model_validate(entry) for entry in
                _load(connection, task.project_id, task.authorization_card.workspace_id)]


def confirm_source_rename(service, task, source_id, new_path, expected_version, expected_target_version=None):
    """Record an explicitly confirmed move; never infer identity from similar contents."""
    source_path(new_path)
    card = task.authorization_card
    service.project_demo_workspace(task.project_id, card.workspace_id, expected_root=card.workspace_root)
    if new_path in PROJECT_DEMO_DERIVED_PATHS:
        raise HarnessError('CODE_PATH_DERIVED', '托管源码不能作为普通源码的重命名目标。')
    with service.records.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        entries = _load(connection, task.project_id, card.workspace_id)
        entry = next((value for value in entries if value['id'] == source_id), None)
        if entry is None or entry['source_version'] != expected_version:
            raise HarnessError('DEMO_SOURCE_CONFLICT', '源码登记已改变，请重新读取。')
        target = next((value for value in entries if value['path'] == new_path and not value.get('deleted')), None)
        if target and (target['id'] == source_id or target['source_version'] != expected_target_version):
            raise HarnessError('DEMO_SOURCE_CONFLICT', '请明确确认目标文件当前版本，才能合并重命名身份。')
        content = read_source(card.workspace_root, new_path)
        if read_source(card.workspace_root, entry['path']) is not None or content is None:
            raise HarnessError('DEMO_SOURCE_CONFLICT', '尚未确认原文件移除且新文件存在。')
        if target:
            if target['content'] != content:
                raise HarnessError('DEMO_SOURCE_CONFLICT', '目标源码已改变，请重新读取。')
            target.update(deleted=True, source_version=target['source_version'] + 1, renamed_into=source_id)
            _save(connection, task.project_id, card.workspace_id, target)
        entry['history'].append({key: entry[key] for key in
            ('path', 'content', 'source_version', 'source_task_id', 'origin')})
        entry.update(path=new_path, content=content, deleted=False,
            source_version=entry['source_version'] + 1, origin='workspace',
            source_task_id=None, latest_write_request_id=None)
        _save(connection, task.project_id, card.workspace_id, entry)
        return entry['id']
