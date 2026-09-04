"""Bounded text-only CodeBuddy CLI adapter; host permissions are never bypassed."""
import asyncio
import json
import shutil
import tempfile
from typing import get_args
from .schemas import ChatRequest, ChatResponse, ModelCatalog, ModelId, ModelOption


def model_catalog() -> ModelCatalog:
    available = shutil.which('codebuddy') is not None
    return ModelCatalog(available=available,
        message='CLI 已安装；登录、模型权限和额度将在发送时检查。' if available else '找不到 codebuddy；请安装并在终端完成登录。',
        models=[ModelOption(id=model, mode='planned' if available else 'blocked') for model in get_args(ModelId)])


class CodeBuddyFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


async def complete(request: ChatRequest) -> ChatResponse:
    executable = shutil.which('codebuddy')
    if not executable:
        raise CodeBuddyFailure('CLI_UNAVAILABLE', '找不到 codebuddy；请安装并登录后重试。')
    with tempfile.TemporaryDirectory(prefix='sceneops-shell-chat-') as cwd:
        process = await asyncio.create_subprocess_exec(
            executable, '--print', '--output-format', 'json', '--model', request.model,
            '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--no-session-persistence', '--max-turns', '1',
            '--append-system-prompt', '你是 SceneOps 对话助手。只回复中文文本，不执行工具、文件修改或任务委派。未实际执行的操作必须明确标为 planned。',
            cwd=cwd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(process.communicate(request.prompt.encode()), timeout=120)
        except asyncio.TimeoutError as error:
            raise CodeBuddyFailure('CLI_TIMEOUT', 'CodeBuddy 120 秒内未完成。请检查登录、网络和模型额度后重试。') from error
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        if process.returncode:
            raise CodeBuddyFailure('CLI_FAILED', f'CodeBuddy 返回退出码 {process.returncode}。请在终端检查登录与所选模型权限；未绕过权限检查。')
        try:
            result = json.loads(stdout)
        except (ValueError, UnicodeError) as error:
            raise CodeBuddyFailure('CLI_INVALID_RESPONSE', 'CodeBuddy 未返回约定的 JSON 结果。') from error
        if not isinstance(result, dict) or result.get('is_error') or not isinstance(result.get('result'), str):
            raise CodeBuddyFailure('CLI_RESPONSE_FAILED', 'CodeBuddy 未完成文本回复，请在终端检查服务状态。')
        return ChatResponse(model=request.model, text=result['result'])
