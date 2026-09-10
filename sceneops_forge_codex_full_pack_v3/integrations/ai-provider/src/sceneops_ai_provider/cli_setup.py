"""Bounded local installation and interactive login; never reads credentials."""
import asyncio
import json
import platform
import re
import shlex
import shutil
import os
import signal
from pathlib import Path
from sceneops_codebuddy import cli_install_prefix, resolve_cli_executable

TOOLS = {
    'codexcli': {'label': 'Codex CLI', 'binary': 'codex', 'install_package': '@openai/codex@0.144.1',
                 'docs_url': 'https://developers.openai.com/codex/cli/', 'login_args': ['login']},
    'codebuddycli': {'label': 'CodeBuddy CLI', 'binary': 'codebuddy',
                    'install_package': '@tencent-ai/codebuddy-code@2.146.0',
                    'docs_url': 'https://www.codebuddy.cn/docs/cli/quickstart', 'login_args': []},
}


class SetupFailure(Exception):
    pass


async def run_command(arguments: list[str], timeout: float) -> None:
    process = await asyncio.create_subprocess_exec(*arguments, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
    try:
        await asyncio.wait_for(process.wait(), timeout)
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
    if process.returncode:
        raise SetupFailure('命令未完成，请检查网络和本地目录权限后重试。')


def installed_version(executable: str | None, package: str) -> str | None:
    if not executable:
        return None
    # npm metadata avoids starting either assistant or probing login credentials.
    target = Path(executable).resolve()
    for directory in target.parents:
        metadata = directory / 'package.json'
        if metadata.is_file():
            try:
                value = json.loads(metadata.read_text())
                version = value.get('version', '')
                if value.get('name') == package and re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][\w.-]+)?', version):
                    return version
            except (OSError, ValueError, TypeError):
                pass
    return None


async def codex_version(executable: str) -> str | None:
    """Probe native Codex builds without starting an assistant or reading login state."""
    try:
        process = await asyncio.create_subprocess_exec(executable, '--version',
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None
    try:
        async with asyncio.timeout(3):
            try:
                output = await process.stdout.readexactly(257)
            except asyncio.IncompleteReadError as error:
                output = error.partial
            if len(output) > 256:
                return None
            await process.wait()
        match = re.fullmatch(rb'codex-cli (\d+\.\d+\.\d+)\s*', output)
        return match.group(1).decode() if process.returncode == 0 and match else None
    except (OSError, asyncio.TimeoutError):
        return None
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


class CLISetup:
    def __init__(self):
        self.operation = {'state': 'idle', 'message': '', 'provider': None}
        self.task: asyncio.Task | None = None

    async def status(self) -> dict:
        system = platform.system().lower()
        tools = []
        for provider, spec in TOOLS.items():
            executable = resolve_cli_executable(spec['binary'])
            version = installed_version(executable, spec['install_package'].rsplit('@', 1)[0])
            if executable and provider == 'codexcli' and version is None:
                version = await codex_version(executable)
            tools.append({'compatible': bool(executable) and (provider != 'codexcli' or version == '0.144.1'),
                'provider': provider, 'label': spec['label'], 'installed': bool(executable),
                'version': version,
                'install_package': spec['install_package'], 'docs_url': spec['docs_url'],
                'login_command': shlex.join([executable or spec['binary'], *spec['login_args']])})
        return {'platform': system, 'install_supported': system in {'darwin', 'linux'},
                'terminal_supported': system == 'darwin', 'npm_available': bool(shutil.which('npm')),
                'tools': tools, 'operation': dict(self.operation)}

    async def start_install(self, providers: list[str]) -> dict:
        if not providers or len(providers) > 2 or any(value not in TOOLS for value in providers):
            raise SetupFailure('请选择受支持的 CLI。')
        if self.task is not None and not self.task.done():
            raise SetupFailure('正在安装，请等待当前安装完成。')
        if platform.system() not in {'Darwin', 'Linux'}:
            raise SetupFailure('当前系统请按官方文档手动安装 CLI。')
        npm = shutil.which('npm')
        if not npm:
            raise SetupFailure('请先从 https://nodejs.org/ 安装 Node.js LTS，然后重启工作台。')
        self.operation = {'state': 'installing', 'message': '正在准备安装…', 'provider': None}
        self.task = asyncio.create_task(self._install(list(dict.fromkeys(providers)), npm))
        return await self.status()

    async def _install(self, providers: list[str], npm: str) -> None:
        try:
            for provider in providers:
                spec = TOOLS[provider]
                before = await self.status()
                if next(tool for tool in before['tools'] if tool['provider'] == provider)['compatible']:
                    continue
                self.operation = {'state': 'installing', 'message': f"正在安装 {spec['label']}…", 'provider': provider}
                prefix = cli_install_prefix()
                prefix.mkdir(parents=True, exist_ok=True)
                await run_command([npm, 'install', '--global', '--prefix', str(prefix),
                    '--registry', 'https://registry.npmjs.org', '--no-audit', '--no-fund', spec['install_package']], 300)
                after = await self.status()
                if not next(tool for tool in after['tools'] if tool['provider'] == provider)['compatible']:
                    raise SetupFailure('安装命令已结束，但 CLI 版本未就绪，请检查安装目录后重试。')
            self.operation = {'state': 'succeeded', 'message': 'CLI 已准备好，请继续在终端登录。', 'provider': None}
        except asyncio.CancelledError:
            self.operation = {'state': 'failed', 'message': '安装已中断，请重新检查环境并重试。', 'provider': None}
            raise
        except (OSError, asyncio.TimeoutError, SetupFailure):
            self.operation = {'state': 'failed', 'message': 'CLI 安装失败或超时，请检查网络、Node.js 和目录权限后重试。',
                              'provider': self.operation['provider']}

    async def login(self, provider: str) -> dict:
        if provider not in TOOLS:
            raise SetupFailure('请选择受支持的 CLI。')
        if platform.system() != 'Darwin':
            raise SetupFailure('请在本机终端运行页面中的登录命令。')
        spec = TOOLS[provider]
        executable = resolve_cli_executable(spec['binary'])
        if not executable:
            raise SetupFailure('请先安装所选 CLI。')
        command = shlex.join([executable, *spec['login_args']])
        script = 'on run argv\ntell application "Terminal"\nactivate\ndo script (item 1 of argv)\nend tell\nend run'
        try:
            await run_command(['/usr/bin/osascript', '-e', script, command], 15)
        except (OSError, asyncio.TimeoutError, SetupFailure) as error:
            raise SetupFailure('无法打开终端，请手动复制登录命令到终端执行。') from error
        return {'message': '已打开终端，请在那里完成登录；工作台不会读取或保存你的登录凭据。'}
