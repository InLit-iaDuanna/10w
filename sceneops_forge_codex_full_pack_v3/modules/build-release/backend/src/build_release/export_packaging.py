"""Local, cancellable Web/Capacitor/Electron packaging with fixed tool commands."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform as host_platform
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

from .export_templates import (BUILDER_VERSION, CAPACITOR_VERSION, ELECTRON_MAIN,
                               ELECTRON_VERSION, VITE_CONFIG, VITE_VERSION,
                               capacitor_config, desktop_package)


class ExportBuildError(RuntimeError):
    pass


class ExportBlocked(ExportBuildError):
    pass


class ExportCancelled(ExportBuildError):
    pass


class LocalExportAdapter:
    """No automatic retry: the owning task records a new explicitly requested attempt."""

    def __init__(self, *, timeout=1800):
        self.timeout = timeout

    def capabilities(self):
        sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        return {'mode': 'live', 'node': shutil.which('node'), 'npm': shutil.which('npm'),
                'host': host_platform.system(), 'android_sdk': sdk if sdk and Path(sdk).is_dir() else None,
                'java': shutil.which('java'), 'platforms': ['android', 'mac-arm64', 'mac-x64', 'win-x64'],
                'versions': {'vite': VITE_VERSION, 'electron': ELECTRON_VERSION,
                             'electron-builder': BUILDER_VERSION, 'capacitor': CAPACITOR_VERSION}}

    def _environment(self):
        # Build children never inherit provider credentials or npm/Gradle injection options.
        allowed = ('PATH', 'HOME', 'USERPROFILE', 'TMPDIR', 'TEMP', 'TMP', 'SystemRoot',
                   'LANG', 'LC_ALL', 'JAVA_HOME', 'ANDROID_HOME', 'ANDROID_SDK_ROOT')
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update({'CI': '1', 'CSC_IDENTITY_AUTO_DISCOVERY': 'false',
                    'NPM_CONFIG_USERCONFIG': os.devnull})
        return env

    def _run(self, args, cwd, emit, cancel_event, stage):
        if cancel_event.is_set():
            raise ExportCancelled('导出已取消。')
        emit(stage, '开始执行 ' + stage)
        environment = self._environment()
        global_config = Path(cwd) / '.sceneops-npm-global'
        global_config.write_text('', 'utf-8')
        environment['NPM_CONFIG_GLOBALCONFIG'] = str(global_config.resolve())
        environment['GRADLE_USER_HOME'] = str(Path(cwd).resolve() / '.sceneops-gradle')
        process = subprocess.Popen(args, cwd=cwd, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=os.name != 'nt')
        lines = queue.Queue()
        def read():
            while chunk := process.stdout.read1(4096):
                lines.put(chunk.decode('utf-8', errors='replace'))
            lines.put(None)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        deadline, logged = time.monotonic() + self.timeout, 0
        try:
            done = False
            while not done or process.poll() is None:
                if cancel_event.is_set():
                    raise ExportCancelled('导出已取消。')
                if time.monotonic() > deadline:
                    raise ExportBuildError(f'{stage} 超时，请检查网络和构建工具后继续。')
                try:
                    chunk = lines.get(timeout=.15)
                    if chunk is None:
                        done = True
                    elif logged < 262144:
                        emit(stage, chunk[:262144 - logged])
                        logged += len(chunk)
                except queue.Empty:
                    pass
            if process.wait() != 0:
                raise ExportBuildError(f'{stage} 失败，退出码 {process.returncode}；请查看构建日志。')
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name != 'nt':
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            process.stdout.close()

    def _tools(self):
        node, npm = shutil.which('node'), shutil.which('npm')
        if not node or not npm:
            raise ExportBlocked('缺少 Node.js/npm。请安装 Node.js 22.12 或更高版本并重启服务后继续。')
        return node, npm

    @staticmethod
    def _dependency_authorization(settings):
        if not settings.get('allow_dependency_install', False):
            raise ExportBlocked('打包需要下载 npm 构建依赖，请启用允许下载构建依赖后继续；不会安装系统工具。')

    def _install(self, root, emit, cancel):
        _, npm = self._tools()
        self._run([npm, 'install', '--ignore-scripts', '--no-audit', '--no-fund',
                   '--registry=https://registry.npmjs.org'], root, emit, cancel, 'dependencies')

    def prepare(self, source_dir, work_dir, settings, emit, cancel_event):
        self._dependency_authorization(settings)
        source_dir, work_dir = Path(source_dir).resolve(), Path(work_dir).resolve()
        node, _ = self._tools()
        if work_dir == source_dir or work_dir.is_relative_to(source_dir):
            raise ExportBuildError('导出工作目录必须独立于源项目。')
        root = work_dir / 'web'
        self._copy_source(source_dir, root, cancel_event)
        package_path = root / 'package.json'
        if not package_path.is_file() or not (root / 'index.html').is_file():
            raise ExportBlocked('当前源项目缺少 package.json 或 index.html，需要先生成可构建的 Web 游戏。')
        package = json.loads(package_path.read_text('utf-8'))
        dependencies = package.get('dependencies', {})
        # Packages may contain data/code, but local, Git, URL dependencies and install hooks are disallowed.
        for name, version in dependencies.items():
            if not re.fullmatch(r'(@[a-z0-9._-]+/)?[a-z0-9._-]+', name) or not isinstance(version, str) or not re.fullmatch(r'[0-9v~^*xX.<>=| +\-]+', version):
                raise ExportBlocked(f'依赖 {name} 不是 npm 版本声明，请先在开发流程中调整。')
        package_path.write_text(json.dumps({'name': 'sceneops-web-export', 'version': '1.0.0',
            'private': True, 'type': 'module', 'dependencies': dependencies,
            'devDependencies': {'vite': VITE_VERSION}}), 'utf-8')
        (root / 'sceneops-export.config.mjs').write_text(VITE_CONFIG, 'utf-8')
        self._install(root, emit, cancel_event)
        self._run([node, str(root / 'node_modules/vite/bin/vite.js'), 'build', '--config',
                   str(root / 'sceneops-export.config.mjs')], root, emit, cancel_event, 'web-build')
        dist = root / 'dist'
        if not (dist / 'index.html').is_file():
            raise ExportBuildError('Web 构建没有生成 index.html。')
        return dist

    def _copy_source(self, source, target, cancel):
        excluded = {'.git', 'node_modules', 'dist', '.gradle', '.sceneops', '.npmrc',
                    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock'}
        target.mkdir(parents=True, exist_ok=False)
        for entry in source.iterdir():
            if cancel.is_set():
                raise ExportCancelled('导出已取消。')
            if entry.name in excluded or entry.name.startswith('.env'):
                continue
            if entry.is_symlink():
                raise ExportBlocked('源项目含符号链接，请在开发流程中将所需资源放入项目目录。')
            if entry.is_dir():
                self._copy_source(entry, target / entry.name, cancel)
            elif entry.is_file():
                shutil.copy2(entry, target / entry.name)

    def build(self, platform, web_dir, work_dir, settings, emit, cancel_event):
        self._dependency_authorization(settings)
        if platform not in ('android', 'mac-arm64', 'mac-x64', 'win-x64'):
            raise ExportBuildError('不支持的导出平台。')
        node, _ = self._tools()
        name = settings.get('app_name') or settings.get('application_name') or 'Game'
        app_id = settings.get('app_id') or settings.get('application_id') or 'com.sceneops.game'
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+', app_id):
            raise ExportBuildError('应用标识须使用反向域名格式，例如 com.example.game。')
        if not name.strip() or any(char in name for char in '/\\\0') or name in ('.', '..'):
            raise ExportBuildError('应用名称不可包含路径分隔符。')
        if platform.startswith('mac-') and host_platform.system() != 'Darwin':
            raise ExportBlocked('macOS 应用需要在 Mac 电脑上构建。')
        if platform == 'android':
            self._android_tools(emit, cancel_event, Path(work_dir))
        root = Path(work_dir) / platform
        root.mkdir(parents=True, exist_ok=False)
        shutil.copytree(web_dir, root / 'dist')
        if platform == 'android':
            return self._android(root, name, app_id, settings, node, emit, cancel_event)
        (root / 'package.json').write_text(json.dumps(desktop_package(name, app_id), ensure_ascii=False), 'utf-8')
        (root / 'main.cjs').write_text(ELECTRON_MAIN, 'utf-8')
        self._install(root, emit, cancel_event)
        # electron-builder downloads the exact Electron target itself; no install scripts needed.
        target, arch = ('--mac', platform[4:]) if platform.startswith('mac-') else ('--win', 'x64')
        self._run([node, str(root / 'node_modules/electron-builder/cli.js'), target, 'zip',
                   '--' + arch, '--publish', 'never'], root, emit, cancel_event, 'desktop-package')
        return self._artifacts(root / 'artifacts', '*.zip')

    def _android_tools(self, emit, cancel, work_dir):
        cap = self.capabilities()
        if not cap['android_sdk'] or not cap['java']:
            raise ExportBlocked('缺少 Android SDK 或 Java。请安装 Android Studio 的 SDK 与 JDK 21，并设置 ANDROID_HOME、JAVA_HOME 后继续；不会自动安装或接受许可。')
        sdk = Path(cap['android_sdk'])
        if not (sdk / 'licenses/android-sdk-license').is_file():
            raise ExportBlocked('尚未接受 Android SDK 许可，请在 Android Studio 中自行阅读并接受后继续。')
        if not (sdk / 'platforms/android-36/android.jar').is_file() or not (sdk / 'build-tools/36.0.0').is_dir():
            raise ExportBlocked('请在 Android Studio SDK Manager 中安装 Android API 36 和 Build Tools 36.0.0 后继续。')
        work_dir.mkdir(parents=True, exist_ok=True)
        self._run([cap['java'], '-version'], work_dir, emit, cancel, 'environment')

    def _android(self, root, name, app_id, settings, node, emit, cancel):
        dependencies = {f'@capacitor/{part}': CAPACITOR_VERSION for part in ('core', 'cli', 'android')}
        (root / 'package.json').write_text(json.dumps({'name': 'sceneops-android-export',
            'version': '1.0.0', 'private': True, 'dependencies': dependencies}), 'utf-8')
        (root / 'capacitor.config.json').write_text(capacitor_config(name, app_id), 'utf-8')
        self._install(root, emit, cancel)
        cli = str(root / 'node_modules/@capacitor/cli/bin/capacitor')
        self._run([node, cli, 'add', 'android'], root, emit, cancel, 'android-project')
        self._run([node, cli, 'sync', 'android'], root, emit, cancel, 'android-sync')
        manifest = root / 'android/app/src/main/AndroidManifest.xml'
        ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
        tree = ET.parse(manifest)
        orientation = settings.get('orientation', 'landscape')
        if orientation not in ('landscape', 'portrait'):
            raise ExportBuildError('屏幕方向必须是 landscape 或 portrait。')
        tree.find('application/activity').set('{http://schemas.android.com/apk/res/android}screenOrientation', orientation)
        tree.write(manifest, encoding='utf-8', xml_declaration=True)
        wrapper = root / 'android' / ('gradlew.bat' if os.name == 'nt' else 'gradlew')
        if os.name != 'nt':
            wrapper.chmod(0o755)
        self._run([str(wrapper), '--no-daemon', '-Pandroid.builder.sdkDownload=false', 'assembleDebug'],
                  root / 'android', emit, cancel, 'android-package')
        return self._artifacts(root / 'android/app/build/outputs/apk/debug', '*.apk')

    @staticmethod
    def _artifacts(root, pattern):
        paths = sorted(root.glob(pattern))
        if not paths or any(not path.is_file() or path.stat().st_size == 0 for path in paths):
            raise ExportBuildError('构建结束但没有生成有效安装包。')
        return paths
