"""Production HTTP adapter with injected transport and trusted workflows."""

import time
from threading import Event
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlparse

from .errors import (
    ComfyAdapterError,
    TransportFailure,
    cancelled_error,
    offline_error,
    timeout_error,
)
from .models import (
    ComfyCapabilities,
    ComfyEnqueueCommand,
    EnqueueResult,
    HealthState,
    IntegrationHealth,
    OutputDescriptor,
    ProgressEvent,
    PromptState,
    RetrievedOutput,
    RetryPolicy,
)
from .ledger import EnqueueLedger, EnqueueLedgerConflict
from .transport import HttpResponse, JsonTransport, UrllibJsonTransport
from .security import validate_output_descriptor, validate_prompt_id
from .workflows import ArtifactInputResolver, TrustedWorkflowRegistry


ADAPTER_VERSION = "0.1.0"
TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class ComfyUIAdapter:
    def __init__(
        self,
        *,
        endpoint: str,
        workflows: TrustedWorkflowRegistry,
        artifact_resolver: ArtifactInputResolver,
        enqueue_ledger: Optional[EnqueueLedger] = None,
        allow_ephemeral_ledger: bool = False,
        allowed_hosts: Sequence[str] = ("127.0.0.1", "localhost", "::1"),
        allow_global_interrupt: bool = False,
        retry_policy: Optional[RetryPolicy] = None,
        transport: Optional[JsonTransport] = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("ComfyUI endpoint must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("ComfyUI endpoint cannot contain credentials")
        if parsed.hostname not in set(allowed_hosts):
            raise PermissionError("ComfyUI endpoint host is not allowlisted")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("ComfyUI endpoint cannot include a path, query, or fragment")
        if enqueue_ledger is None:
            raise ValueError("live ComfyUI requires an injected durable enqueue ledger")
        if not enqueue_ledger.durable and not allow_ephemeral_ledger:
            raise PermissionError(
                "process-local enqueue ledgers require explicit test-only opt-in"
            )

        self._endpoint = endpoint.rstrip("/")
        self._workflows = workflows
        self._artifact_resolver = artifact_resolver
        self._enqueue_ledger = enqueue_ledger
        self._allow_global_interrupt = allow_global_interrupt
        self._retry = retry_policy or RetryPolicy()
        self._transport = transport or UrllibJsonTransport()
        self._sleep = sleeper
        self._clock = clock
        self._prompt_states: Dict[str, PromptState] = {}

    def health_check(self) -> IntegrationHealth:
        try:
            self._request("GET", "/system_stats", None)
        except ComfyAdapterError as exc:
            return IntegrationHealth(
                state=HealthState.OFFLINE,
                endpoint=self._endpoint,
                adapter_version=ADAPTER_VERSION,
                error_code=exc.code,
                message=exc.message,
            )
        return IntegrationHealth(
            state=HealthState.ONLINE,
            endpoint=self._endpoint,
            adapter_version=ADAPTER_VERSION,
        )

    def capabilities(self) -> ComfyCapabilities:
        return ComfyCapabilities(
            adapter_version=ADAPTER_VERSION,
            trusted_workflow_references=list(self._workflows.references),
            running_cancel_scope="global" if self._allow_global_interrupt else "disabled",
            durable_enqueue_idempotency=self._enqueue_ledger.durable,
        )

    def enqueue(self, command: ComfyEnqueueCommand) -> EnqueueResult:
        command = ComfyEnqueueCommand.model_validate(command.model_dump(mode="python"))
        if command.execution_mode != "live":
            raise ComfyAdapterError(
                "EXECUTION_MODE_MISMATCH",
                "The HTTP adapter accepts only live commands.",
                retryable=False,
            )
        graph = self._workflows.bind(command, self._artifact_resolver)
        try:
            claim = self._enqueue_ledger.claim(command)
        except EnqueueLedgerConflict as exc:
            raise ComfyAdapterError(
                "IDEMPOTENCY_CONFLICT",
                "The request ID was already used for different inputs.",
                retryable=False,
                details={"request_id": command.request_id},
            ) from exc
        if not claim.created:
            if claim.state == "succeeded" and claim.result is not None:
                self._prompt_states.setdefault(claim.result.prompt_id, PromptState.QUEUED)
                payload = claim.result.model_dump(mode="python")
                payload["reused_request"] = True
                return EnqueueResult.model_validate(payload)
            raise ComfyAdapterError(
                "IDEMPOTENCY_UNCERTAIN",
                "The prior enqueue delivery is incomplete or uncertain; reconcile ComfyUI before retrying.",
                retryable=False,
                details={"request_id": command.request_id},
                suggested_actions=["integration.open"],
            )

        try:
            response = self._request(
                "POST",
                "/prompt",
                {"prompt": graph, "client_id": "sceneops:" + command.render_job_id},
            )
            body = self._json_object(response)
            prompt_id = body.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise self._response_error("ComfyUI enqueue response omitted prompt_id")
            validate_prompt_id(prompt_id)
            result = EnqueueResult(
                request_id=command.request_id,
                render_job_id=command.render_job_id,
                prompt_id=prompt_id,
                workflow_reference=command.workflow_reference,
                workflow_checksum_sha256=command.workflow_checksum_sha256,
                adapter_version=ADAPTER_VERSION,
            )
        except ComfyAdapterError as exc:
            self._enqueue_ledger.mark_uncertain(command.request_id)
            if exc.code == "DELIVERY_UNCERTAIN":
                raise
            raise ComfyAdapterError(
                "DELIVERY_UNCERTAIN",
                "ComfyUI accepted or may have accepted the command, but its prompt ID could not be verified.",
                retryable=False,
                details={"request_id": command.request_id, "cause_code": exc.code},
                suggested_actions=["integration.open"],
            ) from exc
        self._enqueue_ledger.mark_succeeded(command.request_id, result)
        self._prompt_states[prompt_id] = PromptState.QUEUED
        return result

    def progress(self, prompt_id: str) -> ProgressEvent:
        prior_state = self._require_owned_prompt(prompt_id)
        if prior_state in {
            PromptState.SUCCEEDED,
            PromptState.FAILED,
            PromptState.CANCELLED,
        }:
            return ProgressEvent(
                prompt_id=prompt_id,
                state=prior_state,
                progress=1.0 if prior_state != PromptState.CANCELLED else 0.0,
                message="ComfyUI prompt is in a terminal local state.",
            )
        response = self._request("GET", "/history/" + prompt_id, None)
        body = self._json_object(response)
        record = body.get(prompt_id)
        if not isinstance(record, dict):
            return ProgressEvent(
                prompt_id=prompt_id,
                state=prior_state,
                progress=0.0,
                message="ComfyUI has not published prompt history.",
            )

        status = record.get("status", {})
        status_name = status.get("status_str") if isinstance(status, dict) else None
        completed = bool(status.get("completed")) if isinstance(status, dict) else False
        outputs = record.get("outputs")
        if status_name in {"error", "failed"}:
            state = PromptState.FAILED
            progress = 1.0
            message = "ComfyUI reported a failed prompt."
        elif completed or (isinstance(outputs, dict) and bool(outputs)):
            state = PromptState.SUCCEEDED
            progress = 1.0
            message = "ComfyUI prompt completed."
        else:
            state = PromptState.RUNNING
            progress = 0.0
            message = "ComfyUI prompt is running; exact progress is unavailable."
        self._prompt_states[prompt_id] = state
        return ProgressEvent(
            prompt_id=prompt_id,
            state=state,
            progress=progress,
            message=message,
        )

    def wait_for_completion(
        self,
        prompt_id: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float = 0.25,
        cancellation: Optional[CancellationToken] = None,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> ProgressEvent:
        if timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("timeout and poll interval must be positive")
        deadline = self._clock() + timeout_seconds
        while True:
            if cancellation is not None and cancellation.cancelled:
                self.cancel(prompt_id)
                raise cancelled_error(prompt_id)
            event = self.progress(prompt_id)
            if on_progress is not None:
                on_progress(event)
            if event.state == PromptState.SUCCEEDED:
                return event
            if event.state == PromptState.FAILED:
                raise ComfyAdapterError(
                    "RENDER_FAILED",
                    event.message,
                    retryable=True,
                    details={"prompt_id": prompt_id},
                    suggested_actions=["render.job.retry"],
                )
            if event.state == PromptState.CANCELLED:
                raise cancelled_error(prompt_id)
            if self._clock() >= deadline:
                raise timeout_error(prompt_id)
            self._sleep(poll_interval_seconds)

    def cancel(self, prompt_id: str) -> ProgressEvent:
        state = self._require_owned_prompt(prompt_id)
        if state in {PromptState.SUCCEEDED, PromptState.FAILED, PromptState.CANCELLED}:
            raise ComfyAdapterError(
                "CANCEL_NOT_ALLOWED",
                "Only queued or running prompts can be cancelled.",
                retryable=False,
                details={"prompt_id": prompt_id, "state": state.value},
            )
        if state == PromptState.QUEUED:
            self._request("POST", "/queue", {"delete": [prompt_id]})
        else:
            if not self._allow_global_interrupt:
                raise ComfyAdapterError(
                    "CANCEL_SCOPE_UNSAFE",
                    "This ComfyUI version only exposes a global running interrupt, which is disabled.",
                    retryable=False,
                    details={"prompt_id": prompt_id},
                    suggested_actions=["integration.open"],
                )
            self._request("POST", "/interrupt", None)
        self._prompt_states[prompt_id] = PromptState.CANCELLED
        return ProgressEvent(
            prompt_id=prompt_id,
            state=PromptState.CANCELLED,
            progress=0.0,
            message="ComfyUI prompt cancelled.",
        )

    def list_outputs(self, prompt_id: str) -> List[OutputDescriptor]:
        self._require_owned_prompt(prompt_id)
        response = self._request("GET", "/history/" + prompt_id, None)
        body = self._json_object(response)
        record = body.get(prompt_id)
        if not isinstance(record, dict):
            raise self._response_error("ComfyUI history omitted the prompt record")
        outputs = record.get("outputs")
        if not isinstance(outputs, dict):
            raise self._response_error("ComfyUI history omitted outputs")

        descriptors: List[OutputDescriptor] = []
        for node_id, node_output in outputs.items():
            images = node_output.get("images", []) if isinstance(node_output, dict) else []
            for image in images:
                descriptor = OutputDescriptor(
                    prompt_id=prompt_id,
                    node_id=str(node_id),
                    filename=image.get("filename", ""),
                    subfolder=image.get("subfolder", ""),
                    output_type=image.get("type", "output"),
                )
                validate_output_descriptor(descriptor)
                descriptors.append(descriptor)
        if not descriptors:
            raise self._response_error("ComfyUI history contained no image outputs")
        return descriptors

    def retrieve_output(self, descriptor: OutputDescriptor) -> Tuple[RetrievedOutput, bytes]:
        descriptor = OutputDescriptor.model_validate(descriptor.model_dump(mode="python"))
        self._require_owned_prompt(descriptor.prompt_id)
        validate_output_descriptor(descriptor)
        authoritative = self.list_outputs(descriptor.prompt_id)
        if descriptor not in authoritative:
            raise ComfyAdapterError(
                "OUTPUT_NOT_OWNED",
                "The output descriptor is not present in this prompt's history.",
                retryable=False,
                details={"prompt_id": descriptor.prompt_id},
            )
        query = urlencode(
            {
                "filename": descriptor.filename,
                "subfolder": descriptor.subfolder,
                "type": descriptor.output_type,
            }
        )
        response = self._request("GET", "/view?" + query, None)
        metadata = RetrievedOutput(
            descriptor=descriptor,
            content_type=response.content_type,
            byte_count=len(response.body),
        )
        return metadata, response.body

    def _request(
        self, method: str, path: str, body: Optional[Dict[str, Any]]
    ) -> HttpResponse:
        last_transport_error: Optional[TransportFailure] = None
        retry_safe = method in {"GET", "HEAD"}
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                response = self._transport.request(
                    method,
                    self._endpoint + path,
                    body,
                    self._retry.request_timeout_seconds,
                )
            except TransportFailure as exc:
                last_transport_error = exc
                if retry_safe and attempt < self._retry.max_attempts:
                    self._sleep(self._retry.backoff_seconds * attempt)
                    continue
                if not retry_safe:
                    raise ComfyAdapterError(
                        "DELIVERY_UNCERTAIN",
                        "ComfyUI command delivery could not be confirmed; it was not retried automatically.",
                        retryable=False,
                        details={"path": path},
                        suggested_actions=["integration.open"],
                    ) from exc
                raise offline_error(str(exc)) from exc
            if (
                retry_safe
                and response.status_code in TRANSIENT_STATUS_CODES
                and attempt < self._retry.max_attempts
            ):
                self._sleep(self._retry.backoff_seconds * attempt)
                continue
            if response.status_code >= 300:
                raise ComfyAdapterError(
                    "INTEGRATION_HTTP_ERROR",
                    "ComfyUI returned HTTP %d." % response.status_code,
                    retryable=response.status_code in TRANSIENT_STATUS_CODES,
                    details={"status_code": response.status_code},
                    suggested_actions=["integration.open", "render.job.retry"],
                )
            return response
        raise offline_error(str(last_transport_error or "unknown transport failure"))

    @staticmethod
    def _json_object(response: HttpResponse) -> dict:
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ComfyUIAdapter._response_error("ComfyUI returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise ComfyUIAdapter._response_error("ComfyUI JSON response must be an object")
        return body

    @staticmethod
    def _response_error(message: str) -> ComfyAdapterError:
        return ComfyAdapterError(
            "INTEGRATION_INVALID_RESPONSE",
            message,
            retryable=True,
            suggested_actions=["integration.open", "render.job.retry"],
        )

    def _require_owned_prompt(self, prompt_id: str) -> PromptState:
        validate_prompt_id(prompt_id)
        try:
            return self._prompt_states[prompt_id]
        except KeyError as exc:
            raise ComfyAdapterError(
                "PROMPT_NOT_OWNED",
                "The prompt was not enqueued by this adapter instance.",
                retryable=False,
                details={"prompt_id": prompt_id},
            ) from exc
