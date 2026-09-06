"""Transactional production projections and immutable artifact version copies."""
import mimetypes
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from sceneops_harness import HarnessError
from .production_catalog import module_catalog
from .production_models import ProductionArtifact, ProductionEvents, ProductionSnapshot, ProductionStep
from .task_models import AgentTaskEvent, AgentTaskRecord, identifier, now


class ProductionStore:
    def __init__(self, database_path, data_dir, records):
        self.records = records
        self.data_dir = Path(data_dir).resolve()
        self.workspace_base = self.data_dir / 'agent-workspaces'
        self.snapshots = self.data_dir / 'production-artifacts'
        with records.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS production_steps (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, task_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS production_steps_project ON production_steps(project_id);
                CREATE TABLE IF NOT EXISTS production_artifact_identity (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    UNIQUE(project_id, source_path));
                CREATE TABLE IF NOT EXISTS production_artifact_versions (
                    id TEXT NOT NULL, version INTEGER NOT NULL, project_id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(id, version));
            ''')

    def upsert_step(self, step):
        step = ProductionStep.model_validate(step)
        with self.records.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            task = self.records._read(connection, step.task_id)
            if task.project_id != step.project_id:
                raise HarnessError('PRODUCTION_SCOPE_DENIED', '步骤不属于当前项目任务。')
            prior = connection.execute('SELECT task_id,project_id,body FROM production_steps WHERE id=?', (step.id,)).fetchone()
            if prior and prior[:2] != (step.task_id, step.project_id):
                raise HarnessError('PRODUCTION_SCOPE_DENIED', '步骤标识已属于其他任务，不能替换。')
            if prior:
                step.artifact_ids = ProductionStep.model_validate_json(prior[2]).artifact_ids
            if step.verification_result:
                for reference in step.verification_result.artifact_refs:
                    artifact = connection.execute('''SELECT 1 FROM production_artifact_versions
                        WHERE id=? AND version=? AND project_id=?''',
                        (reference.artifact_id, reference.version, step.project_id)).fetchone()
                    if not artifact:
                        raise HarnessError('VERIFICATION_EVIDENCE_INVALID',
                                           '验证记录引用的产物版本不属于当前项目。')
            connection.execute('INSERT INTO production_steps VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                               (step.id, step.project_id, step.task_id, step.model_dump_json()))
            self.records._event(connection, task, 'production.step.updated', {'step': step.model_dump(mode='json')})
        return step

    @staticmethod
    def _open_regular(path):
        """Walk canonical absolute components with no-follow, including ancestors."""
        path = Path(path)
        if not path.is_absolute() or '..' in path.parts:
            raise HarnessError('ARTIFACT_SCOPE_DENIED', '产物路径不是规范绝对路径。')
        descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:-1]:
                next_descriptor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
            source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        except OSError as error:
            raise HarnessError('ARTIFACT_UNAVAILABLE', '产物不存在或路径包含符号链接。') from error
        finally:
            os.close(descriptor)
        metadata = os.fstat(source)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 512 * 1024 * 1024:
            os.close(source)
            raise HarnessError('ARTIFACT_UNAVAILABLE', '产物必须是 512 MB 以内的普通文件。')
        return os.fdopen(source, 'rb'), metadata

    @staticmethod
    def _format(path):
        suffix = path.suffix.lower()
        if suffix in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
            return 'image', mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if suffix in {'.glb', '.gltf', '.fbx', '.obj', '.blend'}:
            return 'model', {'glb': 'model/gltf-binary', 'gltf': 'model/gltf+json'}.get(suffix[1:], 'application/octet-stream')
        if suffix in {'.wav', '.mp3', '.ogg', '.m4a'}:
            return 'audio', mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if suffix in {'.txt', '.md', '.json', '.py', '.cs', '.ts', '.tsx'}:
            return 'text', 'text/plain'
        # HTML and SVG are deliberately never served as active inline documents.
        return 'file', 'application/octet-stream'

    @staticmethod
    def _copy_snapshot(source, metadata, destination):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.copy-', delete=False) as output:
                temporary = output.name
                remaining = metadata.st_size
                while remaining:
                    chunk = source.read(min(remaining, 65536))
                    if not chunk:
                        raise HarnessError('ARTIFACT_CHANGED', '复制期间产物发生变化，未发布该版本。')
                    output.write(chunk)
                    remaining -= len(chunk)
                output.flush()
                os.fsync(output.fileno())
            after = os.fstat(source.fileno())
            if source.read(1) or (after.st_size, after.st_mtime_ns) != (metadata.st_size, metadata.st_mtime_ns):
                raise HarnessError('ARTIFACT_CHANGED', '复制期间产物发生变化，未发布该版本。')
            os.link(temporary, destination)
        finally:
            if temporary is not None:
                os.unlink(temporary)

    @contextmanager
    def _artifact_transaction(self):
        copies = []
        try:
            with self.records.connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                yield connection, copies
        except BaseException:
            # Only discard this transaction's unpublished copies, never sources.
            for path in copies:
                path.unlink(missing_ok=True)
            raise

    def record_artifact(self, task, step_id, module_id, path):
        task = self.records.get(task.id)
        root = self.workspace_base / task.project_id
        path = Path(path)
        path = path if path.is_absolute() else root / path
        if (not task.grant or task.grant.workspace_root != str(root)
                or not self.records.owns_workspace(task.project_id, root)
                or not path.is_relative_to(root) or '..' in path.parts):
            raise HarnessError('ARTIFACT_SCOPE_DENIED', '产物不属于已登记的任务工作区。')
        relative = path.relative_to(root)
        if any(part.startswith('.') for part in relative.parts):
            raise HarnessError('ARTIFACT_SCOPE_DENIED', '隐藏文件不是可发布产物。')
        source, metadata = self._open_regular(path)
        with source, self._artifact_transaction() as (connection, copies):
            row = connection.execute('SELECT body FROM production_steps WHERE id=?', (step_id,)).fetchone()
            if not row:
                raise HarnessError('PRODUCTION_STEP_REQUIRED', '产物必须关联已持久化步骤。')
            step = ProductionStep.model_validate_json(row[0])
            if (step.task_id, step.project_id, step.module_id) != (task.id, task.project_id, module_id):
                raise HarnessError('ARTIFACT_SCOPE_DENIED', '产物的步骤归属不一致。')
            row = connection.execute('SELECT id FROM production_artifact_identity WHERE project_id=? AND source_path=?',
                                     (task.project_id, relative.as_posix())).fetchone()
            artifact_id = row[0] if row else identifier('artifact')
            version = connection.execute('SELECT COALESCE(MAX(version),0)+1 FROM production_artifact_versions WHERE id=?',
                                         (artifact_id,)).fetchone()[0]
            destination = self.snapshots / artifact_id / str(version)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.parent.resolve() != destination.parent:
                raise HarnessError('ARTIFACT_SCOPE_DENIED', '产物版本目录包含符号链接。')
            self._copy_snapshot(source, metadata, destination)
            copies.append(destination)
            kind, media_type = self._format(relative)
            artifact = ProductionArtifact(id=artifact_id, version=version, project_id=task.project_id,
                task_id=task.id, step_id=step_id, module_id=module_id, name=relative.name,
                source_path=relative.as_posix(), kind=kind, media_type=media_type,
                size_bytes=metadata.st_size, created_at=now().isoformat())
            connection.execute('INSERT OR IGNORE INTO production_artifact_identity VALUES(?,?,?)',
                               (artifact_id, task.project_id, relative.as_posix()))
            connection.execute('INSERT INTO production_artifact_versions VALUES(?,?,?,?)',
                               (artifact_id, version, task.project_id, artifact.model_dump_json()))
            if artifact_id not in step.artifact_ids:
                step.artifact_ids.append(artifact_id)
                connection.execute('UPDATE production_steps SET body=? WHERE id=?', (step.model_dump_json(), step_id))
            self.records._event(connection, task, 'production.artifact.recorded', {'artifact': artifact.model_dump(mode='json')})
        return artifact

    def snapshot(self, project_id):
        with self.records.connect() as connection:
            connection.execute('BEGIN')
            cursor = connection.execute('SELECT COALESCE(MAX(sequence),0) FROM agent_task_events WHERE project_id=?', (project_id,)).fetchone()[0]
            tasks = [AgentTaskRecord.model_validate_json(row[0]) for row in connection.execute(
                'SELECT body FROM agent_tasks WHERE project_id=? ORDER BY rowid', (project_id,))]
            steps = [ProductionStep.model_validate_json(row[0]) for row in connection.execute(
                'SELECT body FROM production_steps WHERE project_id=? ORDER BY rowid', (project_id,))]
            artifacts = [ProductionArtifact.model_validate_json(row[0]) for row in connection.execute('''
                SELECT body FROM production_artifact_versions WHERE project_id=? ORDER BY id,version''', (project_id,))]
            task_by_id = {task.id: task for task in tasks}
            for step in steps:
                task = task_by_id[step.task_id]
                if step.state == 'running' and task.status in ('cancelled', 'failed', 'interrupted', 'blocked', 'needs_approval'):
                    step.state = task.status if task.status in ('cancelled', 'failed', 'blocked') else 'blocked'
                    step.reason = task.reason
        return ProductionSnapshot(project_id=project_id, cursor=cursor, tasks=tasks, steps=steps,
                                  artifacts=artifacts, modules=module_catalog())

    def events(self, project_id, after=0):
        with self.records.connect() as connection:
            rows = connection.execute('''SELECT sequence,task_id,project_id,occurred_at,event_type,payload
                FROM agent_task_events WHERE project_id=? AND sequence>? ORDER BY sequence LIMIT 200''', (project_id, after)).fetchall()
        import json
        events = [AgentTaskEvent(sequence=row[0], task_id=row[1], project_id=row[2], occurred_at=row[3],
            event_type=row[4], payload=json.loads(row[5])) for row in rows]
        return ProductionEvents(events=events, next_cursor=events[-1].sequence if events else after)

    def artifact_content(self, project_id, artifact_id, version=None):
        with self.records.connect() as connection:
            row = connection.execute('''SELECT body FROM production_artifact_versions
                WHERE project_id=? AND id=? AND (? IS NULL OR version=?) ORDER BY version DESC LIMIT 1''',
                (project_id, artifact_id, version, version)).fetchone()
        if not row:
            raise HarnessError('ARTIFACT_NOT_FOUND', '此项目没有该产物版本。')
        artifact = ProductionArtifact.model_validate_json(row[0])
        stream, _ = self._open_regular(self.snapshots / artifact.id / str(artifact.version))
        return stream, artifact
