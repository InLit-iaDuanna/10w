"""Durable project-scoped exports with isolated sources and bounded adapters."""
import json
import os
import shutil
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .export_models import (ExportTask, ExportPlatformRun, ExportAttempt, ExportArtifact,
    ExportLog, ExportMessage, ExportSettings, CreateExportRequest, ExportMessageRequest)


def now():
    return datetime.now(timezone.utc).isoformat()


from .export_native import NativeExportMixin

class ExportService(NativeExportMixin):
    def __init__(self, root, resolve_project, adapter=None, agent_callback=None, redact_text=None, native_agent=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.resolve_project = resolve_project
        if adapter is None:
            from .export_packaging import LocalExportAdapter
            adapter = LocalExportAdapter()
        self.adapter, self.agent_callback = adapter, agent_callback
        self.redact_text = redact_text or (lambda text: text)
        self.lock = threading.RLock()
        self.native_agent = native_agent
        self.native_cancel_events = {}
        self.cancel_events = {}
        self.threads = []
        self.db = sqlite3.connect(self.root / 'exports.sqlite3', check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS exports (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS export_files (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, path TEXT NOT NULL)')
        self.db.commit()
        for (body,) in self.db.execute('SELECT body FROM exports').fetchall():
            task = ExportTask.model_validate_json(body)
            changed = False
            for native in task.native_runs:
                if native.status in ('queued', 'running'):
                    native.status, native.finished_at = 'interrupted', now()
                    native.error = '服务重启，执行已中断；请发送消息继续。'
                    changed = True
            for run in task.platforms:
                if run.status in ('queued', 'running'):
                    run.status = 'interrupted'
                    if run.attempts:
                        run.attempts[-1].status = 'interrupted'
                        run.attempts[-1].finished_at = now()
                    changed = True
            if changed:
                self._save(task)

    def _save(self, task):
        task.updated_at = now()
        task.revision += 1
        self.db.execute('INSERT OR REPLACE INTO exports VALUES (?,?,?)',
                        (task.id, task.project_id, task.model_dump_json()))
        self.db.commit()

    def get(self, project_id, task_id):
        self.resolve_project(project_id)
        with self.lock:
            row = self.db.execute('SELECT body FROM exports WHERE id=? AND project_id=?', (task_id, project_id)).fetchone()
            if not row:
                raise KeyError('导出任务不存在')
            return ExportTask.model_validate_json(row[0])

    def list(self, project_id):
        self.resolve_project(project_id)
        with self.lock:
            return [ExportTask.model_validate_json(row[0]) for row in self.db.execute(
                'SELECT body FROM exports WHERE project_id=? ORDER BY rowid DESC', (project_id,))]

    def create(self, project_id, request, previous_task_id=None):
        if request.execution_mode == 'native' and not request.accept_full_access:
            raise ValueError('电脑操作需要明确授权本次 Agent 完整访问')
        previous = self.get(project_id, previous_task_id) if previous_task_id else None
        project = self.resolve_project(project_id)
        source = Path(project['root_path']).resolve(strict=True)
        if not source.is_dir() or source == self.root or self.root.is_relative_to(source):
            raise ValueError('导出目录必须独立于源工程目录')
        task_id = str(uuid4())
        directory = self.root / task_id
        directory.mkdir()
        snapshot = directory / 'source'
        # Reject symlinks: build snapshots must never read outside the selected source.
        ignored = {'.git', 'node_modules', '.env', '.DS_Store', 'dist', 'build', '.sceneops', '.npmrc', '.yarnrc', '.pypirc', '.ssh', '.aws', '.gnupg'}
        def ignore(folder, names):
            excluded = [name for name in names if name in ignored or name.startswith('.env.') or Path(name).suffix.lower() in {'.jks', '.keystore', '.p12', '.pfx', '.pem', '.key'}]
            if any((Path(folder) / name).is_symlink() for name in names if name not in excluded):
                raise ValueError('源工程含符号链接，请使用工程内实际文件后导出')
            return excluded
        try:
            commit = self._source_commit(source)
            before = self._source_inventory(source, ignore)
            shutil.copytree(source, snapshot, ignore=ignore)
            if before != self._source_inventory(source, ignore) or commit != self._source_commit(source):
                raise ValueError('复制期间源码发生变化，请等待保存完成后重新导出')
        except Exception:
            shutil.rmtree(directory)
            raise
        source_version = f"{commit or 'saved'}:snapshot:{task_id}"
        settings = request.settings.model_copy(deep=True)
        settings.app_name = settings.app_name.strip() or project.get('name', 'Game')
        settings.app_id = settings.app_id or 'com.sceneops.p' + ''.join(c for c in project_id if c.isalnum()).lower()
        settings = ExportSettings.model_validate(settings.model_dump())
        task = ExportTask(id=task_id, project_id=project_id, source_version=source_version,
            settings=settings, created_at=now(), updated_at=now(), previous_task_id=previous_task_id,
            messages=[message.model_copy(deep=True) for message in previous.messages] if previous else [],
            platforms=[ExportPlatformRun(platform=p, status='pending' if request.execution_mode == 'native' else 'queued') for p in dict.fromkeys(request.platforms)],
            mode=getattr(self.adapter, 'mode', 'live'))
        if previous:
            task.messages.append(ExportMessage(id=str(uuid4()), role='system', created_at=now(),
                content='已从最新保存的源码建立新导出任务。先前任务的日志、产物和设备验收仅保留在原任务中，不作为当前版本的验证证据。'))
        with self.lock:
            self._save(task)
            if request.execution_mode == 'fixed':
                for run in task.platforms:
                    self._start(task, run.platform)
        if request.execution_mode == 'native':
            return self.native_message(project_id, task_id, ExportMessageRequest(content='请检查当前环境，补齐所需工具，并导出本任务选择的平台安装包。缺少构建依赖时自行安装，完成后提交产物报告。', execution_mode='native', accept_full_access=True))
        return self.get(project_id, task_id)

    def refresh_source(self, project_id, task_id):
        previous = self.get(project_id, task_id)
        request = CreateExportRequest(platforms=[run.platform for run in previous.platforms],
                                      settings=previous.settings.model_copy(deep=True),
                                      execution_mode='native' if previous.native_runs else 'fixed',
                                      accept_full_access=bool(previous.native_runs))
        return self.create(project_id, request, previous_task_id=previous.id)

    @staticmethod
    def _source_commit(source):
        result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else ''

    @staticmethod
    def _source_inventory(source, ignore):
        inventory = {}
        for folder, directories, files in os.walk(source):
            excluded = set(ignore(folder, directories + files))
            directories[:] = [name for name in directories if name not in excluded]
            for name in files:
                if name in excluded:
                    continue
                path = Path(folder) / name
                stat = path.stat()
                inventory[str(path.relative_to(source))] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        return inventory

    def consent(self, project_id, task_id, request):
        with self.lock:
            task = self.get(project_id, task_id)
            task.settings.allow_dependency_install = request.allow_dependency_install
            task.messages.append(ExportMessage(id=str(uuid4()), role='system', created_at=now(),
                content='用户已' + ('允许' if request.allow_dependency_install else '禁止') + '后续执行下载构建依赖；已有执行的授权不变。'))
            self._save(task)
            return task

    def _start(self, task, platform):
        if any(run.status in ('queued', 'running') for run in task.native_runs):
            raise ValueError('Agent 正在操作此导出，请等待完成或先取消 Agent')
        run = next((r for r in task.platforms if r.platform == platform), None)
        if run is None:
            raise KeyError('该平台不属于本次导出')
        if run.attempts and run.status in ('queued', 'running', 'succeeded'):
            raise ValueError('只能继续失败、取消或中断的平台')
        attempt = ExportAttempt(id=str(uuid4()), number=len(run.attempts)+1, status='queued', started_at=now(), settings=task.settings.model_copy(deep=True))
        run.attempts.append(attempt)
        run.status = 'queued'
        run.verification, run.verification_notes = 'pending', ''
        run.verification_device, run.verification_attempt_id = '', None
        self._save(task)
        cancel = threading.Event()
        self.cancel_events[(task.id, platform)] = cancel
        thread = threading.Thread(target=self._execute, args=(task.project_id, task.id, platform, attempt.id, task.settings.model_dump(), cancel), daemon=True)
        self.threads.append(thread)
        thread.start()

    def _change(self, project_id, task_id, platform, attempt_id, action):
        with self.lock:
            task = self.get(project_id, task_id)
            run = next(r for r in task.platforms if r.platform == platform)
            attempt = next(a for a in run.attempts if a.id == attempt_id)
            action(task, run, attempt)
            self._save(task)

    def _execute(self, project_id, task_id, platform, attempt_id, settings, cancel):
        directory = self.root / task_id
        work = directory / platform / attempt_id
        work.mkdir(parents=True)
        def emit(stage, message):
            def update(task, run, attempt):
                run.status = attempt.status = 'running'
                attempt.stage = stage
                attempt.logs.append(ExportLog(timestamp=now(), stage=stage, message=self.redact_text(message)))
            self._change(project_id, task_id, platform, attempt_id, update)
        try:
            # One prepared Web output is shared by all platforms and subsequent retries.
            with self._prepare_lock(task_id):
                marker = directory / 'prepared.json'
                if cancel.is_set():
                    raise InterruptedError('导出已取消')
                if marker.exists():
                    web = Path(json.loads(marker.read_text())['path'])
                else:
                    emit('prepare', '正在准备隔离的游戏构建')
                    web = self.adapter.prepare(directory / 'source', directory / ('web-' + attempt_id), settings, emit, cancel)
                    marker.write_text(json.dumps({'path': str(web)}))
            if cancel.is_set():
                raise InterruptedError('导出已取消')
            paths = self.adapter.build(platform, web, work, settings, emit, cancel)
            if cancel.is_set():
                raise InterruptedError('导出已取消')
            def success(task, run, attempt):
                for item in paths:
                    path = Path(item).resolve(strict=True)
                    if not path.is_relative_to(work.resolve()) or not path.is_file():
                        raise ValueError('构建产物不在本次执行目录内')
                    artifact_id = str(uuid4())
                    self.db.execute('INSERT INTO export_files VALUES (?,?,?)', (artifact_id, task_id, str(path)))
                    attempt.artifacts.append(ExportArtifact(id=artifact_id, name=path.name, size=path.stat().st_size,
                        download_url=f'/api/projects/{project_id}/exports/{task_id}/artifacts/{artifact_id}'))
                if not attempt.artifacts:
                    raise ValueError('构建没有生成可下载产物')
                run.status = attempt.status = 'succeeded'
                attempt.stage, attempt.finished_at = 'complete', now()
            self._change(project_id, task_id, platform, attempt_id, success)
        except Exception as error:
            def failed(task, run, attempt):
                run.status = attempt.status = ('cancelled' if cancel.is_set() else
                    'blocked' if type(error).__name__ == 'ExportBlocked' else 'failed')
                attempt.error, attempt.finished_at = self.redact_text(str(error)), now()
            self._change(project_id, task_id, platform, attempt_id, failed)

    def _prepare_lock(self, task_id):
        with self.lock:
            if not hasattr(self, '_prepare_locks'):
                self._prepare_locks = {}
            return self._prepare_locks.setdefault(task_id, threading.Lock())

    def continue_platform(self, project_id, task_id, platform):
        with self.lock:
            task = self.get(project_id, task_id)
            self._start(task, platform)
        return self.get(project_id, task_id)

    def cancel(self, project_id, task_id, platform):
        with self.lock:
            task = self.get(project_id, task_id)
            run = next((r for r in task.platforms if r.platform == platform), None)
            if not run:
                raise KeyError('平台不存在')
            event = self.cancel_events.get((task_id, platform))
            if run.status in ('queued', 'running') and event:
                event.set()
                run.attempts[-1].cancel_requested = True
                self._save(task)
            return task

    def artifact(self, project_id, task_id, artifact_id):
        self.get(project_id, task_id)
        with self.lock:
            row = self.db.execute('SELECT path FROM export_files WHERE id=? AND task_id=?', (artifact_id, task_id)).fetchone()
        if not row:
            raise KeyError('产物不存在')
        path = Path(row[0]).resolve(strict=True)
        if not path.is_relative_to(self.root / task_id):
            raise ValueError('产物路径不合法')
        return path

    def verify(self, project_id, task_id, platform, request):
        with self.lock:
            task = self.get(project_id, task_id)
            run = next((r for r in task.platforms if r.platform == platform), None)
            if not run or not run.attempts or run.attempts[-1].id != request.attempt_id:
                raise ValueError('验证必须对应当前执行轮次')
            if request.status != 'pending' and (run.status != 'succeeded' or not request.device.strip() or not request.notes.strip()):
                raise ValueError('请提供已生成安装包的实际设备和验证记录')
            run.verification, run.verification_notes = request.status, request.notes
            run.verification_device, run.verification_attempt_id = request.device, request.attempt_id
            self._save(task)
            return task

    def message(self, project_id, task_id, request):
        if request.execution_mode == 'native':
            return self.native_message(project_id, task_id, request)
        return self.discuss_message(project_id, task_id, request)

    def discuss_message(self, project_id, task_id, request):
        with self.lock:
            task = self.get(project_id, task_id)
            task.messages.append(ExportMessage(id=str(uuid4()), role='user', content=self.redact_text(request.content), created_at=now()))
            self._save(task)
        try:
            if self.agent_callback is None:
                raise ValueError('尚未连接 Agent 提供方，请配置后继续对话')
            result = self.agent_callback(task.model_dump(), request.content, request.provider_id, request.model)
            with self.lock:
                task = self.get(project_id, task_id)
                fields = {k: result[k] for k in ('agent_task_id', 'provider_id', 'model', 'usage', 'invocation') if k in result}
                response = ExportMessage(id=str(uuid4()), role='assistant', content=self.redact_text(result['content']), created_at=now(), **fields)
                for action in result.get('actions', []):
                    if action['action'] == 'request_development':
                        response.proposed_development = action.get('request', '')
                task.messages.append(response)
                self._save(task)
        except Exception as error:
            with self.lock:
                task = self.get(project_id, task_id)
                task.messages.append(ExportMessage(id=str(uuid4()), role='system', content=self.redact_text(str(error)), created_at=now()))
                self._save(task)
        return self.get(project_id, task_id)

    def close(self):
        for event in self.native_cancel_events.values():
            event.set()
        for event in self.cancel_events.values():
            event.set()
        for thread in self.threads:
            thread.join(timeout=5)
        # Workers may still be stopping an external process; leave their connection alive.
        if not any(thread.is_alive() for thread in self.threads):
            self.db.close()
