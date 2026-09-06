from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from .errors import ErrorCode, VersionCollaborationError
from .git_models import GitProgress


@dataclass(frozen=True)
class GitCommandOutput:
    stdout: str
    stderr: str
    return_code: int


@dataclass(frozen=True)
class GitCommandLog:
    operation: str
    argument_names: tuple[str, ...]
    return_code: int | None
    duration_ms: int
    state: str


class GitCommandRunner:
    def __init__(
        self,
        *,
        git_binary: str = "git",
        timeout_seconds: float = 15,
        progress: Callable[[GitProgress], None] | None = None,
    ) -> None:
        self._git_binary = git_binary
        self._timeout_seconds = timeout_seconds
        self._progress = progress or (lambda _: None)
        self._logs: list[GitCommandLog] = []

    @property
    def logs(self) -> tuple[GitCommandLog, ...]:
        return tuple(self._logs)

    def run(
        self,
        operation: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        allowed_return_codes: tuple[int, ...] = (0,),
        cancellation: Event | None = None,
        mutation: bool = False,
    ) -> GitCommandOutput:
        attempts = 1 if mutation else 2
        last_error: VersionCollaborationError | None = None
        for attempt in range(attempts):
            try:
                return self._run_once(
                    operation,
                    args,
                    cwd=cwd,
                    allowed_return_codes=allowed_return_codes,
                    cancellation=cancellation,
                )
            except VersionCollaborationError as error:
                last_error = error
                if error.code != ErrorCode.GIT_TIMEOUT or attempt + 1 >= attempts:
                    raise
        assert last_error is not None
        raise last_error

    def _run_once(
        self,
        operation: str,
        args: tuple[str, ...],
        *,
        cwd: Path,
        allowed_return_codes: tuple[int, ...],
        cancellation: Event | None,
    ) -> GitCommandOutput:
        started = time.monotonic()
        self._progress(GitProgress(operation=operation, stage="git", state="started"))
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                (self._git_binary, *args),
                cwd=cwd,
                shell=False,
                env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
            )
            stdout, stderr = self._communicate(process, cancellation, started)
            if process.returncode not in allowed_return_codes:
                raise VersionCollaborationError(
                    ErrorCode.GIT_COMMAND_FAILED,
                    "Git could not complete the typed operation.",
                    details={"operation": operation, "return_code": process.returncode},
                    suggested_actions=("version.status.refresh", "integration.open"),
                )
            self._record(operation, args, process.returncode, started, "completed")
            self._progress(GitProgress(operation=operation, stage="git", state="completed"))
            return GitCommandOutput(stdout=stdout, stderr=stderr, return_code=process.returncode)
        except FileNotFoundError as error:
            self._record(operation, args, None, started, "failed")
            self._progress(GitProgress(operation=operation, stage="git", state="failed"))
            raise VersionCollaborationError(
                ErrorCode.GIT_OFFLINE,
                "Git executable is unavailable.",
                details={"operation": operation},
                suggested_actions=("integration.open",),
            ) from error
        except VersionCollaborationError as error:
            state = "cancelled" if error.code == ErrorCode.GIT_CANCELLED else "failed"
            self._record(operation, args, process.returncode if process else None, started, state)
            self._progress(GitProgress(operation=operation, stage="git", state=state))
            raise

    def _communicate(
        self, process: subprocess.Popen[str], cancellation: Event | None, started: float
    ) -> tuple[str, str]:
        while True:
            if cancellation is not None and cancellation.is_set():
                self._stop(process)
                raise VersionCollaborationError(
                    ErrorCode.GIT_CANCELLED,
                    "Git operation was cancelled.",
                    suggested_actions=("run.retry",),
                )
            remaining = self._timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                self._stop(process)
                raise VersionCollaborationError(
                    ErrorCode.GIT_TIMEOUT,
                    "Git operation exceeded its timeout.",
                    retryable=True,
                    suggested_actions=("run.retry", "integration.open"),
                )
            try:
                return process.communicate(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue

    def _stop(self, process: subprocess.Popen[str]) -> None:
        process.terminate()
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()

    def _record(
        self,
        operation: str,
        args: tuple[str, ...],
        return_code: int | None,
        started: float,
        state: str,
    ) -> None:
        safe_names = tuple(
            argument.split("=", 1)[0] if argument.startswith("-") else "<value>"
            for argument in args
        )
        self._logs.append(
            GitCommandLog(
                operation=operation,
                argument_names=safe_names,
                return_code=return_code,
                duration_ms=int((time.monotonic() - started) * 1000),
                state=state,
            )
        )
