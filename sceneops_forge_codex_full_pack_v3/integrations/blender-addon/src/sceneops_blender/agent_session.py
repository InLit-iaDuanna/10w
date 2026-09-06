"""Visible, task-owned Blender session with an OS-enforced filesystem boundary."""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

from .agent_protocol import validate_binding, validate_command


def sandbox_profile(workspace: Path, state: Path, executable: Path, source: Path) -> str:
    quote = lambda value: json.dumps(str(value))
    reads = ["/System", "/usr", "/bin", "/sbin", "/Library", "/private/etc", "/private/var/db", "/dev", str(executable.parents[2]), str(source)]
    lines = ["(version 1)", "(deny default)", "(allow process-info* sysctl-read mach* ipc* iokit* signal)",
             '(allow file-read* (literal "/"))',
             '(allow file-read-metadata (literal "/var") (literal "/etc") (literal "/Applications"))',
             "(allow process-fork)", f"(allow process-exec (literal {quote(executable)}))",
             '(allow network-inbound (local ip "localhost:*"))',
             '(allow network-outbound (remote ip "localhost:*"))']
    for path in reads:
        lines.append(f"(allow file-read* (subpath {quote(path)}))")
    for parent in sorted({parent for root in (workspace, state, source) for parent in root.parents}):
        lines.append(f"(allow file-read-metadata (literal {quote(parent)}))")
    for path in (workspace, state):
        lines.append(f"(allow file-read* file-write* (subpath {quote(path)}))")
    lines.append('(allow file-write-data (literal "/dev/null"))')
    return "\n".join(lines)


class BlenderAgentSession:
    def __init__(self, workspace_root: Path, state_root: Path, *, executable: Path | None = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.content_root = self.workspace_root / "blender"
        self.state_root = Path(state_root).resolve()
        if self.workspace_root == self.state_root or self.workspace_root in self.state_root.parents or self.state_root in self.workspace_root.parents:
            raise ValueError("workspace and tool state must be separate directories")
        self.executable = Path(executable or "/Applications/Blender.app/Contents/MacOS/Blender").resolve()
        self._process = None
        self._connection = None
        self._binding = None

    def bind_authorization(self, authorization: dict) -> None:
        binding = validate_binding(authorization)
        if Path(binding["workspace_root"]).resolve() != self.workspace_root:
            raise ValueError("grant does not cover this workspace")
        if self._binding is not None and self._binding != binding:
            raise ValueError("a tool session cannot change task grant")
        self._binding = binding

    def start(self) -> dict:
        if self._binding is None:
            raise ValueError("bind_authorization must precede session start")
        if os.name != "posix":
            raise RuntimeError("BLENDER_SANDBOX_UNAVAILABLE: persistent sessions require macOS sandbox-exec")
        import fcntl
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state_root / "startup.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._start()

    def _start(self) -> dict:
        metadata = self.state_root / "session.json"
        if self.content_root.resolve() != self.content_root:
            raise ValueError("Blender content directory must not be a symlink")
        if not metadata.exists() and self.content_root.exists() and any(self.content_root.iterdir()):
            raise ValueError("a new agent session requires an empty Blender content directory")
        if metadata.exists():
            self._connection = json.loads(metadata.read_text())
            if self._connection["binding"] != self._binding or self._connection["workspace_root"] != str(self.workspace_root):
                raise ValueError("persisted session belongs to another task or workspace")
            try:
                return self.inspect()
            except (OSError, TimeoutError):
                pid_file = self.state_root / "process.pid"
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), 0)
                    except ProcessLookupError:
                        pass
                    else:
                        raise ConnectionError("BLENDER_SESSION_DISCONNECTED: owned editor is still running; reconnect after it responds")
                self._connection = None
        if not self.executable.is_file() or not Path("/usr/bin/sandbox-exec").is_file():
            raise RuntimeError("BLENDER_SANDBOX_UNAVAILABLE: Blender or macOS sandbox-exec is unavailable")
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.content_root.mkdir(exist_ok=True)
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_root, 0o700)
        for name in ("tmp", "config", "cache"):
            (self.state_root / name).mkdir(exist_ok=True)
        source = Path(__file__).resolve().parents[2]
        bootstrap = source / "scripts" / "agent_bridge.py"
        with socket.socket() as reserve:
            reserve.bind(("127.0.0.1", 0))
            port = reserve.getsockname()[1]
        self._connection = {"port": port, "token": secrets.token_urlsafe(32), "binding": self._binding,
                            "workspace_root": str(self.workspace_root), "content_root": str(self.content_root), "state_root": str(self.state_root),
                            "session_id": "blender_" + secrets.token_hex(12),
                            "outside_probe": str(self.workspace_root.parent / ("isolation-probe-" + secrets.token_hex(12)))}
        metadata.write_text(json.dumps(self._connection))
        os.chmod(metadata, 0o600)
        profile = sandbox_profile(self.content_root, self.state_root, self.executable, source)
        (self.state_root / "sandbox.sb").write_text(profile)
        env = {key: os.environ[key] for key in ("PATH", "LANG", "DISPLAY", "__CF_USER_TEXT_ENCODING") if key in os.environ}
        env.update(HOME=str(self.state_root), TMPDIR=str(self.state_root / "tmp"),
                   BLENDER_USER_CONFIG=str(self.state_root / "config"), XDG_CACHE_HOME=str(self.state_root / "cache"))
        with (self.state_root / "blender.log").open("ab") as log:
            self._process = subprocess.Popen(["/usr/bin/sandbox-exec", "-f", str(self.state_root / "sandbox.sb"),
                str(self.executable), "--factory-startup", "--disable-autoexec", "--python", str(bootstrap), "--", str(metadata)],
                cwd=self.content_root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        (self.state_root / "process.pid").write_text(str(self._process.pid))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(f"BLENDER_START_FAILED: process exited {self._process.returncode}; see {self.state_root / 'blender.log'}")
            try:
                return self.inspect()
            except (OSError, TimeoutError):
                time.sleep(0.2)
        self._process.terminate()
        self._process.wait(timeout=15)
        raise TimeoutError("BLENDER_CONNECT_TIMEOUT: visible editor did not expose its session; owned process stopped")

    def _request(self, command: dict) -> dict:
        validate_command(command, self._binding or {})
        if self._connection is None:
            raise ConnectionError("Blender session is not connected")
        payload = {"token": self._connection["token"], "command": command}
        with socket.create_connection(("127.0.0.1", self._connection["port"]), timeout=10) as connection:
            connection.settimeout(60)
            connection.sendall(json.dumps(payload, allow_nan=False).encode() + b"\n")
            with connection.makefile("rb") as reader:
                raw = reader.readline(1024 * 1024)
        if not raw:
            raise ConnectionError("Blender session disconnected before acknowledging the command")
        result = json.loads(raw)
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "Blender command failed"))
        evidence = result["result"]
        if evidence.get("session_id") != self._connection["session_id"]:
            raise RuntimeError("Blender endpoint belongs to another session")
        return evidence

    def inspect(self) -> dict:
        return self._request({"operation": "inspect"})

    def create_asset(self, *, request_id, asset_id, sceneops_id, dimensions_m, authorization: dict, name=None, dry_run=False) -> dict:
        command = dict(operation="create_asset", request_id=request_id, asset_id=asset_id,
                       sceneops_id=sceneops_id, dimensions_m=dimensions_m, authorization=authorization)
        if name is not None:
            command["name"] = name
        return self._mutation(command, dry_run)

    def export_asset(self, *, request_id, asset_id, authorization: dict, dry_run=False) -> dict:
        return self._mutation(dict(operation="export_asset", request_id=request_id, asset_id=asset_id, authorization=authorization), dry_run)

    def _mutation(self, command, dry_run):
        validate_command(command, self._binding or {})
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be boolean")
        if dry_run:
            outputs = ["scene.blend"] if command["operation"] == "create_asset" else [command["asset_id"] + suffix for suffix in (".fbx", ".identity.json")]
            return {"mode": "planned", "operation": command["operation"], "request_id": command["request_id"],
                    "would_write": [str(self.content_root / name) for name in outputs]}
        return self._request(command)

    def stop(self) -> None:
        if self._connection is not None:
            self._request({"operation": "stop"})
        if self._process is not None:
            self._process.wait(timeout=15)
        self._connection = None
