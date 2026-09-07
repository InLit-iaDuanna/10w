"""Fixed game-project checks, builds and owned localhost previews."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import sys

from sceneops_harness import HarnessError
from .task_models import GameBuildCandidate, GameExecutionRun, GameProjectExecution, now

MAX_LOG_BYTES = 262144
VITE_CONFIG = """export default {
  root: process.cwd(),
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
}
"""


class GameProjectRuntime:
    def __init__(self, records, data_dir, *, pnpm_executable=None):
        self.records = records
        self.data_dir = Path(data_dir).resolve() / 'game-runtime'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vite_config = self.data_dir / 'vite.config.mjs'
        if self.vite_config.exists() or self.vite_config.is_symlink():
            self._validate_vite_config()
        else:
            descriptor = os.open(self.vite_config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(VITE_CONFIG)
        self.pnpm_executable = pnpm_executable or shutil.which('pnpm')
        self.processes = {}
        self.previews = {}
        self.locks = {}
        with self.records.connect() as connection:
            self._migrate_run_table(connection)
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS game_build_candidates (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, task_id TEXT NOT NULL, build_run_id TEXT NOT NULL,
                    body TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(project_id, workspace_id, sequence));
                CREATE INDEX IF NOT EXISTS game_build_candidates_scope
                    ON game_build_candidates(project_id, workspace_id, sequence);
                CREATE TABLE IF NOT EXISTS game_workspace_playables (
                    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    latest_sequence INTEGER NOT NULL, current_candidate_id TEXT,
                    PRIMARY KEY(project_id, workspace_id));
            ''')
            rows = connection.execute("SELECT id,body FROM game_project_runs").fetchall()
            for run_id, body in rows:
                run = GameExecutionRun.model_validate_json(body)
                if run.status == 'running':
                    run.status, run.failure_code, run.finished_at = 'interrupted', 'SERVICE_RESTARTED', now()
                    connection.execute('UPDATE game_project_runs SET body=?,updated_at=? WHERE id=?',
                        (run.model_dump_json(), now().isoformat(), run_id))

    @staticmethod
    def _migrate_run_table(connection):
        columns = connection.execute('PRAGMA table_info(game_project_runs)').fetchall()
        if not columns:
            connection.execute('''CREATE TABLE game_project_runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                card_id TEXT, task_id TEXT NOT NULL, workspace_root TEXT NOT NULL, branch TEXT,
                operation TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            return
        by_name = {column[1]: column for column in columns}
        if ('workspace_id' in by_name and not by_name['card_id'][3]
                and not by_name['branch'][3]):
            return
        connection.execute('ALTER TABLE game_project_runs RENAME TO game_project_runs_legacy')
        connection.execute('''CREATE TABLE game_project_runs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            card_id TEXT, task_id TEXT NOT NULL, workspace_root TEXT NOT NULL, branch TEXT,
            operation TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        for row in connection.execute('''SELECT id,project_id,card_id,task_id,workspace_root,branch,
                                                operation,body,updated_at
                                         FROM game_project_runs_legacy ORDER BY rowid'''):
            run = GameExecutionRun.model_validate_json(row[7])
            connection.execute('''INSERT INTO game_project_runs
                (id,project_id,workspace_id,card_id,task_id,workspace_root,branch,operation,body,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (run.id, run.project_id, run.workspace_id, run.card_id, run.task_id,
                 run.workspace_root, run.branch, run.operation, run.model_dump_json(), row[8]))
        connection.execute('DROP TABLE game_project_runs_legacy')

    @staticmethod
    def workspace_id(task):
        grant = task.grant
        workspace_id = getattr(grant, 'workspace_id', None) or grant.card_id
        if not workspace_id:
            raise HarnessError('GAME_WORKSPACE_ID_REQUIRED', '游戏工程缺少已登记的工作区身份。')
        return workspace_id

    @staticmethod
    def key(project_id, workspace_id):
        return project_id, workspace_id

    def _lock(self, project_id, workspace_id):
        return self.locks.setdefault(self.key(project_id, workspace_id), asyncio.Lock())

    def _validate_vite_config(self):
        if (self.vite_config.is_symlink() or not self.vite_config.is_file()
                or self.vite_config.stat().st_nlink != 1 or self.vite_config.read_text('utf-8') != VITE_CONFIG):
            raise HarnessError('GAME_RUNTIME_CONFIG_INVALID', '应用自有 Vite 配置已改变，拒绝运行项目配置。')

    def _save(self, run):
        with self.records.connect() as connection:
            connection.execute('''INSERT INTO game_project_runs
                (id,project_id,workspace_id,card_id,task_id,workspace_root,branch,operation,body,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at''',
                (run.id, run.project_id, run.workspace_id, run.card_id, run.task_id,
                 run.workspace_root, run.branch, run.operation, run.model_dump_json(), now().isoformat()))
        return run

    def _latest(self, project_id, workspace_id, operation, *, task_id=None):
        with self.records.connect() as connection:
            row = connection.execute('''SELECT body FROM game_project_runs
                WHERE project_id=? AND workspace_id=? AND operation=? AND (? IS NULL OR task_id=?)
                ORDER BY rowid DESC LIMIT 1''',
                (project_id, workspace_id, operation, task_id, task_id)).fetchone()
        return GameExecutionRun.model_validate_json(row[0]) if row else None

    def _run_by_id(self, project_id, workspace_id, run_id):
        with self.records.connect() as connection:
            row = connection.execute('''SELECT body FROM game_project_runs
                WHERE id=? AND project_id=? AND workspace_id=?''',
                (run_id, project_id, workspace_id)).fetchone()
        return GameExecutionRun.model_validate_json(row[0]) if row else None

    def _begin_candidate(self, run):
        with self.records.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('''SELECT latest_sequence,current_candidate_id
                FROM game_workspace_playables WHERE project_id=? AND workspace_id=?''',
                (run.project_id, run.workspace_id)).fetchone()
            sequence = (row[0] if row else 0) + 1
            task = self.records.get(run.task_id)
            materialization = task.observations.get('demo_materialization', {})
            writes = [action for action in task.actions
                if action.action.capability_id == 'code.file.write'
                and action.state == 'succeeded' and action.effect_state == 'COMMITTED']
            content_actions = [action for action in task.actions
                if action.action.capability_id in {
                    'project.asset.door.create', 'project.asset.door.update',
                    'environment.object.place', 'environment.demo_object.transform',
                    'environment.key_door.configure', 'environment.object.remove'}
                and action.state == 'succeeded' and action.effect_state == 'COMMITTED']
            source_version = {**materialization.get('source_version', {}),
                'code_write_requests': [action.request_id for action in writes],
                'code_paths': sorted({action.action.inputs['path'] for action in writes}),
                'content_action_ids': [action.action.action_id for action in content_actions],
                'goal_request_id': ((task.observations.get('demo_goals') or [{}])[-1].get('request_id')
                                    if isinstance(task.observations.get('demo_goals'), list) else None)}
            candidate = GameBuildCandidate(project_id=run.project_id, workspace_id=run.workspace_id,
                task_id=run.task_id, sequence=sequence, build_run_id=run.id,
                source_version=source_version,
                scene_id=materialization.get('scene_id'), scene_version=materialization.get('scene_version'),
                asset_versions=materialization.get('asset_versions', []))
            connection.execute('''INSERT INTO game_build_candidates
                (id,project_id,workspace_id,sequence,task_id,build_run_id,body,updated_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (candidate.id, candidate.project_id, candidate.workspace_id, candidate.sequence,
                 candidate.task_id, candidate.build_run_id, candidate.model_dump_json(),
                 candidate.updated_at.isoformat()))
            connection.execute('''INSERT INTO game_workspace_playables
                (project_id,workspace_id,latest_sequence,current_candidate_id) VALUES(?,?,?,?)
                ON CONFLICT(project_id,workspace_id) DO UPDATE SET latest_sequence=excluded.latest_sequence''',
                (run.project_id, run.workspace_id, sequence, row[1] if row else None))
        run.candidate_id, run.candidate_sequence = candidate.id, sequence
        return candidate

    def _finish_candidate(self, run, candidate):
        with self.records.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('''SELECT latest_sequence,current_candidate_id
                FROM game_workspace_playables WHERE project_id=? AND workspace_id=?''',
                (candidate.project_id, candidate.workspace_id)).fetchone()
            current = row[0] == candidate.sequence
            if run.status == 'succeeded' and run.passed and run.artifact_path:
                status = 'succeeded' if current else 'superseded'
                if current:
                    connection.execute('''UPDATE game_workspace_playables SET current_candidate_id=?
                        WHERE project_id=? AND workspace_id=? AND latest_sequence=?''',
                        (candidate.id, candidate.project_id, candidate.workspace_id, candidate.sequence))
            else:
                status = 'failed'
            candidate = candidate.model_copy(update={'status': status,
                'artifact_path': run.artifact_path, 'failure_code': run.failure_code, 'updated_at': now()})
            connection.execute('''UPDATE game_build_candidates SET body=?,updated_at=?
                WHERE id=? AND project_id=? AND workspace_id=?''',
                (candidate.model_dump_json(), candidate.updated_at.isoformat(), candidate.id,
                 candidate.project_id, candidate.workspace_id))
        return candidate

    def _candidate_snapshot(self, project_id, workspace_id):
        with self.records.connect() as connection:
            rows = connection.execute('''SELECT body FROM game_build_candidates
                WHERE project_id=? AND workspace_id=? ORDER BY sequence''',
                (project_id, workspace_id)).fetchall()
            state = connection.execute('''SELECT current_candidate_id FROM game_workspace_playables
                WHERE project_id=? AND workspace_id=?''', (project_id, workspace_id)).fetchone()
        candidates = [GameBuildCandidate.model_validate_json(row[0]) for row in rows]
        latest = candidates[-1] if candidates else None
        current_id = state[0] if state else None
        current = next((item for item in candidates if item.id == current_id), None)
        if latest is None:
            update_state = 'idle'
        elif latest.status == 'building':
            update_state = 'building'
        elif latest.status == 'failed':
            update_state = 'failed'
        else:
            update_state = 'updated'
        return candidates, latest, current, update_state

    @staticmethod
    def _validate_root(root):
        root = Path(root)
        package = root / 'package.json'
        if (not root.is_absolute() or root.resolve() != root or not root.is_dir()
                or package.is_symlink() or not package.is_file() or package.stat().st_size > 65536):
            raise HarnessError('GAME_PROJECT_INVALID', '卡片工作区缺少可执行的普通 package.json。')
        try:
            body = json.loads(package.read_text('utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise HarnessError('GAME_PROJECT_INVALID', 'package.json 不是有效的 UTF-8 JSON。') from error
        if not isinstance(body.get('dependencies'), dict) or not isinstance(body.get('devDependencies'), dict):
            raise HarnessError('GAME_PROJECT_INVALID', '游戏工程依赖声明不完整。')
        return root

    def dependencies_ready(self, root):
        root = Path(root)
        return all((root / relative).exists() for relative in ('node_modules/.bin/tsc', 'node_modules/.bin/vite'))

    @staticmethod
    def _validate_output(root, *, required):
        output = Path(root) / 'dist'
        if output.is_symlink() or (output.exists() and (not output.is_dir() or output.resolve() != output)):
            raise HarnessError('BUILD_OUTPUT_INVALID', '构建目录不是当前卡片内的普通目录。')
        if not output.exists():
            if required:
                raise HarnessError('CURRENT_BUILD_REQUIRED', '当前构建产物不存在，请重新构建。')
            return output
        for parent, directories, files in os.walk(output, followlinks=False):
            if any((Path(parent) / name).is_symlink() for name in (*directories, *files)):
                raise HarnessError('BUILD_OUTPUT_INVALID', '构建产物包含链接，不能作为应用预览。')
        index = output / 'index.html'
        if required and (index.is_symlink() or not index.is_file()):
            raise HarnessError('CURRENT_BUILD_REQUIRED', '当前构建缺少普通 index.html。')
        return output

    def _environment(self):
        paths = [value for value in os.environ.get('PATH', '').split(os.pathsep)
                 if value and Path(value).is_absolute() and Path(value).is_dir()]
        home = self.data_dir / 'home'
        cache = self.data_dir / 'cache'
        temporary = self.data_dir / 'tmp'
        for directory in (home, cache, temporary):
            directory.mkdir(parents=True, exist_ok=True)
        return {
            'PATH': os.pathsep.join(paths), 'HOME': str(home), 'XDG_CACHE_HOME': str(cache),
            'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_DATA_HOME': str(home / '.local/share'),
            'TMPDIR': str(temporary), 'CI': '1', 'NO_COLOR': '1',
            'npm_config_userconfig': os.devnull, 'npm_config_ignore_scripts': 'true',
            'LANG': os.environ.get('LANG', 'C.UTF-8'),
        }

    @staticmethod
    def _append_log(run, content):
        encoded = (run.log + content).encode('utf-8', errors='replace')
        if len(encoded) > MAX_LOG_BYTES:
            encoded = b'[earlier output truncated]\n' + encoded[-(MAX_LOG_BYTES - 28):]
        run.log = encoded.decode('utf-8', errors='replace')

    async def _command(self, run, args, *, timeout=300):
        try:
            process = await asyncio.create_subprocess_exec(*args, cwd=run.workspace_root,
                env=self._environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                start_new_session=True)
        except (FileNotFoundError, PermissionError, OSError) as error:
            self._append_log(run, f'{type(error).__name__}: {error}\n')
            return None
        self.processes[run.id] = process
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
            self._append_log(run, output.decode('utf-8', errors='replace'))
            return process.returncode
        except asyncio.TimeoutError:
            run.failure_code = 'COMMAND_TIMEOUT'
            await self._terminate(process)
            return None
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        finally:
            self.processes.pop(run.id, None)

    @staticmethod
    async def _terminate(process):
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def execute(self, task, operation):
        grant = task.grant
        workspace_id = self.workspace_id(task)
        root = self._validate_root(grant.workspace_root)
        async with self._lock(task.project_id, workspace_id):
            if operation == 'preview_start':
                try:
                    run = await self._start_preview(task, root)
                except HarnessError as error:
                    run = GameExecutionRun(operation=operation, project_id=task.project_id,
                        workspace_id=workspace_id, card_id=grant.card_id, task_id=task.id,
                        workspace_root=str(root), branch=grant.branch,
                        status='failed', passed=False, failure_code=error.code, finished_at=now(), log=str(error) + '\n')
                    self._save(run)
            elif operation == 'preview_stop':
                run = await self._stop_preview(task, root)
            else:
                run = GameExecutionRun(operation=operation, project_id=task.project_id,
                    workspace_id=workspace_id, card_id=grant.card_id, task_id=task.id,
                    workspace_root=str(root), branch=grant.branch,
                    build_kind='test' if operation == 'build_test' else 'delivery')
                candidate = self._begin_candidate(run) if operation == 'build' else None
                self._save(run)
                try:
                    if operation == 'prepare':
                        if not self.pnpm_executable:
                            run.failure_code = 'PNPM_NOT_AVAILABLE'
                            self._append_log(run, 'pnpm is not available in the application environment.\n')
                            code = None
                        else:
                            args = [self.pnpm_executable, 'install', '--ignore-scripts',
                                    '--ignore-workspace', '--no-lockfile']
                            if (root / 'pnpm-lock.yaml').is_file():
                                args.append('--frozen-lockfile')
                            code = await self._command(run, args, timeout=600)
                        passed = code == 0 and self.dependencies_ready(root)
                    else:
                        if not self.dependencies_ready(root):
                            run.failure_code = 'DEPENDENCIES_NOT_READY'
                            self._append_log(run, 'Project dependencies are not prepared.\n')
                            code, passed = None, False
                        elif not self.pnpm_executable:
                            run.failure_code = 'PNPM_NOT_AVAILABLE'
                            self._append_log(run, 'pnpm is not available in the application environment.\n')
                            code, passed = None, False
                        elif operation == 'check':
                            code = await self._command(run, [self.pnpm_executable, 'exec', 'tsc', '--noEmit'])
                            passed = code == 0
                        elif operation in ('build', 'build_test'):
                            self._validate_vite_config()
                            self._validate_output(root, required=False)
                            check_code = await self._command(run, [self.pnpm_executable, 'exec', 'tsc', '--noEmit'])
                            code = check_code
                            if check_code == 0:
                                code = await self._command(run, [self.pnpm_executable, 'exec', 'vite', 'build',
                                    '--config', str(self.vite_config), '--mode',
                                    'sceneops-test' if operation == 'build_test' else 'production'])
                            output = self._validate_output(root, required=code == 0)
                            passed = code == 0
                            if passed:
                                from .browser_observation import build_files
                                before = build_files(output)
                                retained = self.data_dir / 'builds' / run.id / 'dist'
                                retained.parent.mkdir(parents=True, exist_ok=False)
                                shutil.copytree(output, retained, symlinks=True)
                                self._validate_output(retained.parent, required=True)
                                if before != build_files(output):
                                    raise HarnessError('BUILD_OUTPUT_CHANGED', '构建输出在登记期间改变，请重新构建。')
                                run.artifact_path = str(retained)
                        else:
                            raise HarnessError('GAME_OPERATION_INVALID', '未知的工程操作。')
                except HarnessError as error:
                    code, passed, run.failure_code = None, False, error.code
                    self._append_log(run, str(error) + '\n')
                except asyncio.CancelledError:
                    run.status, run.passed, run.failure_code, run.finished_at = (
                        'interrupted', False, 'COMMAND_CANCELLED', now())
                    self._save(run)
                    if candidate is not None:
                        self._finish_candidate(run, candidate)
                    raise
                run.exit_code, run.passed, run.finished_at = code, passed, now()
                run.status = 'succeeded' if passed else 'failed'
                if not passed and run.failure_code is None:
                    run.failure_code = 'COMMAND_FAILED' if code is not None else 'COMMAND_NOT_STARTED'
                self._save(run)
                if candidate is not None:
                    self._finish_candidate(run, candidate)
            return self.evidence(task, run)

    def _current_build(self, task, *, kind='delivery'):
        workspace_id = self.workspace_id(task)
        if kind == 'delivery':
            _, _, current, _ = self._candidate_snapshot(task.project_id, workspace_id)
            run = (self._run_by_id(task.project_id, workspace_id, current.build_run_id)
                   if current is not None else None)
        else:
            run = self._latest(task.project_id, workspace_id, 'build_test')
        if (not run or run.status != 'succeeded' or not run.passed
                or (kind == 'test' and run.source_stale)):
            raise HarnessError('TEST_BUILD_REQUIRED' if kind == 'test' else 'CURRENT_BUILD_REQUIRED',
                '请先让当前源码通过对应类型的构建，再启动预览。')
        if run.build_kind != kind:
            raise HarnessError('BUILD_KIND_MISMATCH', '构建类型与检查范围不一致。')
        expected = self.data_dir / 'builds' / run.id / 'dist'
        if run.artifact_path != str(expected):
            raise HarnessError('CURRENT_BUILD_REQUIRED', '旧构建没有独立输出版本，请重新构建。')
        self._validate_output(expected.parent, required=True)
        return run

    async def _start_preview(self, task, root, *, kind='delivery', key=None):
        build = self._current_build(task, kind=kind)
        self._validate_output(root, required=True)
        workspace_id = self.workspace_id(task)
        key = key or self.key(task.project_id, workspace_id)
        active = self.previews.get(key)
        if (active and active['process'].returncode is None and not active['run'].source_stale
                and active['run'].build_run_id == build.id):
            return active['run']
        if active:
            await self._stop_active(key, status='stopped')
        run = GameExecutionRun(operation='preview_test' if kind == 'test' else 'preview_start', project_id=task.project_id,
            workspace_id=workspace_id, card_id=task.grant.card_id, task_id=task.id,
            workspace_root=str(root), branch=task.grant.branch,
            build_run_id=build.id, build_kind=kind)
        self._save(run)
        script = Path(__file__).with_name('preview_server.py').resolve()
        try:
            process = await asyncio.create_subprocess_exec(sys.executable, '-I', str(script), '--directory', build.artifact_path,
                cwd=str(root), env=self._environment(), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        except (OSError, PermissionError) as error:
            run.status, run.passed, run.failure_code, run.finished_at = 'failed', False, 'PREVIEW_START_FAILED', now()
            self._append_log(run, f'{type(error).__name__}: {error}\n')
            return self._save(run)
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            ready = json.loads(line.decode('utf-8'))
            if ready.get('host') != '127.0.0.1' or not isinstance(ready.get('port'), int):
                raise ValueError('invalid preview handshake')
        except (asyncio.TimeoutError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            await self._terminate(process)
            run.status, run.passed, run.failure_code, run.finished_at = 'failed', False, 'PREVIEW_START_FAILED', now()
            self._append_log(run, f'{error}\n')
            return self._save(run)
        except asyncio.CancelledError:
            await self._terminate(process)
            run.status, run.passed, run.failure_code, run.finished_at = (
                'interrupted', False, 'PREVIEW_START_CANCELLED', now())
            self._save(run)
            raise
        run.preview_url = f"http://127.0.0.1:{ready['port']}/"
        run.status, run.passed = 'running', True
        self._append_log(run, line.decode('utf-8', errors='replace'))
        reader = asyncio.create_task(self._read_preview(run, process))
        self.previews[key] = {'process': process, 'run': run, 'reader': reader}
        return self._save(run)

    async def _read_preview(self, run, process):
        while line := await process.stdout.readline():
            self._append_log(run, line.decode('utf-8', errors='replace'))
            self._save(run)

    async def _stop_active(self, key, *, status):
        active = self.previews.get(key)
        if not active:
            return None
        process, run = active['process'], active['run']
        cancelled = False
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            await self._terminate(process)
        except asyncio.CancelledError:
            cancelled = True
            await self._terminate(process)
        await asyncio.gather(active['reader'], return_exceptions=True)
        if self.previews.get(key) is active:
            self.previews.pop(key, None)
        run.status, run.finished_at = ('interrupted' if cancelled else status), now()
        run.exit_code = process.returncode
        self._save(run)
        if cancelled:
            raise asyncio.CancelledError()
        return run

    async def _stop_preview(self, task, root):
        workspace_id = self.workspace_id(task)
        key = self.key(task.project_id, workspace_id)
        stopped = await self._stop_active(key, status='stopped')
        run = GameExecutionRun(operation='preview_stop', project_id=task.project_id,
            workspace_id=workspace_id, card_id=task.grant.card_id, task_id=task.id,
            workspace_root=str(root), branch=task.grant.branch,
            status='succeeded', passed=True, finished_at=now(), log='Owned preview stopped.\n' if stopped else 'No owned preview was running.\n')
        return self._save(run)

    async def stop_task_preview(self, task):
        key = self.key(task.project_id, self.workspace_id(task))
        async with self._lock(*key):
            return await self._stop_active(key, status='stopped')

    def snapshot(self, task):
        grant = task.grant
        workspace_id = self.workspace_id(task)
        root = self._validate_root(grant.workspace_root)
        key = self.key(task.project_id, workspace_id)
        active = self.previews.get(key)
        if active and active['process'].returncode is not None:
            run = active['run']
            run.status, run.passed, run.finished_at = 'interrupted', False, now()
            run.exit_code = active['process'].returncode
            self._save(run)
            self.previews.pop(key, None)
        candidates, latest_candidate, current_candidate, update_state = self._candidate_snapshot(
            task.project_id, workspace_id)
        if task.authorization_card.task_profile in ('project-demo', 'project-demo-agent'):
            update = task.observations.get('demo_update', {})
            if task.status in ('queued', 'running'):
                update_state = 'building'
            elif isinstance(update, dict) and update.get('status') == 'failed':
                update_state = 'failed'
        return GameProjectExecution(project_id=task.project_id, workspace_id=workspace_id,
            card_id=grant.card_id,
            workspace_root=str(root), branch=grant.branch, dependencies_ready=self.dependencies_ready(root),
            dependency=self._latest(task.project_id, workspace_id, 'prepare'),
            check=self._latest(task.project_id, workspace_id, 'check'),
            build=self._latest(task.project_id, workspace_id, 'build'),
            test_build=self._latest(task.project_id, workspace_id, 'build_test', task_id=task.id),
            interaction=self._latest(task.project_id, workspace_id, 'interact', task_id=task.id),
            observation=self._latest(task.project_id, workspace_id, 'observe'),
            preview=(active['run'] if active and active['process'].returncode is None
                     else self._latest(task.project_id, workspace_id, 'preview_start')),
            build_candidates=candidates, latest_candidate=latest_candidate,
            current_playable_candidate=current_candidate, update_state=update_state)

    def evidence(self, task, run):
        snapshot = self.snapshot(task)
        return {'tool': 'game_project', 'mode': 'live', 'effect_state': 'COMMITTED',
            'operation': run.operation, 'run': run.model_dump(mode='json'),
            'project': snapshot.model_dump(mode='json')}

    def invalidate_workspace(self, workspace_root):
        with self.records.connect() as connection:
            rows = connection.execute('SELECT id,body FROM game_project_runs WHERE workspace_root=?',
                                      (str(workspace_root),)).fetchall()
            for run_id, body in rows:
                run = GameExecutionRun.model_validate_json(body)
                if run.operation in ('check', 'build', 'build_test', 'observe', 'interact') and run.status == 'succeeded':
                    run.status, run.source_stale = 'stale', True
                elif run.operation in ('preview_start', 'preview_test') and run.status == 'running':
                    run.source_stale = True
                else:
                    continue
                connection.execute('UPDATE game_project_runs SET body=?,updated_at=? WHERE id=?',
                    (run.model_dump_json(), now().isoformat(), run_id))
        for active in self.previews.values():
            if active['run'].workspace_root == str(workspace_root):
                active['run'].source_stale = True
                self._save(active['run'])

    def has_active_previews(self):
        return any(active['process'].returncode is None for active in self.previews.values())

    async def close(self):
        await asyncio.gather(*(self._terminate(process) for process in list(self.processes.values())),
                             return_exceptions=True)
        for key in list(self.previews):
            await self._stop_active(key, status='stopped')
