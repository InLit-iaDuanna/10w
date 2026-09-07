"""Current-build browser evidence, using the existing game run and artifact stores."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

from sceneops_harness import HarnessError
from .production_models import ProductionStep
from .task_models import GameExecutionRun, now


def build_files(root):
    """Detect writes/replacements during capture; no Git-HEAD or pixel inference."""
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise HarnessError('BUILD_OUTPUT_INVALID', '构建包含链接。')
        if path.is_file():
            stat = path.stat()
            result[path.relative_to(root).as_posix()] = (
                stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return result


def target(runtime, task):
    build = runtime._current_build(task)
    active = runtime.previews.get(runtime.key(task.project_id, task.grant.card_id))
    if not active or active['process'].returncode is not None:
        raise HarnessError('CURRENT_PREVIEW_REQUIRED', '当前卡片没有运行中的已登记预览。')
    preview = active['run']
    expected = (task.project_id, task.grant.card_id, task.grant.workspace_root, task.grant.branch)
    for run in (build, preview):
        if run.task_id != task.id or (run.project_id, run.card_id, run.workspace_root, run.branch) != expected:
            raise HarnessError('BROWSER_TARGET_MISMATCH', '构建或预览不属于当前登记工作区。')
    if preview.source_stale or preview.build_run_id != build.id:
        raise HarnessError('CURRENT_PREVIEW_REQUIRED', '预览未关联当前构建，请重新启动当前构建预览。')
    url = urlsplit(preview.preview_url or '')
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or url.username or url.password:
        raise HarnessError('BROWSER_TARGET_MISMATCH', '预览地址不是应用登记的 loopback 服务。')
    return build, preview


async def capture(runtime, url, screenshot):
    node = shutil.which('node')
    if not node:
        return {'status': 'failed', 'failure_code': 'BROWSER_UNAVAILABLE', 'reason': 'Node runtime missing.'}
    worker = Path(__file__).with_name('browser_worker.mjs')
    environment = runtime._environment()
    cache = Path.home() / ('Library/Caches/ms-playwright' if sys.platform == 'darwin' else '.cache/ms-playwright')
    environment['PLAYWRIGHT_BROWSERS_PATH'] = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', str(cache))
    process = await asyncio.create_subprocess_exec(node, str(worker),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=environment, start_new_session=True)
    runtime.processes[str(screenshot)] = process
    try:
        payload = {'url': url, 'screenshot_path': str(screenshot),
            'playwright_module': os.environ.get('SCENEOPS_PLAYWRIGHT_MODULE')}
        output, error = await asyncio.wait_for(process.communicate(json.dumps(payload).encode()), timeout=30)
        if process.returncode or not output:
            return {'status': 'failed', 'failure_code': 'BROWSER_PROCESS_FAILED',
                'reason': error.decode(errors='replace')[-2000:]}
        return json.loads(output)
    except asyncio.TimeoutError:
        return {'status': 'failed', 'failure_code': 'BROWSER_TIMEOUT'}
    finally:
        cleanup = asyncio.create_task(runtime._terminate(process))
        cancelled = False
        try:
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            if cancelled:
                raise asyncio.CancelledError()
        finally:
            runtime.processes.pop(str(screenshot), None)


async def observe(service, task):
    runtime = service.game
    run = GameExecutionRun(operation='observe', project_id=task.project_id,
        card_id=task.grant.card_id, task_id=task.id,
        workspace_root=task.grant.workspace_root, branch=task.grant.branch)
    step_id = f'{task.id}:{run.id}'
    directory = runtime.data_dir / 'observations' / task.id / run.id
    service.production.upsert_step(ProductionStep(id=step_id, project_id=task.project_id,
        task_id=task.id, module_id='ai-playtest', title='观察当前构建',
        capability_id='code.browser.observe', state='running', mode='live',
        run_id=run.id, effect_state='NONE', updated_at=now().isoformat()))
    runtime._save(run)
    try:
        async with asyncio.timeout(35), runtime._lock(task.project_id, task.grant.card_id):
            service.browser_task(task.id)
            build, preview = target(runtime, task)
            run.build_run_id, run.preview_run_id, run.preview_url = build.id, preview.id, preview.preview_url
            runtime._save(run)
            output = Path(build.artifact_path)
            before = build_files(output)
            directory.mkdir(parents=True, exist_ok=False)
            screenshot = directory / 'current-view.png'
            result = await capture(runtime, preview.preview_url, screenshot)
            run.observation = result
            service.browser_task(task.id)
            current_build, current_preview = target(runtime, task)
            if (current_build.id, current_preview.id, build_files(output)) != (build.id, preview.id, before):
                raise HarnessError('BUILD_CHANGED_DURING_OBSERVATION', '检查期间构建发生变化，结果不能作为当前证据。')
            run.status = result['status']
            run.failure_code = result.get('failure_code')
            # "passed" concerns capture completion only; gameplay/visual flags stay false.
            run.passed = run.status == 'succeeded'
            if result.get('screenshot_collected'):
                artifact = service.production.record_observation_artifact(task, step_id, run.id, screenshot)
                run.artifact_ids.append(artifact.id)
                run.observation['screenshot_artifact'] = artifact.model_dump(mode='json')
    except HarnessError as error:
        run.status, run.passed, run.failure_code, run.log = 'failed', False, error.code, str(error)
        run.source_stale = error.code in ('BUILD_CHANGED_DURING_OBSERVATION', 'CURRENT_PREVIEW_REQUIRED', 'CURRENT_BUILD_REQUIRED')
    except asyncio.CancelledError:
        run.status, run.passed, run.failure_code = 'interrupted', False, 'BROWSER_CANCELLED'
    except TimeoutError:
        run.status, run.passed, run.failure_code = 'failed', False, 'BROWSER_TIMEOUT'
    except Exception as error:
        run.status, run.passed, run.failure_code, run.log = 'failed', False, 'BROWSER_PROCESS_FAILED', str(error)[:2000]
    finally:
        run.finished_at = now()
        runtime._save(run)
        service.production.upsert_step(ProductionStep(id=step_id, project_id=task.project_id,
            task_id=task.id, module_id='ai-playtest', title='观察当前构建',
            capability_id='code.browser.observe', state='completed' if run.passed else 'failed',
            mode='live', run_id=run.id, effect_state='NONE', artifact_ids=run.artifact_ids,
            reason=run.failure_code, updated_at=now().isoformat()))
    return {'tool': 'browser_observation', 'mode': 'live', 'effect_state': 'COMMITTED',
        'run': run.model_dump(mode='json'), 'gameplay_verified': False, 'visual_reviewed': False}
