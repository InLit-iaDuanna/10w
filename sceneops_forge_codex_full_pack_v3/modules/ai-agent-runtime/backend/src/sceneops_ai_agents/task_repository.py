"""Task-level aggregate and journal; execution records stay in Harness tables."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sceneops_harness import HarnessError
from .task_models import AgentTaskEvent, AgentTaskEvents, AgentTaskRecord, now


class AgentTaskRepository:
    @staticmethod
    def safe_to_release(task):
        if task.observations.get('cleanup_uncertain') is True:
            return False
        mutations = {'blender.asset.create', 'blender.asset.export', 'unity.asset.import', 'codex.task.execute'}
        mutations.update({'unity.prototype.compose', 'unity.prototype.play', 'unity.prototype.capture', 'unity.prototype.verify'})
        mutations.update({'code.file.write', 'code.dependencies.prepare', 'code.project.check',
                          'code.project.build', 'code.preview.start', 'code.preview.stop'})
        mutations.add('environment.object.transform')
        writes = [action for action in task.actions if action.action.capability_id in mutations]
        if any(action.state in ('running', 'uncertain') or action.effect_state in ('STAGED', 'APPLIED', 'UNKNOWN')
               for action in writes):
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
        return AgentTaskRecord.model_validate_json(row[0])

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
            if event_type == 'agent.task.authorized' and task.status == 'queued':
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
        prior = connection.execute('SELECT task_id FROM agent_project_claims WHERE project_id=?',
                                   (task.project_id,)).fetchone()
        if prior and prior[0] != task.id:
            raise HarnessError('PROJECT_EXECUTION_BUSY', '此项目已有执行或尚待核查的写入，不能并发开始其他任务。')
        # Existing pre-migration tasks may still hold a grant but have no claim row.
        for row in connection.execute('SELECT body FROM agent_tasks WHERE project_id=? AND task_id<>?',
                                      (task.project_id, task.id)):
            other = AgentTaskRecord.model_validate_json(row[0])
            if other.grant and (not AgentTaskRepository.safe_to_release(other) or other.owner_pid is not None):
                raise HarnessError('PROJECT_EXECUTION_BUSY', '此项目先前的执行尚未完成核查，不能开始其他写入。')
        # Card worktrees are owned by the workspace repository's (project, card) registration.
        # Keep project serialization, but never replace the legacy one-project workspace mapping.
        if task.authorization_card.task_profile != 'card-development':
            owner = connection.execute('SELECT workspace_root FROM agent_project_workspaces WHERE project_id=?',
                                       (task.project_id,)).fetchone()
            if owner and owner[0] != task.grant.workspace_root:
                raise HarnessError('TASK_SCOPE_DENIED', '已记录的项目目录与授权不一致。')
            connection.execute('INSERT OR IGNORE INTO agent_project_workspaces VALUES(?,?,?)',
                               (task.project_id, task.grant.workspace_root, now().isoformat()))
        connection.execute("INSERT OR IGNORE INTO agent_project_claims VALUES(?,?,'active')", (task.project_id, task.id))

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

    def list(self, project_id=None):
        with self.connect() as connection:
            if project_id is None:
                rows = connection.execute("SELECT body FROM agent_tasks ORDER BY rowid DESC LIMIT 20").fetchall()
            else:
                rows = connection.execute("SELECT body FROM agent_tasks WHERE project_id=? ORDER BY rowid DESC LIMIT 20", (project_id,)).fetchall()
        return [AgentTaskRecord.model_validate_json(row[0]) for row in rows]
