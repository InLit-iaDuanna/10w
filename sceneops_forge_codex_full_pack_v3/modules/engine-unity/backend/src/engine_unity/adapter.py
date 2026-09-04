"""Safe Unity adapter implementing validation, modes, retry, and truthful results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any, Dict, Iterable, List, Optional

from pydantic import ValidationError

from .cache import LiveResultCache
from .build_manifest import (
    BuildTestEvidence,
    UnityBuildManifest,
    artifact_record,
)
from .contracts import (
    BuildPayload,
    CapabilityReport,
    ChangePreview,
    CommandName,
    CommandRequest,
    CommandResult,
    CommandStatus,
    ExecutionContext,
    ExecutionMode,
    ResultError,
    StructuredLog,
)
from .errors import ErrorCode, UnityIntegrationError
from .mock_runner import FixtureUnityRunner
from .policy import COMMAND_POLICIES, command_policy
from .runner import UnityBatchRunner, UnityCommandRunner
from .security import validate_command_request
from .versioning import (
    MAXIMUM_MAJOR,
    MINIMUM_VERSION,
    PINNED_UNITY_VERSION,
    project_unity_version,
    validate_unity_version,
)


class UnityAdapter:
    ADAPTER_VERSION = "0.1.0"

    def __init__(
        self,
        *,
        live_runner: Optional[UnityCommandRunner],
        mock_runner: FixtureUnityRunner,
        cache: Optional[LiveResultCache] = None,
    ) -> None:
        self.live_runner = live_runner
        self.mock_runner = mock_runner
        self.cache = cache or LiveResultCache()
        self._idempotent_results: Dict[str, CommandResult] = {}
        self._idempotent_signatures: Dict[str, str] = {}
        self._live_execution_lock = Lock()

    @classmethod
    def with_defaults(
        cls,
        *,
        unity_editor: Optional[str],
        fixture_file: Path,
    ) -> "UnityAdapter":
        live = UnityBatchRunner(unity_editor) if unity_editor else None
        return cls(live_runner=live, mock_runner=FixtureUnityRunner(fixture_file))

    def capabilities(self) -> CapabilityReport:
        return CapabilityReport(
            adapter_version=self.ADAPTER_VERSION,
            minimum_unity_version=".".join(str(part) for part in MINIMUM_VERSION),
            maximum_unity_major=MAXIMUM_MAJOR,
            pinned_unity_version=PINNED_UNITY_VERSION,
            command_allowlist=list(COMMAND_POLICIES),
            execution_modes=frozenset(ExecutionMode),
        )

    def dry_run(
        self, request: CommandRequest, context: ExecutionContext
    ) -> ChangePreview:
        root, payload, target_paths = validate_command_request(
            request, context, enforce_approval=False
        )
        policy = command_policy(request.command)
        proposed = (
            request.change_set.proposed_values
            if request.change_set
            else payload.model_dump(mode="json")
        )
        return ChangePreview(
            request_id=request.request_id,
            command=request.command,
            mutating=policy.mutating,
            approval_required=policy.approval_required,
            resolved_project_root=str(root),
            target_paths=target_paths,
            proposed_values=proposed,
            validation_steps=[
                "project root boundary",
                "typed payload schema",
                "permission policy",
                "base version",
                "command and component allowlists",
            ],
        )

    def execute(
        self,
        request: CommandRequest,
        context: ExecutionContext,
        cancellation: Optional[Event] = None,
    ) -> CommandResult:
        if request.mode is ExecutionMode.BLOCKED:
            return self._blocked_result(request, "Execution was explicitly marked blocked.")

        enforce_approval = request.mode not in {
            ExecutionMode.PLANNED,
            ExecutionMode.CACHED,
        }
        try:
            root, _, _ = validate_command_request(
                request, context, enforce_approval=enforce_approval
            )
            validate_unity_version(project_unity_version(root))
        except UnityIntegrationError as error:
            return self._error_result(request, error, attempts=0)

        if request.mode is ExecutionMode.PLANNED:
            preview = self.dry_run(request, context)
            return CommandResult(
                request_id=request.request_id,
                command=request.command,
                status=CommandStatus.PLANNED,
                mode=ExecutionMode.PLANNED,
                attempts=0,
                data=preview.model_dump(mode="json"),
            )

        if request.mode is ExecutionMode.CACHED:
            if not request.cache_key:
                return self._error_result(
                    request,
                    UnityIntegrationError(
                        ErrorCode.CACHE_MISS,
                        "Cached execution requires cache_key.",
                    ),
                    attempts=0,
                )
            try:
                scope = self._request_scope(
                    request, request.cache_key, context=context, project_root=root
                )
                signature = self._request_signature(request)
                if scope not in self._idempotent_signatures:
                    raise UnityIntegrationError(
                        ErrorCode.CACHE_MISS,
                        "No matching successful live Unity request exists in this scope.",
                    )
                if self._idempotent_signatures[scope] != signature:
                    raise UnityIntegrationError(
                        ErrorCode.IDEMPOTENCY_CONFLICT,
                        "Cached Unity input does not match the successful live request.",
                    )
                return self.cache.replay(scope, request.request_id)
            except UnityIntegrationError as error:
                return self._error_result(request, error, attempts=0)

        if request.mode is ExecutionMode.MOCK:
            return self._execute_with_retry(
                request, root, self.mock_runner, cancellation
            )

        with self._live_execution_lock:
            return self._execute_live(request, context, root, cancellation)

    @staticmethod
    def _request_scope(
        request: CommandRequest,
        key: str,
        *,
        context: ExecutionContext,
        project_root: Path,
    ) -> str:
        return json.dumps(
            {
                "actor_id": context.actor_id,
                "project_id": request.project_id,
                "project_root": str(project_root),
                "command": request.command.value,
                "base_version": request.base_version,
                "key": key,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _request_signature(request: CommandRequest) -> str:
        change_set = (
            request.change_set.model_dump(mode="json") if request.change_set else None
        )
        return json.dumps(
            {
                "payload": request.typed_payload().model_dump(mode="json"),
                "change_set": change_set,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _execute_live(
        self,
        request: CommandRequest,
        context: ExecutionContext,
        root: Path,
        cancellation: Optional[Event],
    ) -> CommandResult:
        scope = self._request_scope(
            request, request.idempotency_key, context=context, project_root=root
        )
        signature = self._request_signature(request)
        if scope in self._idempotent_results:
            if self._idempotent_signatures[scope] != signature:
                return self._error_result(
                    request,
                    UnityIntegrationError(
                        ErrorCode.IDEMPOTENCY_CONFLICT,
                        "Idempotency key was reused with different Unity command input.",
                    ),
                    attempts=0,
                )
            original = self._idempotent_results[scope]
            return original.model_copy(
                update={
                    "request_id": request.request_id,
                    "mode": ExecutionMode.CACHED,
                    "cached_from_request_id": original.request_id,
                },
                deep=True,
            )

        if self.live_runner is None:
            return self._blocked_result(
                request,
                "No Unity editor is configured for live execution.",
                ErrorCode.INTEGRATION_OFFLINE,
            )

        try:
            if request.command is CommandName.RUN_BUILD:
                self._validate_new_build_identity(request, root)
            if isinstance(self.live_runner, UnityBatchRunner):
                validate_unity_version(self.live_runner.editor_version())
        except UnityIntegrationError as error:
            return self._error_result(request, error, attempts=0)

        result = self._execute_with_retry(
            request, root, self.live_runner, cancellation
        )
        if result.status is CommandStatus.SUCCEEDED:
            self._idempotent_results[scope] = result.model_copy(deep=True)
            self._idempotent_signatures[scope] = signature
            self.cache.put(scope, result)
        return result

    @staticmethod
    def _validate_new_build_identity(request: CommandRequest, root: Path) -> None:
        payload = BuildPayload.model_validate(request.payload)
        manifest_path = root / "Artifacts" / "BuildManifests" / f"{payload.build_id}.json"
        if manifest_path.exists():
            raise UnityIntegrationError(
                ErrorCode.IDENTITY_CONFLICT,
                "Build ID already has an immutable Unity build manifest.",
                details={"build_id": payload.build_id},
            )

    def _execute_with_retry(
        self,
        request: CommandRequest,
        root: Path,
        runner: UnityCommandRunner,
        cancellation: Optional[Event],
    ) -> CommandResult:
        policy = command_policy(request.command)
        attempts_allowed = request.max_attempts if policy.retryable else 1
        logs: List[StructuredLog] = []
        for attempt in range(1, attempts_allowed + 1):
            logs.append(
                StructuredLog.now(
                    "info",
                    "UNITY_COMMAND_ATTEMPT_STARTED",
                    "Unity command attempt started.",
                    attempt=attempt,
                )
            )
            try:
                raw = runner.execute(request, root, cancellation)
                result = self._result_from_raw(request, raw, attempt, logs, root)
                if result.status is not CommandStatus.FAILED:
                    return result
                if not result.error or not result.error.retryable or attempt == attempts_allowed:
                    return result
            except UnityIntegrationError as error:
                logs.append(
                    StructuredLog.now(
                        "error", error.code.value, str(error), **error.details
                    )
                )
                if not (error.retryable and policy.retryable and attempt < attempts_allowed):
                    return self._error_result(request, error, attempts=attempt, logs=logs)
        raise AssertionError("retry loop exited without a result")

    def _result_from_raw(
        self,
        request: CommandRequest,
        raw: Dict[str, Any],
        attempts: int,
        prefix_logs: List[StructuredLog],
        project_root: Path,
    ) -> CommandResult:
        status_value = str(raw.get("status", "failed"))
        status = (
            CommandStatus.SUCCEEDED
            if status_value == "succeeded"
            else CommandStatus.FAILED
        )
        logs = [*prefix_logs, *_parse_logs(raw.get("logs", []))]
        data = raw.get("data") or {}
        if not data and raw.get("resultJson"):
            try:
                data = json.loads(raw["resultJson"])
            except json.JSONDecodeError:
                data = {"rawResult": raw["resultJson"]}
        error = None
        if status is CommandStatus.FAILED:
            error = ResultError(
                code=str(raw.get("errorCode") or ErrorCode.RESULT_INVALID.value),
                message=str(raw.get("message") or "Unity command failed."),
                retryable=bool(raw.get("retryable", False)),
                details={"unity_log_tail": raw.get("unityLogTail", "")},
            )
        result = CommandResult(
            request_id=request.request_id,
            command=request.command,
            status=status,
            mode=request.mode,
            attempts=attempts,
            data=data,
            logs=logs,
            error=error,
        )
        if (
            result.status is CommandStatus.SUCCEEDED
            and result.mode is ExecutionMode.LIVE
            and request.command is CommandName.RUN_BUILD
        ):
            result = self._attach_live_build_manifest(result, request, project_root)
        return result

    def _attach_live_build_manifest(
        self,
        result: CommandResult,
        request: CommandRequest,
        project_root: Path,
    ) -> CommandResult:
        payload = BuildPayload.model_validate(request.payload)
        artifact_path = project_root / payload.output_path
        if not artifact_path.exists():
            raise UnityIntegrationError(
                ErrorCode.RESULT_MISSING,
                "Unity reported build success but the build artifact is missing.",
                details={"output_path": str(artifact_path)},
            )
        test_evidence = [
            BuildTestEvidence(
                run_id=run_id,
                status="blocked",
                mode=ExecutionMode.BLOCKED,
                results_path="",
            )
            for run_id in payload.required_test_runs
        ]
        manifest = UnityBuildManifest(
            build_id=payload.build_id,
            project_id=request.project_id,
            profile=payload.profile,
            execution_mode=ExecutionMode.LIVE,
            unity_version=str(result.data.get("unityVersion", "2022.3")),
            package_version=self.ADAPTER_VERSION,
            source_commit=payload.source_commit,
            scenes=list(payload.scenes),
            source_assets=[
                source.model_dump(mode="json") for source in payload.source_assets
            ],
            settings={"target": payload.target, "development": payload.development},
            tests=test_evidence,
            artifacts=[artifact_record(project_root, artifact_path)],
            produced_at=datetime.now(timezone.utc),
        )
        manifest_path = project_root / "Artifacts" / "BuildManifests" / f"{payload.build_id}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with manifest_path.open("x", encoding="utf-8") as stream:
                stream.write(manifest.model_dump_json(indent=2))
        except FileExistsError as exc:
            raise UnityIntegrationError(
                ErrorCode.IDENTITY_CONFLICT,
                "Build ID already has an immutable Unity build manifest.",
                details={"build_id": payload.build_id},
            ) from exc
        data = dict(result.data)
        data["buildManifest"] = manifest.model_dump(mode="json")
        data["buildManifestPath"] = str(manifest_path.relative_to(project_root))
        return result.model_copy(update={"data": data}, deep=True)

    @staticmethod
    def _blocked_result(
        request: CommandRequest,
        message: str,
        code: ErrorCode = ErrorCode.INTEGRATION_OFFLINE,
    ) -> CommandResult:
        return CommandResult(
            request_id=request.request_id,
            command=request.command,
            status=CommandStatus.BLOCKED,
            mode=ExecutionMode.BLOCKED,
            attempts=0,
            error=ResultError(code=code.value, message=message, retryable=True),
        )

    @staticmethod
    def _error_result(
        request: CommandRequest,
        error: UnityIntegrationError,
        *,
        attempts: int,
        logs: Optional[List[StructuredLog]] = None,
    ) -> CommandResult:
        if error.code is ErrorCode.APPROVAL_REQUIRED:
            status = CommandStatus.WAITING_APPROVAL
        elif error.code is ErrorCode.CANCELLED:
            status = CommandStatus.CANCELLED
        else:
            status = CommandStatus.FAILED
        mode = request.mode
        return CommandResult(
            request_id=request.request_id,
            command=request.command,
            status=status,
            mode=mode,
            attempts=attempts,
            logs=logs or [],
            error=ResultError(
                code=error.code.value,
                message=str(error),
                retryable=error.retryable,
                details=error.details,
            ),
        )


def _parse_logs(raw_logs: Iterable[Dict[str, Any]]) -> List[StructuredLog]:
    parsed: List[StructuredLog] = []
    for item in raw_logs:
        occurred_at = item.get("occurredAt") or item.get("occurred_at")
        try:
            timestamp = datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            timestamp = StructuredLog.now("debug", "UNITY_LOG_TIME_REPAIRED", "").occurred_at
        parsed.append(
            StructuredLog(
                level=item.get("level", "info"),
                code=item.get("code", "UNITY_LOG"),
                message=item.get("message", ""),
                occurred_at=timestamp,
                details=item.get("details", {}),
            )
        )
    return parsed
