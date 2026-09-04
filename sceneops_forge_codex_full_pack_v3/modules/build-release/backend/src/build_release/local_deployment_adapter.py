"""Contained, verified, atomically activated local release adapter."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .adapter_support import (
    SystemUtcClock,
    atomic_write_json,
    assert_no_symlink_chain,
    assert_within,
    ensure_contained_directory,
    resolve_regular_file,
    validated_root,
)
from .checksum import file_sha256
from .enums import DeploymentTarget, ExecutionMode
from .errors import AdapterExecutionError
from .ports import (
    AdapterCapabilities,
    AdapterProgress,
    AdapterResult,
    CancellationToken,
    DeploymentCommand,
    DeploymentPreview,
    IntegrationHealth,
    ProgressSink,
)


class LocalFileDeploymentAdapter:
    """Atomically activates one verified artifact under a configured local root."""

    adapter_id = "adapter.local-release"
    adapter_version = "1.0.0"

    def __init__(
        self,
        artifact_root: Path,
        target_roots: Dict[DeploymentTarget, Path],
        clock: Optional[SystemUtcClock] = None,
    ) -> None:
        self._artifact_root = validated_root(artifact_root)
        self._target_roots = {
            target: validated_root(root) for target, root in target_roots.items()
        }
        self._clock = clock or SystemUtcClock()

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            targets=sorted(self._target_roots, key=lambda target: target.value),
            execution_mode=ExecutionMode.LIVE,
            supports_dry_run=True,
            supports_rollback=True,
        )

    def health_check(self) -> IntegrationHealth:
        roots = [self._artifact_root, *self._target_roots.values()]
        healthy = all(root.exists() and root.is_dir() and not root.is_symlink() for root in roots)
        return IntegrationHealth(
            healthy=healthy,
            code="READY" if healthy else "ROOT_UNAVAILABLE",
            message=(
                "Configured artifact and deployment roots are available."
                if healthy
                else "A configured artifact or deployment root is unavailable."
            ),
        )

    def dry_run(self, command: DeploymentCommand) -> DeploymentPreview:
        try:
            source = resolve_regular_file(self._artifact_root, command.artifact.uri)
            root = self._target_root(command.target)
            scope = self._scope_path(root, command)
            destination = scope / "releases" / command.candidate_id / source.name
            assert_no_symlink_chain(root, destination)
            return DeploymentPreview(
                target=command.target,
                destination=str(destination),
                artifact_id=command.artifact.artifact_id,
                source_checksum=command.artifact.checksum,
                would_activate=True,
                mode=ExecutionMode.LIVE,
            )
        except AdapterExecutionError:
            raise
        except ValueError as exc:
            raise self._invalid_path(command, exc) from exc
        except OSError as exc:
            raise self._io_failure(command, exc) from exc

    def execute(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        return self._activate(command, cancellation, progress, "deploy")

    def rollback(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
    ) -> AdapterResult:
        return self._activate(command, cancellation, progress, "rollback")

    def _activate(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
        action: str,
    ) -> AdapterResult:
        try:
            return self._activate_verified(command, cancellation, progress, action)
        except AdapterExecutionError:
            raise
        except ValueError as exc:
            raise self._invalid_path(command, exc) from exc
        except OSError as exc:
            raise self._io_failure(command, exc) from exc

    def _activate_verified(
        self,
        command: DeploymentCommand,
        cancellation: CancellationToken,
        progress: ProgressSink,
        action: str,
    ) -> AdapterResult:
        configured_root = self._target_root(command.target)
        root = ensure_contained_directory(
            configured_root,
            "targets",
            command.target.value,
            "projects",
            command.project_id,
            command.game_id,
            command.build_target_id,
        )
        existing = self._existing_result(root, command, action)
        if existing is not None:
            return existing
        source = resolve_regular_file(self._artifact_root, command.artifact.uri)
        if (
            file_sha256(source) != command.artifact.checksum
            or source.stat().st_size != command.artifact.size_bytes
        ):
            raise AdapterExecutionError(
                "Source artifact bytes or size changed before activation.",
                retryable=False,
                details={"artifact_id": command.artifact.artifact_id},
            )
        self._check_cancelled(cancellation, command.operation_id)
        progress(self._progress(command.operation_id, 1, "staging", 20, "正在暂存发布产物"))

        staging_dir = ensure_contained_directory(root, ".staging")
        release_dir = ensure_contained_directory(
            root, "releases", command.candidate_id
        )
        descriptor, staged_name = tempfile.mkstemp(
            prefix=f".{command.operation_id}.", suffix=".part", dir=staging_dir
        )
        staged = Path(staged_name)
        destination = release_dir / source.name
        assert_within(root, staged)
        assert_within(root, destination)
        try:
            staged_stream = os.fdopen(descriptor, "wb")
            descriptor = -1
            with staged_stream, source.open("rb") as source_stream:
                shutil.copyfileobj(source_stream, staged_stream)
                staged_stream.flush()
                os.fsync(staged_stream.fileno())
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            staged.unlink(missing_ok=True)
            raise
        try:
            staged_checksum = file_sha256(staged)
            if (
                staged_checksum != command.artifact.checksum
                or staged.stat().st_size != command.artifact.size_bytes
            ):
                raise AdapterExecutionError(
                    "Staged artifact failed checksum verification.",
                    retryable=True,
                    details={"operation_id": command.operation_id},
                )
            self._check_cancelled(cancellation, command.operation_id)
            progress(
                self._progress(
                    command.operation_id, 2, "verify", 70, "已校验暂存产物"
                )
            )
            assert_no_symlink_chain(root, release_dir)
            os.replace(staged, destination)
        finally:
            staged.unlink(missing_ok=True)
        self._activate_pointer(root, destination, command, action)
        progress(self._progress(command.operation_id, 3, "activate", 100, "发布目标已原子切换"))
        return AdapterResult(
            operation_id=command.operation_id,
            mode=ExecutionMode.LIVE,
            deployed_uri=str(destination),
            deployed_checksum=staged_checksum,
            logs=[
                f"{action}: verified artifact {command.artifact.artifact_id}",
                f"{action}: activated candidate {command.candidate_id}",
            ],
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
        )

    def _activate_pointer(
        self,
        root: Path,
        destination: Path,
        command: DeploymentCommand,
        action: str,
    ) -> None:
        pointer = self._operation_record(root, destination, command, action)
        receipt_dir = ensure_contained_directory(root, "receipts")
        atomic_write_json(root, "active.json", pointer)
        atomic_write_json(
            receipt_dir, f"{command.operation_id}.json", pointer
        )

    @staticmethod
    def _operation_record(
        root: Path,
        destination: Path,
        command: DeploymentCommand,
        action: str,
    ) -> Dict[str, Any]:
        return {
            "operation_id": command.operation_id,
            "candidate_id": command.candidate_id,
            "project_id": command.project_id,
            "game_id": command.game_id,
            "build_target_id": command.build_target_id,
            "target": command.target.value,
            "artifact_id": command.artifact.artifact_id,
            "checksum": command.artifact.checksum,
            "size_bytes": command.artifact.size_bytes,
            "idempotency_key": command.idempotency_key,
            "uri": str(destination.relative_to(root)),
            "action": action,
        }

    def _existing_result(
        self, root: Path, command: DeploymentCommand, action: str
    ) -> Optional[AdapterResult]:
        locations = (
            f"receipts/{command.operation_id}.json",
            "active.json",
        )
        for relative_uri in locations:
            path = root / relative_uri
            if not path.exists() and not path.is_symlink():
                continue
            record = self._read_record(root, relative_uri)
            if (
                relative_uri == "active.json"
                and record.get("operation_id") != command.operation_id
            ):
                continue
            self._validate_record(record, command, action)
            destination_uri = record.get("uri")
            if not isinstance(destination_uri, str):
                raise AdapterExecutionError(
                    "Activation receipt has no valid destination URI.",
                    retryable=False,
                    details={"operation_id": command.operation_id},
                )
            destination = resolve_regular_file(root, destination_uri)
            observed = file_sha256(destination)
            if observed != command.artifact.checksum:
                raise AdapterExecutionError(
                    "Previously activated artifact no longer matches its receipt.",
                    retryable=False,
                    details={"operation_id": command.operation_id},
                )
            return AdapterResult(
                operation_id=command.operation_id,
                mode=ExecutionMode.LIVE,
                deployed_uri=str(destination),
                deployed_checksum=observed,
                logs=["idempotency: reconciled previously activated operation"],
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
            )
        return None

    @staticmethod
    def _read_record(root: Path, relative_uri: str) -> Mapping[str, Any]:
        path = resolve_regular_file(root, relative_uri)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("activation receipt must contain a JSON object")
        return payload

    @staticmethod
    def _validate_record(
        record: Mapping[str, Any],
        command: DeploymentCommand,
        action: str,
    ) -> None:
        expected = {
            "operation_id": command.operation_id,
            "candidate_id": command.candidate_id,
            "project_id": command.project_id,
            "game_id": command.game_id,
            "build_target_id": command.build_target_id,
            "target": command.target.value,
            "artifact_id": command.artifact.artifact_id,
            "checksum": command.artifact.checksum,
            "size_bytes": command.artifact.size_bytes,
            "idempotency_key": command.idempotency_key,
            "action": action,
        }
        if any(record.get(key) != value for key, value in expected.items()):
            raise AdapterExecutionError(
                "Operation ID was already activated with different immutable inputs.",
                retryable=False,
                details={"operation_id": command.operation_id},
            )

    def _target_root(self, target: DeploymentTarget) -> Path:
        try:
            return self._target_roots[target]
        except KeyError as exc:
            raise AdapterExecutionError(
                "Deployment target is not configured.",
                retryable=False,
                details={"target": target.value},
            ) from exc

    @staticmethod
    def _scope_path(root: Path, command: DeploymentCommand) -> Path:
        return (
            root
            / "targets"
            / command.target.value
            / "projects"
            / command.project_id
            / command.game_id
            / command.build_target_id
        )

    @staticmethod
    def _invalid_path(
        command: DeploymentCommand, error: ValueError
    ) -> AdapterExecutionError:
        return AdapterExecutionError(
            "Deployment path or receipt validation failed.",
            retryable=False,
            details={"operation_id": command.operation_id, "reason": str(error)},
        )

    @staticmethod
    def _io_failure(
        command: DeploymentCommand, error: OSError
    ) -> AdapterExecutionError:
        return AdapterExecutionError(
            "Deployment storage operation failed.",
            retryable=True,
            details={"operation_id": command.operation_id, "reason": str(error)},
        )

    def _progress(
        self, operation_id: str, sequence: int, phase: str, percent: int, message: str
    ) -> AdapterProgress:
        return AdapterProgress(
            operation_id=operation_id,
            sequence=sequence,
            phase=phase,
            percent=percent,
            message=message,
            occurred_at=self._clock.now(),
        )

    @staticmethod
    def _check_cancelled(cancellation: CancellationToken, operation_id: str) -> None:
        if cancellation.cancelled:
            raise AdapterExecutionError(
                "Deployment was cancelled before activation.",
                retryable=True,
                details={"operation_id": operation_id},
            )
