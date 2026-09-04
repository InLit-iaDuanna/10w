"""Fixed-argument Unity batch runner with timeout and cancellation."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from threading import Event
from typing import Any, Dict, List, Optional, Protocol

from .contracts import CommandName, CommandRequest, RunTestsPayload
from .errors import ErrorCode, UnityIntegrationError


class UnityCommandRunner(Protocol):
    def execute(
        self,
        request: CommandRequest,
        project_root: Path,
        cancellation: Optional[Event] = None,
    ) -> Dict[str, Any]:
        ...


class UnityBatchRunner:
    """Invokes one pinned SceneOps router; callers cannot supply methods or flags."""

    ROUTER_METHOD = "SceneOps.Forge.Unity.Editor.SceneOpsBatchCommandRouter.Execute"

    def __init__(self, unity_editor: str) -> None:
        self.unity_editor = str(Path(unity_editor).resolve(strict=False))

    def editor_version(self, timeout_seconds: float = 20) -> str:
        try:
            completed = subprocess.run(
                [self.unity_editor, "-version"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise UnityIntegrationError(
                ErrorCode.INTEGRATION_OFFLINE,
                "Configured Unity editor executable is unavailable.",
                retryable=True,
                details={"unity_editor": self.unity_editor},
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise UnityIntegrationError(
                ErrorCode.TIMEOUT,
                "Unity version check timed out.",
                retryable=True,
            ) from exc
        output = (completed.stdout or completed.stderr).strip()
        if completed.returncode != 0 or not output:
            raise UnityIntegrationError(
                ErrorCode.INTEGRATION_OFFLINE,
                "Unity version check failed.",
                retryable=True,
                details={"return_code": completed.returncode, "output": output[-2000:]},
            )
        return output.splitlines()[-1].strip()

    def execute(
        self,
        request: CommandRequest,
        project_root: Path,
        cancellation: Optional[Event] = None,
    ) -> Dict[str, Any]:
        if request.command is CommandName.RUN_TESTS:
            return self._run_unity_tests(request, project_root, cancellation)
        with tempfile.TemporaryDirectory(prefix="sceneops-unity-command-") as temp_dir:
            temporary = Path(temp_dir)
            request_path = temporary / "request.json"
            result_path = temporary / "result.json"
            log_path = temporary / "unity.log"
            request_path.write_text(
                json.dumps(self._wire_request(request), sort_keys=True), encoding="utf-8"
            )
            arguments = [
                self.unity_editor,
                "-batchmode",
                "-nographics",
                "-quit",
                "-projectPath",
                str(project_root),
                "-executeMethod",
                self.ROUTER_METHOD,
                "-sceneopsRequest",
                str(request_path),
                "-sceneopsResult",
                str(result_path),
                "-logFile",
                str(log_path),
            ]
            return_code = self._run_process(
                arguments, request.timeout_seconds, cancellation, log_path
            )
            log_tail = _read_tail(log_path)
            if not result_path.is_file():
                code = _map_log_error(log_tail, request.command)
                raise UnityIntegrationError(
                    code,
                    "Unity exited without producing a SceneOps command result.",
                    retryable=code in {ErrorCode.INTEGRATION_OFFLINE, ErrorCode.TIMEOUT},
                    details={"return_code": return_code, "log_tail": log_tail},
                )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise UnityIntegrationError(
                    ErrorCode.RESULT_INVALID,
                    "Unity returned an invalid SceneOps result document.",
                    details={"log_tail": log_tail},
                ) from exc
            if return_code != 0 and result.get("status") == "succeeded":
                raise UnityIntegrationError(
                    _map_log_error(log_tail, request.command),
                    "Unity process failed after reporting command success.",
                    details={"return_code": return_code, "log_tail": log_tail},
                )
            result["processReturnCode"] = return_code
            result["unityLogTail"] = log_tail
            return result

    def _run_unity_tests(
        self,
        request: CommandRequest,
        project_root: Path,
        cancellation: Optional[Event],
    ) -> Dict[str, Any]:
        payload = RunTestsPayload.model_validate(request.payload)
        results_path = (project_root / payload.results_path).resolve(strict=False)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        log_path = results_path.with_suffix(".unity.log")
        arguments = [
            self.unity_editor,
            "-batchmode",
            "-nographics",
            "-projectPath",
            str(project_root),
            "-runTests",
            "-testPlatform",
            payload.test_mode.lower(),
            "-testResults",
            str(results_path),
            "-logFile",
            str(log_path),
        ]
        if payload.test_filter:
            arguments.extend(["-testFilter", payload.test_filter])
        return_code = self._run_process(
            arguments, request.timeout_seconds, cancellation, log_path
        )
        log_tail = _read_tail(log_path)
        if not results_path.is_file():
            raise UnityIntegrationError(
                _map_log_error(log_tail, CommandName.RUN_TESTS),
                "Unity test runner did not produce a result file.",
                details={"return_code": return_code, "log_tail": log_tail},
            )
        summary = _parse_test_results(results_path)
        if return_code != 0 or summary["failed"]:
            raise UnityIntegrationError(
                ErrorCode.TEST_FAILED,
                "Unity test run failed.",
                retryable=False,
                details={**summary, "return_code": return_code, "log_tail": log_tail},
            )
        return {
            "status": "succeeded",
            "message": "Unity test run completed.",
            "data": {**summary, "resultsPath": str(results_path)},
            "logs": [],
        }

    def _run_process(
        self,
        arguments: List[str],
        timeout_seconds: float,
        cancellation: Optional[Event],
        log_path: Path,
    ) -> int:
        try:
            process = subprocess.Popen(arguments)
        except (FileNotFoundError, PermissionError) as exc:
            raise UnityIntegrationError(
                ErrorCode.INTEGRATION_OFFLINE,
                "Configured Unity editor executable is unavailable.",
                retryable=True,
                details={"unity_editor": self.unity_editor},
            ) from exc

        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None:
            if cancellation and cancellation.is_set():
                _terminate(process)
                raise UnityIntegrationError(
                    ErrorCode.CANCELLED,
                    "Unity command was cancelled.",
                    details={"log_tail": _read_tail(log_path)},
                )
            if time.monotonic() >= deadline:
                _terminate(process)
                raise UnityIntegrationError(
                    ErrorCode.TIMEOUT,
                    "Unity command exceeded its timeout.",
                    retryable=True,
                    details={"log_tail": _read_tail(log_path)},
                )
            time.sleep(0.05)
        return int(process.returncode or 0)

    @staticmethod
    def _wire_request(request: CommandRequest) -> Dict[str, Any]:
        payload = request.typed_payload().model_dump(mode="json")
        if request.command is CommandName.SET_COMPONENT_PROPERTY and "value" in payload:
            payload["value_json"] = json.dumps(payload.pop("value"), sort_keys=True)
        payload_json = json.dumps(payload, sort_keys=True)
        change_set_json = ""
        if request.change_set:
            change_set_json = json.dumps(
                {
                    "change_set_id": request.change_set.change_set_id,
                    "base_version": request.change_set.base_version,
                    "approval_state": request.change_set.approval_state.value,
                    "command": request.change_set.command.value,
                    "target_object_ids": request.change_set.target_object_ids,
                    "proposed_payload_json": payload_json,
                },
                sort_keys=True,
            )
        return {
            "requestId": request.request_id,
            "command": request.command.value,
            "projectId": request.project_id,
            "projectRoot": request.project_root,
            "baseVersion": request.base_version,
            "executionMode": request.mode.value,
            "payloadJson": payload_json,
            "changeSetJson": change_set_json,
        }


def _terminate(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _read_tail(path: Path, limit: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def _map_log_error(log: str, command: CommandName) -> ErrorCode:
    lowered = log.lower()
    if "compiler error" in lowered or "scripts have compiler errors" in lowered:
        return ErrorCode.COMPILE_FAILED
    if "missing material" in lowered:
        return ErrorCode.MISSING_MATERIAL
    if "missing script" in lowered:
        return ErrorCode.MISSING_SCRIPT
    if command is CommandName.RUN_TESTS:
        return ErrorCode.TEST_FAILED
    if command is CommandName.RUN_BUILD:
        return ErrorCode.BUILD_FAILED
    return ErrorCode.RESULT_MISSING


def _parse_test_results(path: Path) -> Dict[str, int]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise UnityIntegrationError(
            ErrorCode.RESULT_INVALID,
            "Unity test result XML is invalid.",
            details={"path": str(path)},
        ) from exc
    return {
        "total": int(root.attrib.get("total", root.attrib.get("testcasecount", "0"))),
        "passed": int(root.attrib.get("passed", root.attrib.get("passedcount", "0"))),
        "failed": int(root.attrib.get("failed", root.attrib.get("failedcount", "0"))),
        "skipped": int(root.attrib.get("skipped", root.attrib.get("skippedcount", "0"))),
    }
