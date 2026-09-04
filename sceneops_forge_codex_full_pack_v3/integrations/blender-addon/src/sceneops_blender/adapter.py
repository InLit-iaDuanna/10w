from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .artifacts import artifact_sha256, read_glb_json
from .contracts import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    BlenderResult,
    CapabilityReport,
    ChangePreview,
    ExecutionMode,
    IntegrationHealth,
    PERSISTENT_SCENE_MUTATIONS,
)
from .identity import extract_sceneops_ids
from .path_policy import ProjectPathPolicy
from .support import capabilities, preview, utc_now
from .transport import BlenderProcessTransport, SubprocessBlenderTransport


ProgressCallback = Callable[[float, str], None]
CancellationCheck = Callable[[], bool]


class LiveBlenderAdapter:
    mode = ExecutionMode.LIVE

    def __init__(
        self,
        project_root: Path,
        executable: Optional[Path] = None,
        transport: Optional[BlenderProcessTransport] = None,
        operation_state_root: Optional[Path] = None,
        discover_executable: bool = False,
    ) -> None:
        self.paths = ProjectPathPolicy(project_root)
        self.project_root = self.paths.project_root
        discovered = executable
        if discovered is None and discover_executable:
            discovered = Path(found) if (found := shutil.which("blender")) else None
        self.executable = self._validated_executable(discovered)
        self.transport = transport or SubprocessBlenderTransport()
        self.operation_state_root = self._validated_state_root(operation_state_root)
        default_bridge = Path(__file__).resolve().parents[2] / "scripts" / "typed_bridge.py"
        self.bridge_path = default_bridge.resolve(strict=True)

    def _validated_state_root(self, value: Optional[Path]) -> Optional[Path]:
        if value is None:
            return None
        resolved = value.expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise BlenderAdapterError(
                "OPERATION_STATE_INVALID", "operation state root must be a directory"
            )
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            return resolved
        raise BlenderAdapterError(
            "OPERATION_STATE_INVALID", "operation state must be outside project content"
        )

    @staticmethod
    def _validated_executable(executable: Optional[Path]) -> Optional[Path]:
        if executable is None:
            return None
        resolved = executable.expanduser().resolve(strict=True)
        if not resolved.is_file() or not os.access(str(resolved), os.X_OK):
            raise BlenderAdapterError("BLENDER_EXECUTABLE_INVALID", "Blender executable is not runnable")
        if resolved.name.casefold() not in {"blender", "blender.exe"}:
            raise BlenderAdapterError("BLENDER_EXECUTABLE_INVALID", "executable name must identify Blender")
        return resolved

    def health_check(self, timeout_seconds: float = 5) -> IntegrationHealth:
        if self.executable is None:
            return IntegrationHealth(
                healthy=False,
                mode=ExecutionMode.BLOCKED,
                code="BLENDER_NOT_FOUND",
                message="Blender executable is not configured or on PATH.",
                checked_at=utc_now(),
            )
        try:
            version = self.transport.health(self.executable, timeout_seconds)
        except BlenderAdapterError as error:
            return IntegrationHealth(
                healthy=False,
                mode=ExecutionMode.BLOCKED,
                code=error.code,
                message=str(error),
                checked_at=utc_now(),
            )
        return IntegrationHealth(
            healthy=True,
            mode=ExecutionMode.LIVE,
            version=version,
            code="BLENDER_OK",
            message="Blender responded to a live health check.",
            checked_at=utc_now(),
        )

    def capabilities(self) -> CapabilityReport:
        return capabilities()

    def dry_run(self, command: BlenderCommand) -> ChangePreview:
        if not command.dry_run:
            raise BlenderAdapterError("DRY_RUN_REQUIRED", "preview command must set dry_run=true")
        self._validate_paths(command)
        return preview(command)

    def execute(
        self,
        command: BlenderCommand,
        timeout_seconds: float,
        is_cancelled: CancellationCheck = lambda: False,
        on_progress: ProgressCallback = lambda _progress, _message: None,
    ) -> BlenderResult:
        if command.dry_run:
            raise BlenderAdapterError("DRY_RUN_EXECUTION_FORBIDDEN", "dry-run command cannot execute")
        self._validate_paths(command)
        if command.source_path and not getattr(self.transport, "filesystem_isolated", False):
            raise BlenderAdapterError(
                "BLENDER_SANDBOX_REQUIRED",
                "Opening project Blender files requires a filesystem-isolated worker.",
            )
        if command.operation in PERSISTENT_SCENE_MUTATIONS and self.operation_state_root is None:
            raise BlenderAdapterError(
                "OPERATION_STATE_UNAVAILABLE",
                "Live mutation requires server-owned operation state storage.",
            )
        health = self.health_check(min(timeout_seconds, 5))
        if not health.healthy or self.executable is None:
            raise BlenderAdapterError(health.code, health.message, retryable=True)
        on_progress(0.05, "Blender command accepted")
        raw = self.transport.execute(
            self.executable,
            self.bridge_path,
            json.dumps(self._bridge_payload(command), sort_keys=True, separators=(",", ":")),
            timeout_seconds,
            is_cancelled,
        )
        raw.update(
            request_id=command.request_id,
            operation=command.operation.value,
            mode=ExecutionMode.LIVE.value,
        )
        if command.operation == BlenderOperation.EXPORT_ASSET and raw.get("succeeded"):
            raw_data = raw.setdefault("data", {})
            if isinstance(raw_data, dict):
                raw_data["artifacts"] = self._live_artifacts(command, raw_data)
        result = BlenderResult.model_validate(raw)
        if not result.succeeded:
            raise BlenderAdapterError(
                result.error_code or "BLENDER_COMMAND_FAILED",
                result.error_message or "Blender command failed",
                result.retryable,
            )
        on_progress(1.0, "Blender command completed")
        return result

    def _validate_paths(self, command: BlenderCommand) -> None:
        if command.source_path:
            self.paths.resolve(command.source_path, must_exist=True)
        self.paths.validate_all(command.output_paths)
        if command.operation in PERSISTENT_SCENE_MUTATIONS and not command.dry_run:
            self.paths.require_asset_factory_working_copy(command.source_path or "", must_exist=True)
        if command.operation == BlenderOperation.SAVE_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.output_paths[0])
            self.paths.require_asset_factory_working_copy(command.output_paths[1])
        if command.operation == BlenderOperation.ROLLBACK_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.source_path or "")
            self.paths.require_asset_factory_working_copy(command.output_paths[0])

    def _bridge_payload(self, command: BlenderCommand) -> Dict[str, object]:
        payload = command.model_dump(mode="json")
        payload["project_root"] = str(self.paths.project_root)
        if command.source_path:
            payload["source_path"] = str(self.paths.resolve(command.source_path, must_exist=True))
        payload["output_paths"] = [str(self.paths.resolve(value)) for value in command.output_paths]
        if command.operation in PERSISTENT_SCENE_MUTATIONS:
            payload["operation_state_directory"] = str(self.operation_state_root)
        return payload

    def _live_artifacts(
        self, command: BlenderCommand, raw_data: Dict[str, object]
    ) -> List[Dict[str, object]]:
        expected_ids = set(raw_data.get("sceneops_ids", []))
        artifacts: List[Dict[str, object]] = []
        for relative_path in command.output_paths:
            path = self.paths.resolve(relative_path, must_exist=True)
            format_name = path.suffix.casefold().lstrip(".")
            if format_name == "glb":
                exported_ids = set(extract_sceneops_ids(read_glb_json(path)))
                if exported_ids != expected_ids:
                    raise BlenderAdapterError(
                        "IDENTITY_EXPORT_MISMATCH",
                        "GLB extras do not match the Blender export identity manifest",
                    )
            artifacts.append(self._artifact_record(path, format_name))
        return artifacts

    def _artifact_record(self, path: Path, format_name: str) -> Dict[str, object]:
        return {
            "artifact_id": "art_%s_%s" % (path.stem.replace("-", "_"), format_name),
            "format": format_name,
            "project_relative_path": path.relative_to(self.paths.project_root).as_posix(),
            "media_type": "model/gltf-binary" if format_name == "glb" else "application/octet-stream",
            "byte_size": path.stat().st_size,
            "sha256": artifact_sha256(path),
        }
