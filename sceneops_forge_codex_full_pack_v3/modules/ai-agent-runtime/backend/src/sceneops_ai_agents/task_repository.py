"""Task-level aggregate and journal; execution records stay in Harness tables."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sceneops_harness import HarnessError
from .task_models import AgentTaskEvent, AgentTaskEvents, AgentTaskRecord, now


class AgentTaskRepository:
    @staticmethod
    def mutation_capabilities():
        mutations = {'blender.asset.begin', 'blender.asset.edit', 'blender.asset.publish', 'blender.asset.create', 'blender.asset.export', 'unity.asset.import',
                     'codex.task.execute', 'agent.task.execute'}
        mutations.update({'unity.prototype.compose', 'unity.prototype.play',
                          'unity.prototype.capture', 'unity.prototype.verify'})
        mutations.update({'code.demo_assets.install', 'code.demo_content.materialize', 'code.demo_runtime.upgrade', 'code.file.write',
                          'code.dependencies.prepare', 'code.project.check',
                          'code.project.build', 'code.preview.start', 'code.preview.stop'})
        mutations.add('environment.object.transform')
        mutations.update({'code.project.build_test', 'code.browser.interact'})
        mutations.update({'project.asset.door.create', 'project.asset.door.update',
                          'environment.object.place', 'environment.demo_object.transform',
                          'environment.key_door.configure', 'environment.object.remove', 'environment.asset.rebind'})
        mutations.update({'blender.asset.derive_unity','unity.content.import','unity.content.edit',
                          'unity.content.focus','unity.content.save','unity.content.play'})
        return mutations

    @staticmethod
    def _writes_settled(task):
        mutations = AgentTaskRepository.mutation_capabilities()
        return not any(action.state in ('running', 'uncertain')
                       or action.effect_state in ('STAGED', 'APPLIED', 'UNKNOWN')
                       for action in task.actions if action.action.capability_id in mutations)

    @staticmethod
    def safe_to_release(task):
        if any(v['status'] in ('opening', 'editing', 'exported', 'saved')
               for v in task.observations.get('blender_candidates', {}).values()):
            return False
        if task.observations.get('cleanup_uncertain') is True:
            return False
        handoff = task.observations.get('project_claim_handoff')
        if (isinstance(handoff, dict) and handoff.get('state') == 'continued'
                and task.status in ('review_required', 'cancelled', 'failed', 'interrupted', 'needs_approval') and task.owner_pid is None
                and task.grant is not None and task.grant.revoked):
            return True
        mutations = AgentTaskRepository.mutation_capabilities()
        writes = [action for action in task.actions if action.action.capability_id in mutations]
        if not AgentTaskRepository._writes_settled(task):
            return False
        if task.status in ('completed', 'review_required'):
            return True
        if task.authorization_card.task_profile == 'card-development':
            return task.status in ('cancelled', 'failed', 'interrupted', 'needs_approval')
        return task.status in ('cancelled', 'failed', 'interrupted', 'needs_approval') and not any(
            action.state == 'succeeded' for action in writes)

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_task_archives (
                    task_id TEXT PRIMARY KEY, archived_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_task_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    project_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS agent_task_events_task ON agent_task_events(task_id,sequence);
                CREATE INDEX IF NOT EXISTS agent_task_events_project ON agent_task_events(project_id,sequence);
                CREATE TABLE IF NOT EXISTS agent_project_workspaces (
                    project_id TEXT PRIMARY KEY, workspace_root TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_project_claims (
                    project_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, state TEXT NOT NULL);
            """)
            legacy = any(index[2] and [field[2] for field in connection.execute(
                'PRAGMA index_info("' + index[1].replace('"', '""') + '")')] == ['project_id']
                for index in connection.execute('PRAGMA index_list(agent_tasks)'))
            if legacy:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute('ALTER TABLE agent_tasks RENAME TO agent_tasks_single_project')
                connection.execute('CREATE TABLE agent_tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)')
                connection.execute('INSERT INTO agent_tasks SELECT task_id,project_id,body FROM agent_tasks_single_project')
                connection.execute('DROP TABLE agent_tasks_single_project')
            connection.execute('CREATE INDEX IF NOT EXISTS agent_tasks_project ON agent_tasks(project_id)')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _read(connection, task_id):
        row = connection.execute("SELECT body FROM agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise HarnessError("TASK_NOT_FOUND", "没有此任务。")
        return AgentTaskRecord.model_validate_json(row[0]).model_copy(update={
            "archived": connection.execute("SELECT 1 FROM agent_task_archives WHERE task_id=?", (task_id,)).fetchone() is not None})

    def get(self, task_id):
        with self.connect() as connection:
            return self._read(connection, task_id)

    def create(self, task):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO agent_tasks VALUES(?,?,?)", (task.id, task.project_id, task.model_dump_json()))
            self._event(connection, task, "agent.task.prepared", {"status": task.status})
        return task

    @staticmethod
    def _event(connection, task, event_type, payload):
        connection.execute("INSERT INTO agent_task_events(task_id,project_id,occurred_at,event_type,payload) VALUES(?,?,?,?,?)",
                           (task.id, task.project_id, now().isoformat(), event_type, json.dumps(payload, ensure_ascii=False)))

    def update(self, task_id, mutate, event_type, payload=None):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = self._read(connection, task_id)
            mutate(task)
            if event_type in ('agent.task.authorized', 'agent.project_demo.goal_added') and task.status == 'queued':
                self._claim_project(connection, task)
            if event_type == 'agent.task.worker_released':
                safe = self.safe_to_release(task)
                if safe:
                    connection.execute('DELETE FROM agent_project_claims WHERE project_id=? AND task_id=?',
                                       (task.project_id, task.id))
                elif task.status not in ('queued', 'running', 'blocked'):
                    connection.execute("UPDATE agent_project_claims SET state='review_required' WHERE project_id=? AND task_id=?",
                                       (task.project_id, task.id))
            task.updated_at = now()
            connection.execute("UPDATE agent_tasks SET body=? WHERE task_id=? AND project_id=?",
                               (task.model_dump_json(), task.id, task.project_id))
            self._event(connection, task, event_type, payload or {"status": task.status, "reason": task.reason})
        return task

    @staticmethod
    def _claim_project(connection, task):
        prior = connection.execute('SELECT task_id,state FROM agent_project_claims WHERE project_id=?',
                                   (task.project_id,)).fetchone()
        if prior and prior[1] == 'manual_edit':
            raise HarnessError('PROJECT_EXECUTION_BUSY', '工作台正在保存此作品，不能同时启动制作。')
        if prior and prior[0] != task.id:
            other = AgentTaskRepository._read(connection, prior[0])
            if AgentTaskRepository.safe_to_release(other) and other.owner_pid is None:
                connection.execute('DELETE FROM agent_project_claims WHERE project_id=? AND task_id=?',
                                   (task.project_id, other.id))
            elif AgentTaskRepository._can_continue_typed_project(other, task):
                AgentTaskRepository._handoff_typed_project(connection, other, task)
                connection.execute('DELETE FROM agent_project_claims WHERE project_id=? AND task_id=?',
                                   (task.project_id, other.id))
            elif AgentTaskRepository._can_continue_native_claim(other, task, prior[1]):
                AgentTaskRepository._handoff_native_claim(connection, other, task)
                connection.execute('DELETE FROM agent_project_claims WHERE project_id=? AND task_id=?',
                                   (task.project_id, other.id))
            else:
                raise HarnessError('PROJECT_EXECUTION_BUSY', '此项目已有执行或尚待核查的写入，不能并发开始其他任务。')
        # Existing pre-migration tasks may still hold a grant but have no claim row.
        for row in connection.execute('SELECT body FROM agent_tasks WHERE project_id=? AND task_id<>?',
                                      (task.project_id, task.id)):
            other = AgentTaskRecord.model_validate_json(row[0])
            if other.grant and (not AgentTaskRepository.safe_to_release(other) or other.owner_pid is not None):
                raise HarnessError('PROJECT_EXECUTION_BUSY', '此项目先前的执行尚未完成核查，不能开始其他写入。')
        # Card worktrees are owned by the workspace repository's (project, card) registration.
        # Keep project serialization, but never replace the legacy one-project workspace mapping.
        if task.authorization_card.task_profile not in ('card-development','unity-asset-edit','project-export-agent'):
            owner = connection.execute('SELECT workspace_root FROM agent_project_workspaces WHERE project_id=?',
                                       (task.project_id,)).fetchone()
            if owner and owner[0] != task.grant.workspace_root:
                raise HarnessError('TASK_SCOPE_DENIED', '已记录的项目目录与授权不一致。')
            connection.execute('INSERT OR IGNORE INTO agent_project_workspaces VALUES(?,?,?)',
                               (task.project_id, task.grant.workspace_root, now().isoformat()))
        connection.execute("INSERT OR IGNORE INTO agent_project_claims VALUES(?,?,'active')", (task.project_id, task.id))
        connection.execute("UPDATE agent_project_claims SET state='active' WHERE project_id=? AND task_id=?",
                           (task.project_id, task.id))

    @contextmanager
    def manual_edit(self, task):
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute('SELECT 1 FROM agent_project_claims WHERE project_id=?',
                                  (task.project_id,)).fetchone():
                raise HarnessError('PROJECT_EXECUTION_BUSY', '作品有正在执行或待核查的修改，请先查看制作记录。')
            connection.execute("INSERT INTO agent_project_claims VALUES(?,?,'manual_edit')",
                               (task.project_id, task.id))
        try:
            yield
        finally:
            with self.connect() as connection:
                connection.execute("DELETE FROM agent_project_claims WHERE project_id=? AND task_id=? AND state='manual_edit'",
                                   (task.project_id, task.id))

    @staticmethod
    def _can_continue_typed_project(previous, current):
        if (previous.authorization_card.task_profile != 'project-demo-agent'
                or current.authorization_card.task_profile != 'project-demo-agent'
                or previous.authorization_card.execution_mode != 'typed-tools'
                or current.authorization_card.execution_mode != 'agent-full-access'
                or previous.status not in ('cancelled', 'failed', 'interrupted', 'needs_approval')
                or previous.owner_pid is not None or previous.grant is None or current.grant is None
                or previous.observations.get('cleanup_uncertain') is True):
            return False
        scope = lambda task: (task.project_id, task.grant.workspace_root,
                              task.grant.workspace_id, task.grant.alignment_id)
        if scope(previous) != scope(current):
            return False
        if any(item['status'] in ('opening', 'editing', 'exported', 'saved')
               for item in previous.observations.get('blender_candidates', {}).values()):
            return False
        return AgentTaskRepository._writes_settled(previous)

    @staticmethod
    def _handoff_typed_project(connection, previous, current):
        previous.grant.revoked = True
        previous.observations['project_claim_handoff'] = {
            'state': 'continued', 'to_task_id': current.id, 'previous_status': previous.status,
            'transferred_at': now().isoformat(), 'workspace_root': current.grant.workspace_root,
        }
        current.observations['project_claim_continuation'] = {
            'from_task_id': previous.id, 'previous_status': previous.status,
            'workspace_root': current.grant.workspace_root,
            'notice': '保留旧任务实际源码和失败记录；先读取工作区，再增量继续，不重放旧动作。',
        }
        connection.execute('UPDATE agent_tasks SET body=? WHERE task_id=? AND project_id=?',
                           (previous.model_dump_json(), previous.id, previous.project_id))
        AgentTaskRepository._event(connection, previous, 'agent.task.claim_handed_off',
                                  {'to_task_id': current.id, 'previous_status': previous.status})

    @staticmethod
    def _conversation_id(task):
        context = task.observations.get('card_context')
        if not isinstance(context, dict):
            return None
        value = context.get('conversation_id')
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _can_continue_native_claim(previous, current, claim_state):
        """Allow an explicit same-thread authorization to continue a stopped native run.

        The prior action remains UNKNOWN. This only transfers serialization ownership after
        the worker has stopped and a Git workspace snapshot is available; it does not replay
        or mark the previous action as verified.
        """
        if previous.observations.get('native_production') and current.observations.get('native_production'):
            session_id = previous.observations.get('native_session_id')
            return (claim_state == 'review_required'
                and previous.status in ('needs_approval', 'cancelled', 'failed', 'interrupted')
                and previous.owner_pid is None and previous.observations.get('cleanup_uncertain') is not True
                and previous.grant is not None and previous.grant.revoked and current.grant is not None
                and bool(session_id) and current.observations.get('native_session_id') == session_id
                and current.observations.get('native_parent_task_id') == previous.id
                and previous.project_id == current.project_id
                and previous.provider_id == current.provider_id
                and previous.grant.workspace_root == current.grant.workspace_root
                and previous.grant.workspace_id == current.grant.workspace_id
                and isinstance(previous.observations.get('native_workspace_changes'), dict)
                and previous.observations['native_workspace_changes'].get('available') is True)
        if (previous.authorization_card.task_profile == 'project-export-agent'
                and current.authorization_card.task_profile == 'project-export-agent'):
            return (claim_state == 'review_required'
                and previous.status in ('needs_approval', 'cancelled', 'failed', 'interrupted')
                and previous.owner_pid is None and previous.observations.get('cleanup_uncertain') is not True
                and previous.grant is not None and previous.grant.revoked and current.grant is not None
                and previous.authorization_card.export_id == current.authorization_card.export_id
                and previous.grant.workspace_root == current.grant.workspace_root
                and previous.project_id == current.project_id)
        if (claim_state != 'review_required' or previous.status != 'needs_approval'
                or previous.owner_pid is not None
                or previous.observations.get('cleanup_uncertain') is True
                or previous.grant is None or not previous.grant.revoked
                or current.grant is None):
            return False
        if (previous.authorization_card.task_profile != 'card-development'
                or current.authorization_card.task_profile != 'card-development'
                or previous.authorization_card.execution_mode != 'agent-full-access'
                or current.authorization_card.execution_mode != 'agent-full-access'):
            return False
        previous_conversation = AgentTaskRepository._conversation_id(previous)
        current_conversation = AgentTaskRepository._conversation_id(current)
        if previous_conversation is None or previous_conversation != current_conversation:
            return False
        previous_scope = (previous.project_id, previous.grant.workspace_root,
                          previous.grant.card_id, previous.grant.branch)
        current_scope = (current.project_id, current.grant.workspace_root,
                         current.grant.card_id, current.grant.branch)
        if previous_scope != current_scope:
            return False
        snapshot = previous.observations.get('native_workspace_changes')
        if not isinstance(snapshot, dict) or snapshot.get('available') is not True:
            return False
        unresolved = [action for action in previous.actions
                      if action.action.capability_id in AgentTaskRepository.mutation_capabilities()
                      and (action.state in ('running', 'uncertain')
                           or action.effect_state in ('STAGED', 'APPLIED', 'UNKNOWN'))]
        return bool(unresolved) and all(
            action.action.capability_id == 'agent.task.execute'
            and action.state == 'uncertain' and action.effect_state == 'UNKNOWN'
            for action in unresolved)

    @staticmethod
    def _handoff_native_claim(connection, previous, current):
        transferred_at = now()
        snapshot = ({} if previous.authorization_card.task_profile == 'project-export-agent'
                    else previous.observations['native_workspace_changes'])
        handoff = {
            'state': 'continued',
            'to_task_id': current.id,
            'conversation_id': AgentTaskRepository._conversation_id(current),
            'workspace_root': current.grant.workspace_root,
            'transferred_at': transferred_at.isoformat(),
            'notice': '保留上一轮实际文件状态，由同一对话的新授权继续；未把未知写入标记为已验证。',
        }
        previous.observations['project_claim_handoff'] = handoff
        previous.status = 'review_required'
        previous.reason = '上一轮 Agent 已停止；现有修改已保留，并由同一对话的新任务继续。功能结果仍待审阅。'
        previous.updated_at = transferred_at
        current.observations['project_claim_continuation'] = {
            'from_task_id': previous.id,
            'conversation_id': handoff['conversation_id'],
            'workspace_root': handoff['workspace_root'],
            'workspace_change_totals': snapshot.get('totals', {}),
            'notice': '先检查当前工作区与未提交改动，再增量继续；不得重放上一轮命令或假定其已完成。',
        }
        connection.execute('UPDATE agent_tasks SET body=? WHERE task_id=? AND project_id=?',
                           (previous.model_dump_json(), previous.id, previous.project_id))
        AgentTaskRepository._event(connection, previous, 'agent.task.claim_handed_off', {
            'to_task_id': current.id,
            'conversation_id': handoff['conversation_id'],
            'workspace_change_totals': snapshot.get('totals', {}),
        })

    def owns_workspace(self, project_id, workspace_root):
        with self.connect() as connection:
            row = connection.execute('SELECT workspace_root FROM agent_project_workspaces WHERE project_id=?',
                                     (project_id,)).fetchone()
        return bool(row and row[0] == str(workspace_root))

    def owns_claim(self, task):
        with self.connect() as connection:
            row = connection.execute('SELECT task_id,state FROM agent_project_claims WHERE project_id=?',
                                     (task.project_id,)).fetchone()
        return bool(row and row[0] == task.id and row[1] == 'active')

    def recover_workspace_ownership(self, workspace_base):
        """Adopt only prior app execution evidence, never arbitrary existing paths."""
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            for row in connection.execute('SELECT body FROM agent_tasks'):
                task = AgentTaskRecord.model_validate_json(row[0])
                if task.grant is None:
                    continue
                if not self.safe_to_release(task):
                    state = 'active' if task.status in ('queued', 'running', 'blocked') else 'review_required'
                    connection.execute('INSERT OR IGNORE INTO agent_project_claims VALUES(?,?,?)',
                                       (task.project_id, task.id, state))
                    continue
                root = Path(task.grant.workspace_root)
                expected = workspace_base / task.project_id
                if root != expected or root.resolve() != root or not root.is_dir():
                    continue
                observation = task.observations.get('verification', {})
                typed_proof = (task.status == 'completed' and observation.get('verified') is True
                    and all(observation.get(tool, {}).get('workspace_root') == str(root) for tool in ('blender', 'unity')))
                prechange = task.observations.get('codex_prechange', {})
                codex_proof = (task.status == 'review_required' and prechange.get('workspace_root') == str(root)
                    and prechange.get('entries') == [] and task.observations.get('codex', {}).get('workspace_root') == str(root))
                if typed_proof or codex_proof:
                    connection.execute('INSERT OR IGNORE INTO agent_project_workspaces VALUES(?,?,?)',
                                       (task.project_id, str(root), now().isoformat()))

    def events(self, task_id, after=0):
        with self.connect() as connection:
            self._read(connection, task_id)
            rows = connection.execute("SELECT sequence,task_id,project_id,occurred_at,event_type,payload FROM agent_task_events WHERE task_id=? AND sequence>? ORDER BY sequence LIMIT 200",
                                      (task_id, after)).fetchall()
        events = [AgentTaskEvent(sequence=row[0], task_id=row[1], project_id=row[2], occurred_at=row[3],
                                 event_type=row[4], payload=json.loads(row[5])) for row in rows]
        return AgentTaskEvents(events=events, next_cursor=events[-1].sequence if events else after)

    def unfinished(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT body FROM agent_tasks").fetchall()
        tasks = [AgentTaskRecord.model_validate_json(row[0]) for row in rows]
        return [task for task in tasks if task.status in ("queued", "running", "cancel_pending")
                or (task.status == "blocked" and task.owner_pid is not None)]

    def archive(self, task_id, archived):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = self._read(connection, task_id)
            if archived and (task.status in ('queued', 'running', 'cancel_pending') or task.owner_pid is not None):
                raise HarnessError('TASK_RUNNING', '任务仍在执行，请停止或等待结束后再归档。')
            if task.archived == archived:
                return task
            if archived:
                connection.execute('INSERT INTO agent_task_archives VALUES (?,?)', (task_id, now().isoformat()))
            else:
                connection.execute('DELETE FROM agent_task_archives WHERE task_id=?', (task_id,))
            task.archived = archived
            self._event(connection, task, 'agent.task.archived' if archived else 'agent.task.restored', {'archived': archived})
            return task

    def list(self, project_id=None, archived=None):
        conditions, values = [], []
        if project_id is not None:
            conditions.append('t.project_id=?'); values.append(project_id)
        if archived is not None:
            conditions.append('a.task_id IS NOT NULL' if archived else 'a.task_id IS NULL')
        where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        limit = '' if archived is True else ' LIMIT 20'
        with self.connect() as connection:
            rows = connection.execute('SELECT t.body, a.task_id IS NOT NULL FROM agent_tasks t '
                'LEFT JOIN agent_task_archives a ON a.task_id=t.task_id' + where + ' ORDER BY t.rowid DESC' + limit, values).fetchall()
        return [AgentTaskRecord.model_validate_json(row[0]).model_copy(update={'archived': bool(row[1])}) for row in rows]
