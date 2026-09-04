from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Protocol

from .contracts import BlenderAdapterError


CancellationCheck = Callable[[], bool]


class BlenderProcessTransport(Protocol):
    filesystem_isolated: bool

    def health(self, executable: Path, timeout_seconds: float) -> str: ...

    def execute(
        self,
        executable: Path,
        bridge_path: Path,
        payload: str,
        timeout_seconds: float,
        is_cancelled: CancellationCheck,
    ) -> Dict[str, object]: ...


class SubprocessBlenderTransport:
    RESULT_PREFIX = "SCENEOPS_RESULT="
    filesystem_isolated = False

    def health(self, executable: Path, timeout_seconds: float) -> str:
        try:
            completed = subprocess.run(
                [str(executable), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                env=self._safe_environment(),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise BlenderAdapterError(
                "BLENDER_HEALTH_FAILED", "Blender health check failed", retryable=True
            ) from error
        first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
        if completed.returncode != 0 or "Blender" not in first_line:
            raise BlenderAdapterError("BLENDER_HEALTH_FAILED", "unexpected Blender --version response")
        return first_line.strip()

    def execute(
        self,
        executable: Path,
        bridge_path: Path,
        payload: str,
        timeout_seconds: float,
        is_cancelled: CancellationCheck,
    ) -> Dict[str, object]:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
            try:
                process = subprocess.Popen(
                    [
                        str(executable),
                        "--background",
                        "--factory-startup",
                        "--disable-autoexec",
                        "--python",
                        str(bridge_path),
                        "--",
                        payload,
                    ],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    text=True,
                    shell=False,
                    start_new_session=True,
                    env=self._safe_environment(),
                )
            except OSError as error:
                raise BlenderAdapterError(
                    "BLENDER_LAUNCH_FAILED", "Blender process could not start", retryable=True
                ) from error
            deadline = time.monotonic() + timeout_seconds
            while process.poll() is None:
                if is_cancelled():
                    self._stop(process)
                    raise BlenderAdapterError("BLENDER_CANCELLED", "Blender command cancelled")
                if time.monotonic() >= deadline:
                    self._stop(process)
                    raise BlenderAdapterError(
                        "BLENDER_TIMEOUT", "Blender command timed out", retryable=True
                    )
                time.sleep(0.05)
            try:
                output.seek(0)
                stdout = output.read()
            except UnicodeError as error:
                raise BlenderAdapterError(
                    "BLENDER_PROTOCOL_ERROR", "Blender output was not valid UTF-8"
                ) from error
        if process.returncode != 0:
            raise BlenderAdapterError(
                "BLENDER_COMMAND_FAILED",
                "Blender exited with status %d" % process.returncode,
                retryable=False,
            )
        result_lines = [line for line in stdout.splitlines() if line.startswith(self.RESULT_PREFIX)]
        if len(result_lines) != 1:
            raise BlenderAdapterError("BLENDER_PROTOCOL_ERROR", "missing typed bridge result")
        try:
            result = json.loads(result_lines[0][len(self.RESULT_PREFIX) :])
        except json.JSONDecodeError as error:
            raise BlenderAdapterError("BLENDER_PROTOCOL_ERROR", str(error)) from error
        if not isinstance(result, dict):
            raise BlenderAdapterError("BLENDER_PROTOCOL_ERROR", "bridge result must be an object")
        return result

    @staticmethod
    def _safe_environment() -> Dict[str, str]:
        allowed = ("PATH", "TMPDIR", "TMP", "TEMP")
        return {key: os.environ[key] for key in allowed if key in os.environ}

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired as error:
                raise BlenderAdapterError(
                    "BLENDER_TERMINATION_FAILED",
                    "Blender process could not be reaped after forced termination",
                ) from error
