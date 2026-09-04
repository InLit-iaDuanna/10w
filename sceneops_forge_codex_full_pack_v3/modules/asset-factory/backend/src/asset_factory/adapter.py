from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from sceneops_blender import (
    BlenderCommand,
    BlenderResult,
    CapabilityReport,
    ChangePreview,
    IntegrationHealth,
)


class BlenderAdapterPort(Protocol):
    mode: object
    project_root: Path

    def health_check(self, timeout_seconds: float = 5) -> IntegrationHealth: ...

    def capabilities(self) -> CapabilityReport: ...

    def dry_run(self, command: BlenderCommand) -> ChangePreview: ...

    def execute(
        self,
        command: BlenderCommand,
        timeout_seconds: float,
        is_cancelled: Callable[[], bool] = lambda: False,
        on_progress: Callable[[float, str], None] = lambda _progress, _message: None,
    ) -> BlenderResult: ...
