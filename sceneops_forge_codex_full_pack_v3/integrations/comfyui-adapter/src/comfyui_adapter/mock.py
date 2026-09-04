"""Deterministic mock path; never presented as live or cached-real."""

from typing import Dict, Tuple

from .errors import ComfyAdapterError
from .models import (
    ComfyCapabilities,
    ComfyEnqueueCommand,
    HealthState,
    IntegrationHealth,
    MockEnqueueResult,
    MockOutput,
    MockProgressEvent,
    PromptState,
)
from .workflows import ArtifactInputResolver, TrustedWorkflowRegistry


class DeterministicMockComfyAdapter:
    def __init__(
        self,
        *,
        workflows: TrustedWorkflowRegistry,
        artifact_resolver: ArtifactInputResolver,
        output_checksum_sha256: str,
    ) -> None:
        self._workflows = workflows
        self._artifact_resolver = artifact_resolver
        self._checksum = output_checksum_sha256
        self._requests: Dict[str, Tuple[dict, MockEnqueueResult]] = {}
        self._states: Dict[str, PromptState] = {}

    def health_check(self) -> IntegrationHealth:
        return IntegrationHealth(
            state=HealthState.ONLINE,
            endpoint="mock://deterministic-comfyui",
            adapter_version="0.1.0",
            execution_mode="mock",
        )

    def capabilities(self) -> ComfyCapabilities:
        return ComfyCapabilities(
            adapter_version="0.1.0",
            trusted_workflow_references=list(self._workflows.references),
            execution_mode="mock",
            durable_enqueue_idempotency=False,
        )

    def enqueue(self, command: ComfyEnqueueCommand) -> MockEnqueueResult:
        command = ComfyEnqueueCommand.model_validate(command.model_dump(mode="python"))
        if command.execution_mode != "mock":
            raise ComfyAdapterError(
                "EXECUTION_MODE_MISMATCH",
                "The deterministic mock adapter accepts only mock commands.",
                retryable=False,
            )
        payload = command.model_dump(mode="json")
        prior = self._requests.get(command.request_id)
        if prior:
            if prior[0] != payload:
                raise ComfyAdapterError(
                    "IDEMPOTENCY_CONFLICT",
                    "The mock request ID was reused for different inputs.",
                    retryable=False,
                )
            data = prior[1].model_dump(mode="python")
            data["reused_request"] = True
            return MockEnqueueResult.model_validate(data)

        self._workflows.bind(command, self._artifact_resolver)
        prompt_id = "mock-prompt:" + command.request_id
        result = MockEnqueueResult(
            request_id=command.request_id,
            render_job_id=command.render_job_id,
            prompt_id=prompt_id,
            workflow_reference=command.workflow_reference,
            workflow_checksum_sha256=command.workflow_checksum_sha256,
        )
        self._requests[command.request_id] = (payload, result)
        self._states[prompt_id] = PromptState.QUEUED
        return result

    def progress(self, prompt_id: str) -> MockProgressEvent:
        try:
            state = self._states[prompt_id]
        except KeyError as exc:
            raise ComfyAdapterError(
                "PROMPT_NOT_OWNED",
                "Unknown deterministic mock prompt.",
                retryable=False,
            ) from exc
        if state in {PromptState.SUCCEEDED, PromptState.CANCELLED}:
            return MockProgressEvent(
                prompt_id=prompt_id,
                state=state,
                progress=1.0 if state == PromptState.SUCCEEDED else 0.0,
                message="Deterministic mock prompt is in a terminal state.",
            )
        next_state = (
            PromptState.RUNNING if state == PromptState.QUEUED else PromptState.SUCCEEDED
        )
        self._states[prompt_id] = next_state
        return MockProgressEvent(
            prompt_id=prompt_id,
            state=next_state,
            progress=1.0 if next_state == PromptState.SUCCEEDED else 0.0,
            message="Deterministic mock progress.",
        )

    def output(self, prompt_id: str) -> MockOutput:
        if self._states.get(prompt_id) != PromptState.SUCCEEDED:
            raise ComfyAdapterError(
                "OUTPUT_NOT_READY",
                "Deterministic mock output is not ready.",
                retryable=True,
            )
        return MockOutput(
            prompt_id=prompt_id,
            artifact_id="artifact:" + prompt_id,
            checksum_sha256=self._checksum,
        )

    def cancel(self, prompt_id: str) -> MockProgressEvent:
        state = self._states.get(prompt_id)
        if state not in {PromptState.QUEUED, PromptState.RUNNING}:
            raise ComfyAdapterError(
                "CANCEL_NOT_ALLOWED",
                "Only queued or running deterministic mock prompts can be cancelled.",
                retryable=False,
            )
        self._states[prompt_id] = PromptState.CANCELLED
        return MockProgressEvent(
            prompt_id=prompt_id,
            state=PromptState.CANCELLED,
            progress=0.0,
            message="Deterministic mock prompt cancelled.",
        )
