"""Read local TCP listeners and stop a revalidated, user-owned development process."""
import asyncio
import os
import re
import shutil
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from typing import Literal
from pydantic import BaseModel
from sceneops_harness import HarnessError


class LocalEndpoint(BaseModel):
    host: str
    port: int


class LocalServerInfo(BaseModel):
    id: str
    pid: int
    name: str
    started_at: str
    endpoints: list[LocalEndpoint]
    project_id: str | None = None
    managed: bool = False
    can_stop: bool = False
    stop_reason: str | None = None


class LocalServerList(BaseModel):
    servers: list[LocalServerInfo]
    observed_at: str


class LocalServerStopResult(BaseModel):
    id: str
    state: Literal["stopped", "still_running"]
    remaining_endpoints: list[LocalEndpoint]
    message: str


def discover_listeners():
    """Use executable names, never process arguments or environment values."""
    executable = shutil.which('lsof')
    if executable is None:
        raise HarnessError('LOCAL_SERVER_TOOL_UNAVAILABLE', '找不到 lsof，无法读取本地服务。')
    environment = {**os.environ, 'LC_ALL': 'C'}
    try:
        listening = subprocess.run([executable, '-nP', '-iTCP', '-sTCP:LISTEN', '-Fpun'],
            capture_output=True, text=True, timeout=5, env=environment)
        processes = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid=,uid=,lstart=,comm='],
            capture_output=True, text=True, check=True, timeout=5, env=environment)
    except (OSError, subprocess.SubprocessError) as error:
        raise HarnessError('LOCAL_SERVER_DISCOVERY_FAILED', '读取本地监听服务失败。') from error
    if listening.returncode not in (0, 1) or (listening.returncode == 1 and listening.stderr.strip()):
        raise HarnessError('LOCAL_SERVER_DISCOVERY_FAILED', '无法取得当前本地监听服务。')
    metadata = {}
    for line in processes.stdout.splitlines():
        parts = line.split(None, 8)
        if len(parts) != 9:
            continue
        pid, parent, uid = map(int, parts[:3])
        started = datetime.strptime(' '.join(parts[3:8]), '%a %b %d %H:%M:%S %Y').astimezone(timezone.utc)
        metadata[pid] = {'pid': pid, 'parent': parent, 'uid': uid,
                         'started_at': started.isoformat(), 'name': Path(parts[8]).name, 'endpoints': []}
    pid = None
    for line in listening.stdout.splitlines():
        if line.startswith('p'):
            pid = int(line[1:])
        elif line.startswith('n') and pid in metadata:
            host, port = line[1:].rsplit(':', 1)
            endpoint = (host.strip('[]'), int(port))
            if endpoint not in metadata[pid]['endpoints']:
                metadata[pid]['endpoints'].append(endpoint)
    return metadata


class LocalServerInventory:
    def __init__(self, game_runtime=None):
        self.game = game_runtime
        self.selections = {}
        self.lock = asyncio.Lock()

    def _managed(self):
        if self.game is None:
            return {}
        return {item['process'].pid: item['run'].project_id for item in self.game.previews.values()
                if item['process'].returncode is None}

    @staticmethod
    def _identity(item):
        return (item['pid'], item['started_at'], item['uid'], tuple(sorted(item['endpoints'])))

    @staticmethod
    def _stop_reason(item, metadata, protected_ports):
        protected = {1, os.getpid()}
        parent = metadata.get(os.getpid(), {}).get('parent')
        while parent and parent not in protected:
            protected.add(parent)
            parent = metadata.get(parent, {}).get('parent')
        if item['pid'] in protected or any(port in protected_ports for _, port in item['endpoints']):
            return '当前应用或其控制服务，不能从这里停止。'
        if item['uid'] != os.getuid():
            return '其他用户或系统拥有的服务，仅供查看。'
        if not re.fullmatch(r'node|bun|deno|ruby|php|python(?:\d+(?:\.\d+)*)?', item['name'], re.I):
            return '未识别为开发运行时，仅供查看。'
        return None

    async def list(self, protected_ports=()):
        async with self.lock:
            metadata = await asyncio.to_thread(discover_listeners)
            managed = self._managed()
            old = {identity: key for key, identity in self.selections.items()}
            selections, servers = {}, []
            for item in metadata.values():
                if not item['endpoints']:
                    continue
                identity = self._identity(item)
                key = old.get(identity) or 'server_' + uuid4().hex
                selections[key] = identity
                reason = self._stop_reason(item, metadata, protected_ports)
                servers.append(LocalServerInfo(id=key, pid=item['pid'], name=item['name'],
                    started_at=item['started_at'], endpoints=[LocalEndpoint(host=host, port=port)
                        for host, port in sorted(item['endpoints'])], project_id=managed.get(item['pid']),
                    managed=item['pid'] in managed, can_stop=reason is None, stop_reason=reason))
            self.selections = selections
            return LocalServerList(servers=sorted(servers, key=lambda item: item.endpoints[0].port),
                                   observed_at=datetime.now(timezone.utc).isoformat())

    async def stop(self, server_id, protected_ports=()):
        async with self.lock:
            identity = self.selections.get(server_id)
            if identity is None:
                raise HarnessError('LOCAL_SERVER_SELECTION_EXPIRED', '服务列表已改变，请刷新后重新选择。')
            metadata = await asyncio.to_thread(discover_listeners)
            item = metadata.get(identity[0])
            if item is None or self._identity(item) != identity:
                raise HarnessError('LOCAL_SERVER_SELECTION_CHANGED', '该进程或监听端口已改变，未发送停止信号。')
            reason = self._stop_reason(item, metadata, protected_ports)
            if reason:
                raise HarnessError('LOCAL_SERVER_STOP_DENIED', reason)
            try:
                os.kill(item['pid'], signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError as error:
                raise HarnessError('LOCAL_SERVER_STOP_DENIED', '没有停止该进程的系统权限。') from error
            if self.game is not None:
                for active in self.game.previews.values():
                    if active['process'].pid == item['pid']:
                        active['stop_requested'] = True
            await asyncio.sleep(0.25)
            current = (await asyncio.to_thread(discover_listeners)).get(item['pid'])
            endpoints = (current['endpoints'] if current and current['started_at'] == item['started_at'] else [])
            return LocalServerStopResult(id=server_id, state='still_running' if endpoints else 'stopped',
                remaining_endpoints=[LocalEndpoint(host=host, port=port) for host, port in endpoints],
                message='已发送停止请求，服务仍在监听。' if endpoints else '该服务已不再监听。')
