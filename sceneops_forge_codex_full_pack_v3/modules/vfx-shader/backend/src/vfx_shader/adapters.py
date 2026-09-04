"""Public adapter protocol boundaries; no vendor SDK types cross this file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from .models import ExecutionMode


@dataclass(frozen=True)
class IntegrationHealth:
    integration_id: str
    online: bool
    message: str


@dataclass(frozen=True)
class AdapterCapabilities:
    integration_id: str
    commands: frozenset[str]
    adapter_version: str


@dataclass(frozen=True)
class AdapterCommand:
    command: str
    project_id: str
    target_sceneops_ids: tuple[str, ...]
    recipe_id: str
    recipe_version: str
    change_set_id: Optional[str]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    code: str
    message: str
    execution_mode: ExecutionMode
    result_id: Optional[str] = None
    artifact_id: Optional[str] = None
    checksum_sha256: Optional[str] = None
    occurred_at: Optional[str] = None
    project_id: Optional[str] = None
    target_sceneops_ids: tuple[str, ...] = ()
    recipe_id: Optional[str] = None
    recipe_version: Optional[str] = None


class UnityVfxAdapter(Protocol):
    def health_check(self) -> IntegrationHealth: ...
    def capabilities(self) -> AdapterCapabilities: ...
    def dry_run(self, command: AdapterCommand) -> AdapterResult: ...
    def publish(self, command: AdapterCommand) -> AdapterResult: ...


class RenderPreviewAdapter(Protocol):
    def health_check(self) -> IntegrationHealth: ...
    def capabilities(self) -> AdapterCapabilities: ...
    def dry_run(self, command: AdapterCommand) -> AdapterResult: ...
    def render(self, command: AdapterCommand) -> AdapterResult: ...


class DeterministicMockUnityAdapter:
    """Test adapter. It can never return live or cached results."""

    def __init__(self, *, online: bool = True, fail_publish: bool = False) -> None:
        self.online = online
        self.fail_publish = fail_publish
        self.commands: list[AdapterCommand] = []

    def health_check(self) -> IntegrationHealth:
        return IntegrationHealth("unity", self.online, "mock online" if self.online else "mock offline")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            "unity",
            frozenset({"publish_vfx_recipe", "set_vfx_enabled"}),
            "mock-unity-v1",
        )

    def dry_run(self, command: AdapterCommand) -> AdapterResult:
        if not self.online:
            return AdapterResult(False, "INTEGRATION_OFFLINE", "mock Unity offline", ExecutionMode.BLOCKED)
        if command.command not in self.capabilities().commands:
            return AdapterResult(False, "CAPABILITY_MISSING", "unsupported command", ExecutionMode.BLOCKED)
        return AdapterResult(True, "DRY_RUN_OK", "mock dry-run passed", ExecutionMode.MOCK, "mock_dryrun_001")

    def publish(self, command: AdapterCommand) -> AdapterResult:
        self.commands.append(command)
        if self.fail_publish:
            return AdapterResult(False, "UNITY_PUBLISH_FAILED", "mock publish failure", ExecutionMode.MOCK)
        return AdapterResult(
            ok=True,
            code="PUBLISHED",
            message="mock publish succeeded",
            execution_mode=ExecutionMode.MOCK,
            result_id="mock_unity_publish_001",
            artifact_id="artifact_mock_unity_vfx_publish_001",
            checksum_sha256="3333333333333333333333333333333333333333333333333333333333333333",
            occurred_at="2026-09-04T00:06:00Z",
            project_id=command.project_id,
            target_sceneops_ids=command.target_sceneops_ids,
            recipe_id=command.recipe_id,
            recipe_version=command.recipe_version,
        )


class DeterministicMockRenderAdapter:
    """Deterministic preview adapter with observable call counts for tests."""

    def __init__(self, *, online: bool = True, fail_render: bool = False) -> None:
        self.online = online
        self.fail_render = fail_render
        self.dry_run_calls = 0
        self.render_calls = 0

    def health_check(self) -> IntegrationHealth:
        return IntegrationHealth("render", self.online, "mock online" if self.online else "mock offline")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities("render", frozenset({"render_vfx_preview"}), "mock-render-v1")

    def dry_run(self, command: AdapterCommand) -> AdapterResult:
        self.dry_run_calls += 1
        return AdapterResult(True, "DRY_RUN_OK", "mock render dry-run passed", ExecutionMode.MOCK, "mock_render_dryrun_001")

    def render(self, command: AdapterCommand) -> AdapterResult:
        self.render_calls += 1
        if self.fail_render:
            return AdapterResult(False, "RENDER_FAILED", "mock render failure", ExecutionMode.MOCK)
        return AdapterResult(
            ok=True,
            code="RENDERED",
            message="mock render succeeded",
            execution_mode=ExecutionMode.MOCK,
            result_id="mock_render_001",
            artifact_id="artifact_mock_render_vfx_preview_001",
            checksum_sha256="4444444444444444444444444444444444444444444444444444444444444444",
            occurred_at="2026-09-04T00:07:00Z",
            project_id=command.project_id,
            target_sceneops_ids=command.target_sceneops_ids,
            recipe_id=command.recipe_id,
            recipe_version=command.recipe_version,
        )
