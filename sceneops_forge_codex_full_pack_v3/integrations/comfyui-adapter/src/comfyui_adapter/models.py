"""Public typed contracts for the ComfyUI adapter."""

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class PromptState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetryPolicy(StrictModel):
    max_attempts: int = Field(default=3, ge=1, le=5)
    request_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    backoff_seconds: float = Field(default=0.05, ge=0.0, le=5.0)


class IntegrationHealth(StrictModel):
    state: HealthState
    endpoint: str
    adapter_version: str
    execution_mode: Literal["live", "mock"] = "live"
    error_code: Optional[str] = None
    message: Optional[str] = None


class ComfyCapabilities(StrictModel):
    adapter_version: str
    api_family: Literal["comfyui-http"] = "comfyui-http"
    supports_enqueue: bool = True
    supports_progress: bool = True
    supports_cancel: bool = True
    supports_output_retrieval: bool = True
    queued_cancel_scope: Literal["prompt"] = "prompt"
    running_cancel_scope: Literal["disabled", "global"] = "disabled"
    accepts_arbitrary_workflow: Literal[False] = False
    accepts_filesystem_paths: Literal[False] = False
    trusted_workflow_references: List[str]
    execution_mode: Literal["live", "mock"] = "live"
    durable_enqueue_idempotency: bool


class WorkflowBinding(StrictModel):
    source: str = Field(
        pattern=r"^(prompt|negative_prompt|seed|model_reference|aov\.(beauty|depth|normal|albedo|object_id|material_id))$"
    )
    node_id: str = Field(min_length=1)
    input_name: str = Field(min_length=1)


class TrustedWorkflow(StrictModel):
    reference: str = Field(min_length=1)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph: Dict[str, dict]
    bindings: List[WorkflowBinding]
    allowed_model_references: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def bindings_target_existing_inputs(self) -> "TrustedWorkflow":
        seen = set()
        for binding in self.bindings:
            key = (binding.node_id, binding.input_name)
            if key in seen:
                raise ValueError("workflow bindings must be unique")
            seen.add(key)
            try:
                inputs = self.graph[binding.node_id]["inputs"]
            except (KeyError, TypeError) as exc:
                raise ValueError("binding node must contain an inputs object") from exc
            if binding.input_name not in inputs:
                raise ValueError("binding input must already exist in trusted graph")
        return self


class ComfyEnqueueCommand(StrictModel):
    request_id: str = Field(min_length=1)
    render_job_id: str = Field(min_length=1)
    workflow_reference: str = Field(min_length=1)
    workflow_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_reference: str = Field(min_length=1)
    seed: int = Field(ge=0)
    prompt: str = Field(min_length=1, max_length=8000)
    negative_prompt: str = Field(default="", max_length=8000)
    aov_artifact_ids: Dict[str, str] = Field(default_factory=dict)
    execution_mode: Literal["live", "mock"] = "live"

    @model_validator(mode="after")
    def aov_keys(self) -> "ComfyEnqueueCommand":
        allowed = {"beauty", "depth", "normal", "albedo", "object_id", "material_id"}
        if not set(self.aov_artifact_ids).issubset(allowed):
            raise ValueError("unknown AOV input key")
        if any(not value for value in self.aov_artifact_ids.values()):
            raise ValueError("AOV artifact IDs cannot be empty")
        return self


class EnqueueResult(StrictModel):
    request_id: str
    render_job_id: str
    prompt_id: str
    workflow_reference: str
    workflow_checksum_sha256: str
    adapter_version: str
    execution_mode: Literal["live"] = "live"
    reused_request: bool = False


class ProgressEvent(StrictModel):
    prompt_id: str
    state: PromptState
    progress: float = Field(ge=0.0, le=1.0)
    message: str
    execution_mode: Literal["live"] = "live"


class OutputDescriptor(StrictModel):
    prompt_id: str
    node_id: str
    filename: str = Field(min_length=1)
    subfolder: str = ""
    output_type: Literal["output", "temp"] = "output"


class RetrievedOutput(StrictModel):
    descriptor: OutputDescriptor
    content_type: str
    byte_count: int = Field(ge=0)
    execution_mode: Literal["live"] = "live"


class MockOutput(StrictModel):
    prompt_id: str
    artifact_id: str
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_mode: Literal["mock"] = "mock"


class MockEnqueueResult(StrictModel):
    request_id: str
    render_job_id: str
    prompt_id: str
    workflow_reference: str
    workflow_checksum_sha256: str
    execution_mode: Literal["mock"] = "mock"
    reused_request: bool = False


class MockProgressEvent(StrictModel):
    prompt_id: str
    state: PromptState
    progress: float = Field(ge=0.0, le=1.0)
    message: str
    execution_mode: Literal["mock"] = "mock"
