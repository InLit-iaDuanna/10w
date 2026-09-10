"""Native execution bridge. The injected port owns AgentTaskService authorization/execution."""
import json
import shutil
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .export_models import ExportNativeRun, ExportMessage, ExportLog, ExportAttempt, ExportArtifact


def now():
    return datetime.now(timezone.utc).isoformat()


class NativeExportMixin:
    def native_context(self, project_id, task_id):
        task = self.get(project_id, task_id)
        workspace = self.root / task_id / 'native-workspace'
        if workspace.is_symlink() or not workspace.resolve().is_relative_to(self.root / task_id):
            raise ValueError('Agent 工作目录不能指向导出任务之外')
        workspace.mkdir(exist_ok=True)
        source = workspace / 'source'
        if source.is_symlink():
            raise ValueError('Agent 源目录不能是符号链接')
        if not source.exists():
            shutil.copytree(self.root / task_id / 'source', source)
        settings = task.settings.model_dump(exclude={'allow_dependency_install'})
        return {**task.model_dump(), 'settings': settings,
                'fixed_build_dependency_download_allowed': task.settings.allow_dependency_install,
                'platforms': [r.platform for r in task.platforms], 'platform_runs': [r.model_dump() for r in task.platforms], 'export_id': task.id, 'workspace_root': str(workspace),
                'source_path': str(source), 'history': [m.model_dump() for m in task.messages],
                'logs': {r.platform: [a.model_dump() for a in r.attempts] for r in task.platforms},
                'output_manifest_path': str(workspace / 'sceneops-export-result.json')}

    def native_message(self, project_id, task_id, request):
        if not request.accept_full_access:
            raise ValueError('电脑操作需要明确授权本次 Agent 完整访问')
        with self.lock:
            task = self.get(project_id, task_id)
            if any(r.status in ('queued', 'running') for r in task.native_runs):
                raise ValueError('Agent 正在执行，请等待完成或先取消')
            if any(r.status in ('queued', 'running') for r in task.platforms):
                raise ValueError('平台打包正在执行，请等待完成或先取消平台任务')
            native = ExportNativeRun(id=str(uuid4()), started_at=now())
            task.messages.append(ExportMessage(id=native.id, role='user', content=self.redact_text(request.content), created_at=now()))
            task.native_runs.append(native)
            self._save(task)
            cancel = threading.Event()
            self.native_cancel_events[task.id] = cancel
            worker = threading.Thread(target=self._native_execute, args=(project_id, task.id, native.id, request, cancel), daemon=True)
            self.threads.append(worker)
            worker.start()
            return task

    def cancel_native(self, project_id, task_id):
        with self.lock:
            task = self.get(project_id, task_id)
            if task.native_runs and task.native_runs[-1].status in ('queued', 'running'):
                event = self.native_cancel_events.get(task_id)
                if event:
                    event.set()
                    task.native_runs[-1].cancel_requested = True
                    self._save(task)
            return task

    def _native_execute(self, project_id, task_id, run_id, request, cancel):
        def update(action):
            with self.lock:
                task = self.get(project_id, task_id)
                native = next(r for r in task.native_runs if r.id == run_id)
                action(task, native)
                self._save(task)
        def emit(stage, message):
            update(lambda task, native: native.logs.append(ExportLog(timestamp=now(), stage=stage, message=self.redact_text(str(message)))))
        cancellation_uncertain = False
        try:
            if self.native_agent is None:
                raise ValueError('尚未连接电脑操作 Agent，请配置原生 Agent 后继续')
            context = self.native_context(project_id, task_id)
            manifest = Path(context['output_manifest_path'])
            # Each execution must produce its own manifest; packaging workspace persists.
            if manifest.exists():
                manifest.rename(manifest.with_name(f'sceneops-export-result-{run_id}.json'))
            if cancel.is_set():
                raise InterruptedError('Agent 已取消')
            agent_id = self.native_agent.prepare(context, request.content, request.provider_id, request.model)
            def linked(task, native):
                native.agent_task_id, native.status = agent_id, 'running'
                next(m for m in task.messages if m.id == run_id).agent_task_id = agent_id
            update(linked)
            result = self.native_agent.run(agent_id, emit, cancel)
            if cancel.is_set():
                cancellation_uncertain = result.get('status') not in ('cancelled', 'succeeded')
                raise InterruptedError(result.get('error') or ('Agent 停止尚未确认，请检查执行记录后继续。' if cancellation_uncertain else 'Agent 已停止'))
            status = result.get('status', 'failed')
            report = None
            if manifest.exists():
                if manifest.is_symlink() or not manifest.resolve().is_relative_to(Path(context['workspace_root']).resolve()) or manifest.stat().st_size > 1024 * 1024:
                    raise ValueError('产物报告必须是工作目录内的小型 JSON 文件')
                report = json.loads(manifest.read_text())
            def complete(task, native):
                if report is not None:
                    self._native_artifacts(task, run_id, Path(context['workspace_root']), report)
                native.status, native.finished_at = ('succeeded' if status == 'succeeded' else 'failed'), now()
                native.error = self.redact_text(str(result.get('error') or f'Agent 执行状态：{status}')) if status != 'succeeded' else None
                content = result.get('content') or native.error or 'Agent 执行完成。'
                if report is None:
                    content += '\n本轮未提交新的安装包，已有平台结果保持不变。'
                task.messages.append(ExportMessage(id=str(uuid4()), role='assistant', content=self.redact_text(content), created_at=now(), agent_task_id=agent_id))
            update(complete)
        except Exception as error:
            def failed(task, native):
                native.status = 'interrupted' if cancellation_uncertain else 'cancelled' if cancel.is_set() else 'failed'
                native.error, native.finished_at = self.redact_text(str(error)), now()
                task.messages.append(ExportMessage(id=str(uuid4()), role='system', content=native.error, created_at=now(), agent_task_id=native.agent_task_id))
            update(failed)
        finally:
            with self.lock:
                self.native_cancel_events.pop(task_id, None)

    def _native_artifacts(self, task, run_id, workspace, report):
        """Import explicit output records only; never rebuild or overwrite native work."""
        if not isinstance(report, dict) or not isinstance(report.get('artifacts', []), list) or not isinstance(report.get('platforms', []), list):
            raise ValueError('产物报告结构无效')
        platforms = {r.platform: r for r in task.platforms}
        grouped = {}
        for item in report.get('artifacts', []):
            platform = item['platform']
            if platform not in platforms:
                raise ValueError('产物平台不属于本次导出')
            relative = Path(item['path'])
            path = (workspace / relative).resolve(strict=True)
            if relative.is_absolute() or not path.is_relative_to(workspace.resolve()) or not path.is_file() or not path.stat().st_size:
                raise ValueError('Agent 产物必须是工作目录内的非空文件')
            expected = '.apk' if platform == 'android' else '.zip'
            if path.suffix.lower() != expected or not zipfile.is_zipfile(path):
                raise ValueError('Agent 产物不是有效的 APK/ZIP 文件')
            with zipfile.ZipFile(path) as archive:
                names = [entry.filename for entry in archive.infolist() if not entry.is_dir() and entry.file_size > 0]
                if platform == 'android' and 'AndroidManifest.xml' not in names:
                    raise ValueError('APK 缺少 AndroidManifest.xml')
                if platform.startswith('mac-') and not any('.app/Contents/MacOS/' in n for n in names):
                    raise ValueError('Mac ZIP 缺少应用可执行文件')
                if platform == 'win-x64' and not any(n.lower().endswith('.exe') for n in names):
                    raise ValueError('Windows ZIP 缺少可执行文件')
            grouped.setdefault(platform, []).append(path)
        reports = {item['platform']: item for item in report.get('platforms', [])}
        if set(reports) - set(platforms):
            raise ValueError('报告平台不属于本次导出')
        for platform in dict.fromkeys([*reports, *grouped]):
            run = platforms[platform]
            paths = grouped.get(platform, [])
            stated = reports.get(platform, {})
            succeeded = bool(paths) and stated.get('status', 'succeeded') == 'succeeded'
            attempt = ExportAttempt(id=str(uuid4()), number=len(run.attempts)+1, status='succeeded' if succeeded else 'failed', settings=task.settings.model_copy(deep=True), stage='native-output', started_at=now(), finished_at=now(), error=None if succeeded else self.redact_text(stated.get('message') or 'Agent 未提交此平台的有效安装包'))
            # Copy accepted outputs so later native repairs cannot overwrite old downloads.
            artifact_dir = self.root / task.id / 'native-artifacts' / run_id / platform
            artifact_dir.mkdir(parents=True, exist_ok=True)
            for index, path in enumerate(paths):
                artifact_id = str(uuid4())
                destination_dir = artifact_dir / str(index)
                destination_dir.mkdir()
                destination = destination_dir / path.name
                shutil.copyfile(path, destination)
                self.db.execute('INSERT INTO export_files VALUES (?,?,?)', (artifact_id, task.id, str(destination)))
                attempt.artifacts.append(ExportArtifact(id=artifact_id, name=path.name, size=destination.stat().st_size, download_url=f'/api/projects/{task.project_id}/exports/{task.id}/artifacts/{artifact_id}'))
            run.attempts.append(attempt)
            run.status = attempt.status
            run.verification, run.verification_notes, run.verification_device, run.verification_attempt_id = 'pending', '', '', None
