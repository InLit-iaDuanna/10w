from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Protocol

from .models import (
    AdapterHealth,
    AdapterProvenance,
    ApplyReceipt,
    ChangePreview,
    CodeChangeSet,
    CompileTestResult,
    ExecutionMode,
    RollbackResult,
    UnityCodeCapability,
)


class UnityAdapterError(RuntimeError):
    pass


class UnityAdapterCancelled(UnityAdapterError):
    pass


@dataclass(frozen=True)
class AdapterProgress:
    stage: str
    completed: int
    total: int
    message: str


@dataclass(frozen=True)
class AdapterExecutionContext:
    request_id: str
    correlation_id: str
    timeout_seconds: int
    max_attempts: int
    is_cancelled: Callable[[], bool]
    report_progress: Callable[[AdapterProgress], None]


class UnityCodeChangeAdapter(Protocol):
    def health_check(self) -> AdapterHealth:
        ...

    def capabilities(self) -> UnityCodeCapability:
        ...

    def dry_run(
        self, change_set: CodeChangeSet, context: AdapterExecutionContext
    ) -> ChangePreview:
        ...

    def apply(
        self, change_set: CodeChangeSet, context: AdapterExecutionContext
    ) -> ApplyReceipt:
        ...

    def compile_and_test(
        self, receipt: ApplyReceipt, context: AdapterExecutionContext
    ) -> CompileTestResult:
        ...

    def rollback(
        self, rollback_token: str, context: AdapterExecutionContext
    ) -> RollbackResult:
        ...


class DeterministicMockUnityCodeChangeAdapter:
    """In-memory contract fixture. It never reads, writes, or executes project code."""

    def __init__(
        self,
        *,
        online: bool = True,
        dry_run_accepted: bool = True,
        compile_succeeded: bool = True,
        edit_mode_succeeded: bool = True,
        play_mode_succeeded: bool = True,
        rollback_succeeded: bool = True,
    ) -> None:
        self.online = online
        self.dry_run_accepted = dry_run_accepted
        self.compile_succeeded = compile_succeeded
        self.edit_mode_succeeded = edit_mode_succeeded
        self.play_mode_succeeded = play_mode_succeeded
        self.rollback_succeeded = rollback_succeeded
        self.calls: List[str] = []
        self.active_rollback_tokens: set[str] = set()

    def health_check(self) -> AdapterHealth:
        self.calls.append("health_check")
        return AdapterHealth(
            adapter_id="unity-code-change-mock",
            adapter_version="1.0.0",
            status="online" if self.online else "offline",
            reason=None if self.online else "Deterministic offline fixture.",
            mode=ExecutionMode.MOCK,
        )

    def capabilities(self) -> UnityCodeCapability:
        self.calls.append("capabilities")
        return UnityCodeCapability(
            adapter_id="unity-code-change-mock",
            adapter_version="1.0.0",
            allowed_commands=[
                "unity.code_change.dry_run",
                "unity.code_change.apply",
                "unity.compile_and_test",
                "unity.code_change.rollback",
            ],
            allowed_project_roots=["fixture://unity-project"],
            timeout_seconds=30,
            max_attempts=1,
            supports_cancellation=True,
            supports_progress=True,
            supports_rollback=True,
            mode=ExecutionMode.MOCK,
        )

    def dry_run(
        self, change_set: CodeChangeSet, context: AdapterExecutionContext
    ) -> ChangePreview:
        self._before_call("dry_run", context)
        return ChangePreview(
            accepted=self.dry_run_accepted,
            impacted_paths=list(change_set.target_paths),
            summary="Deterministic diff preview; no project files were touched.",
            rejection_code=None if self.dry_run_accepted else "MOCK_DRY_RUN_REJECTED",
            mode=ExecutionMode.MOCK,
            provenance=self._provenance("unity.code_change.dry_run", context),
        )

    def apply(
        self, change_set: CodeChangeSet, context: AdapterExecutionContext
    ) -> ApplyReceipt:
        self._before_call("apply", context)
        rollback_token = f"rollback_{change_set.change_set_id}"
        self.active_rollback_tokens.add(rollback_token)
        return ApplyReceipt(
            receipt_id=f"receipt_{change_set.change_set_id}",
            rollback_token=rollback_token,
            logs=["Mock adapter recorded an in-memory apply receipt."],
            mode=ExecutionMode.MOCK,
            provenance=self._provenance("unity.code_change.apply", context),
        )

    def compile_and_test(
        self, receipt: ApplyReceipt, context: AdapterExecutionContext
    ) -> CompileTestResult:
        self._before_call("compile_and_test", context)
        return CompileTestResult(
            compile_succeeded=self.compile_succeeded,
            edit_mode_succeeded=self.edit_mode_succeeded,
            play_mode_succeeded=self.play_mode_succeeded,
            logs=[f"Mock validation for {receipt.receipt_id}."],
            mode=ExecutionMode.MOCK,
            provenance=self._provenance("unity.compile_and_test", context),
        )

    def rollback(
        self, rollback_token: str, context: AdapterExecutionContext
    ) -> RollbackResult:
        self._before_call("rollback", context)
        known = rollback_token in self.active_rollback_tokens
        succeeded = known and self.rollback_succeeded
        if succeeded:
            self.active_rollback_tokens.remove(rollback_token)
        return RollbackResult(
            succeeded=succeeded,
            logs=["Mock rollback completed." if succeeded else "Mock rollback failed."],
            mode=ExecutionMode.MOCK,
            provenance=self._provenance("unity.code_change.rollback", context),
        )

    def _before_call(
        self, name: str, context: AdapterExecutionContext
    ) -> None:
        if context.is_cancelled():
            raise UnityAdapterCancelled(f"Adapter call '{name}' was cancelled.")
        self.calls.append(name)
        context.report_progress(
            AdapterProgress(stage=name, completed=1, total=1, message="mock")
        )

    def _provenance(
        self, command: str, context: AdapterExecutionContext
    ) -> AdapterProvenance:
        return AdapterProvenance(
            adapter_id="unity-code-change-mock",
            adapter_version="1.0.0",
            command=command,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            mode=ExecutionMode.MOCK,
        )
