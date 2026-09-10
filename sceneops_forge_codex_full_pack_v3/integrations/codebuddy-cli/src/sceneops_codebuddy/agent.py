"""Caller-authorized native CodeBuddy session; model prose has no output schema."""
import asyncio
import json
import logging
import os
import shutil
import re
from sceneops_codebuddy.cli_paths import resolve_cli_executable
from pathlib import Path
from uuid import uuid4
from .provider import CodeBuddyFailure, MODEL_IDS, EFFORT_LEVELS, _stop, _failure_from_output


def _audit_codebuddy_agent(event: str, **fields: object) -> None:
    logging.getLogger('sceneops.ai.transport').info(
        event,
        extra={'sceneops_audit': {'event': event, 'fields': fields}},
    )


def arguments(model, effort, system_prompt: str | None = None, *, native_production=False,
              session_id=None, permission_mode="full", mcp_config=None):
    if permission_mode not in ("scoped", "full"):
        raise CodeBuddyFailure("CLI_PERMISSION_INVALID", "原生执行权限模式无效。")
    if session_id is not None and (not native_production or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_:-]{0,199}", session_id)):
        raise CodeBuddyFailure("CLI_SESSION_INVALID", "续接需要有效的原生制作会话 ID。")
    if mcp_config is not None and not native_production:
        raise CodeBuddyFailure("CLI_SCOPE_REQUIRED", "领域工具只用于原生制作。")
    if model != 'cli-default' and model not in MODEL_IDS:
        raise CodeBuddyFailure('CLI_MODEL_INVALID', '所选 CodeBuddy 模型无效。')
    if effort not in EFFORT_LEVELS:
        raise CodeBuddyFailure('CLI_EFFORT_INVALID', '所选 CodeBuddy 思考强度无效。')
    args = ['--print', '--output-format', 'stream-json', '--include-partial-messages',
        '--permission-mode', 'bypassPermissions', '--tools', 'Bash,Read,Write,Edit,Glob,Grep',
        '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
        '--settings', '{"disableAllHooks":true}', '--no-session-persistence', '--effort', effort,
        '--append-system-prompt', '你在 SceneOps 内执行已授权任务。用中文简短同步当前工作，最后说明修改、验证和未完成事项。正常输出文字，不需要 JSON。不要输出凭据。']
    if system_prompt:
        args[-1] += '\n' + system_prompt
    if permission_mode == 'scoped':
        args[args.index('bypassPermissions')] = 'acceptEdits'
    if native_production:
        args.remove('--no-session-persistence')
        # Native production is CodeBuddy's own harness. Do not replace its built-in
        # plan, skill, teammate or file/image-capable tools with a SceneOps subset.
        args[args.index('--tools') + 1] = 'default'
        if mcp_config is not None:
            args[args.index('--mcp-config') + 1] = json.dumps(mcp_config)
            if 'sceneops' in mcp_config.get('mcpServers', {}):
                # The deferred wrapper checks toolName as a command permission arg.
                # Never allow the wrapper globally: that skips target permission checks.
                args += ['--allowedTools', 'DeferExecuteTool(mcp__sceneops__*)', 'mcp__sceneops__*']
        if session_id is not None:
            args += ['--resume', session_id]
    if model != 'cli-default':
        args += ['--model', model]
    return args


def activity(event):
    kind = event.get('type')
    if kind == 'stream_event':
        body = event.get('event', {})
        delta = body.get('delta', {})
        if body.get('type') == 'content_block_delta' and delta.get('type') == 'text_delta':
            return {'type': 'text_delta', 'text': delta.get('text', '')}
        if body.get('type') == 'message_start':
            return {'type': 'message_start', 'id': body.get('message', {}).get('id')}
        if body.get('type') == 'content_block_start':
            block = body.get('content_block', {})
            if block.get('type') == 'tool_use':
                return {'type': 'tool_start', 'id': block.get('id'), 'name': block.get('name', '工具')}
    if kind == 'assistant':
        blocks = event.get('message', {}).get('content', [])
        text = ''.join(block.get('text', '') for block in blocks if block.get('type') == 'text')
        tools = [{'id': block.get('id'), 'name': block.get('name', '工具'),
                  'input': {key: value for key, value in block.get('input', {}).items()
                            if key in ('file_path', 'path', 'command', 'description', 'pattern', 'offset', 'limit')
                            and isinstance(value, (str, int))}}
                 for block in blocks if block.get('type') == 'tool_use']
        if text or tools:
            return {'type': 'message_completed', 'id': event.get('message', {}).get('id'), 'text': text, 'tools': tools}
    if kind == 'user':
        return {'type': 'tool_completed', 'results': [{'id': block.get('tool_use_id'), 'failed': block.get('is_error', False)} for block in event.get('message', {}).get('content', []) if isinstance(block, dict) and block.get('type') == 'tool_result']}
    return None


async def invoke_agent(prompt, *, workspace_root, authorized_scope, model='cli-default',
                       reasoning_effort='low', timeout: float | None = 1200, on_event=None,
                       system_prompt: str | None = None, native_production=False, session_id=None,
                       permission_mode="full", mcp_config=None):
    if not isinstance(authorized_scope, str) or not authorized_scope.strip():
        raise CodeBuddyFailure("CLI_SCOPE_REQUIRED", "原生执行缺少服务端授权范围。")
    root = Path(workspace_root)
    if not root.is_absolute() or not root.is_dir() or root.resolve() != root:
        raise CodeBuddyFailure('CLI_WORKSPACE_INVALID', '执行目录必须是已登记的绝对目录。')
    executable = resolve_cli_executable('codebuddy')
    if not executable:
        raise CodeBuddyFailure('CLI_UNAVAILABLE', '找不到 CodeBuddy CLI。')
    call_id = str(uuid4())
    cli_version = None
    if native_production:
        version_process = await asyncio.create_subprocess_exec(executable, '--version',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
        try:
            version_output, _ = await asyncio.wait_for(version_process.communicate(), 10)
            if version_process.returncode:
                raise CodeBuddyFailure('CLI_VERSION_FAILED', '无法读取 CodeBuddy CLI 版本。')
            cli_version = version_output.decode().strip()
        finally:
            await _stop(version_process)
    cli_arguments = arguments(model, reasoning_effort, system_prompt, native_production=native_production,
            session_id=session_id, permission_mode=permission_mode, mcp_config=mcp_config)
    _audit_codebuddy_agent(
        'transport.request',
        call_id=call_id,
        provider='codebuddycli',
        mode='authorized-agent',
        model=model,
        prompt=prompt,
        authorized_scope=authorized_scope,
        developer_arguments=cli_arguments,
        workspace_root=str(root),
        permission_mode=permission_mode,
        native_production=native_production,
        session_id=session_id,
    )
    process = await asyncio.create_subprocess_exec(executable, *cli_arguments,
        env={key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY') if key in os.environ},
        cwd=root, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, start_new_session=True, limit=4 * 1024 * 1024)
    result = None
    observed_session_id = None
    async def read_events():
        nonlocal result, observed_session_id
        async for line in process.stdout:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError as error:
                raise CodeBuddyFailure('CLI_PROTOCOL_ERROR', 'CodeBuddy 会话事件传输中断。') from error
            if not isinstance(event, dict):
                raise CodeBuddyFailure('CLI_PROTOCOL_ERROR', 'CodeBuddy 会话事件格式不正确。')
            identifier = event.get('session_id')
            if native_production and isinstance(identifier, str) and identifier:
                if (session_id is not None and identifier != session_id) or (observed_session_id is not None and identifier != observed_session_id):
                    raise CodeBuddyFailure('CLI_SESSION_MISMATCH', 'CodeBuddy 返回的会话与指定续接会话不一致。')
                if observed_session_id is None:
                    observed_session_id = identifier
                    if on_event:
                        await on_event({'type': 'session_started', 'session_id': identifier, 'cli_version': cli_version})
            if event.get('type') == 'result':
                result = event
            update = activity(event)
            if update is not None and on_event:
                await on_event(update)
    async def read_stderr():
        tail = b''
        while chunk := await process.stderr.read(8192):
            tail = (tail + chunk)[-8192:]
        return tail
    async def write():
        process.stdin.write((f'本次授权范围：\n{authorized_scope}\n\n用户任务：\n{prompt}').encode())
        await process.stdin.drain()
        process.stdin.close()
    jobs = [asyncio.create_task(read_events()), asyncio.create_task(read_stderr()), asyncio.create_task(write())]
    try:
        _, stderr, _ = await asyncio.wait_for(asyncio.gather(*jobs), timeout)
        await process.wait()
        if process.returncode or (result and (result.get('is_error') or result.get('subtype') not in (None, 'success'))):
            raise _failure_from_output(json.dumps(result or {}).encode(), stderr, process.returncode)
        if result is None:
            raise CodeBuddyFailure('CLI_INTERRUPTED', 'CodeBuddy 会话未正常结束；已收到的内容已保留。')
        if native_production and observed_session_id is None:
            raise CodeBuddyFailure('CLI_SESSION_MISSING', 'CodeBuddy 未返回持久会话 ID；结果待核查，不自动重放。')
        output = {'result': result.get('result', ''), 'usage': result.get('usage'),
                  **({'session_id': observed_session_id, 'cli_version': cli_version} if native_production else {})}
        _audit_codebuddy_agent('transport.response', call_id=call_id, provider='codebuddycli',
                               model=model, response=output.get('result'), usage=output.get('usage'))
        return output
    except asyncio.TimeoutError as error:
        raise CodeBuddyFailure('CLI_TIMEOUT', '本次 Agent 执行已到时间上限；已完成的修改和回复已保留。') from error
    finally:
        await _stop(process)
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
