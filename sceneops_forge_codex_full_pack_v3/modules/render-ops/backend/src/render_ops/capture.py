"""Typed AOV capture worker boundary for Blender or Unity render adapters."""

from threading import Event
from typing import Callable, List, Protocol

from pydantic import Field

from .cache import validate_aov_artifacts
from .schemas import (
    AovArtifact,
    AovPass,
    ExecutionMode,
    RenderCaptureCommand,
    RenderRecipe,
    StrictModel,
)


class CaptureCapabilities(StrictModel):
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    command_ids: List[str] = Field(min_length=1)
    supported_passes: List[AovPass] = Field(min_length=1)
    supports_dry_run: bool
    supports_cancellation: bool
    execution_mode: ExecutionMode


class CapturePreview(StrictModel):
    render_job_id: str
    accepted: bool
    pass_count: int = Field(ge=0)
    estimated_output_count: int = Field(ge=0)
    execution_mode: ExecutionMode
    reason: str = ""


class CaptureResult(StrictModel):
    render_job_id: str
    aovs: List[AovArtifact]
    adapter_id: str
    adapter_version: str
    execution_mode: ExecutionMode


class CaptureCancellation:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class RenderCaptureAdapter(Protocol):
    def capabilities(self) -> CaptureCapabilities:
        ...

    def dry_run(self, command: RenderCaptureCommand) -> CapturePreview:
        ...

    def execute(
        self,
        command: RenderCaptureCommand,
        cancellation: CaptureCancellation,
        on_progress: Callable[[float, str], None],
    ) -> CaptureResult:
        ...


class AovCaptureWorker:
    def run(
        self,
        *,
        command: RenderCaptureCommand,
        recipe: RenderRecipe,
        adapter: RenderCaptureAdapter,
        cancellation: CaptureCancellation,
        on_progress: Callable[[float, str], None],
    ) -> CaptureResult:
        capabilities = adapter.capabilities()
        if command.command_id not in capabilities.command_ids:
            raise PermissionError("capture command is not allowlisted by adapter")
        unsupported = set(command.passes) - set(capabilities.supported_passes)
        if unsupported:
            labels = ", ".join(sorted(item.value for item in unsupported))
            raise ValueError("adapter does not support AOV passes: " + labels)
        if not capabilities.supports_dry_run or not capabilities.supports_cancellation:
            raise PermissionError("capture adapter must support dry-run and cancellation")
        if capabilities.execution_mode.value != command.execution_mode:
            raise ValueError("capture command mode does not match adapter mode")
        if cancellation.cancelled:
            raise RuntimeError("capture cancelled before dry-run")

        preview = adapter.dry_run(command)
        if not preview.accepted:
            raise PermissionError(preview.reason or "capture dry-run rejected")
        if preview.render_job_id != command.render_job_id:
            raise ValueError("capture dry-run returned the wrong render job ID")
        if preview.execution_mode.value != command.execution_mode:
            raise ValueError("capture dry-run mode does not match command mode")
        result = adapter.execute(command, cancellation, on_progress)
        if cancellation.cancelled:
            raise RuntimeError("capture adapter returned output after cancellation")
        if result.render_job_id != command.render_job_id:
            raise ValueError("capture adapter returned the wrong render job ID")
        if (result.adapter_id, result.adapter_version) != (
            capabilities.adapter_id,
            capabilities.adapter_version,
        ):
            raise ValueError("capture result adapter identity is inconsistent")
        if result.execution_mode.value != command.execution_mode:
            raise ValueError("capture result mode does not match command mode")
        for aov in result.aovs:
            if aov.artifact.execution_mode != result.execution_mode:
                raise ValueError("captured AOV mode does not match capture result mode")
            if (
                aov.artifact.source_project_id != command.scene.project_id
                or aov.artifact.source_version != command.scene.scene_version
            ):
                raise ValueError("captured AOV provenance does not match scene version")

        if not set(command.passes).issubset(set(recipe.required_passes + recipe.optional_passes)):
            raise ValueError("capture command contains a pass outside the selected recipe")
        validate_aov_artifacts(
            command.passes,
            command.scene,
            command.width,
            command.height,
            result.aovs,
            execution_mode=result.execution_mode,
        )
        return result
