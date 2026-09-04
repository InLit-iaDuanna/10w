import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from comfyui_adapter import (
    CancellationToken,
    ComfyAdapterError,
    ComfyEnqueueCommand,
    ComfyUIAdapter,
    DeterministicMockComfyAdapter,
    HealthState,
    HttpResponse,
    InMemoryEnqueueLedger,
    OutputDescriptor,
    PromptState,
    RetryPolicy,
    SQLiteEnqueueLedger,
    TransportFailure,
    TrustedWorkflow,
    TrustedWorkflowRegistry,
    WorkflowBinding,
    compute_workflow_checksum_sha256,
)


OUTPUT_CHECKSUM = "b" * 64
WORKFLOW_GRAPH = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "configured"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "configured"}},
    "3": {"class_type": "KSampler", "inputs": {"seed": 0}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "configured"}},
    "5": {"class_type": "LoadImage", "inputs": {"image": "configured"}},
}
CHECKSUM = compute_workflow_checksum_sha256(WORKFLOW_GRAPH)


class Resolver:
    def __init__(self, values=None):
        self.values = values or {"artifact_depth": "scene/depth.exr"}

    def resolve_staged_input(self, artifact_id):
        return self.values[artifact_id]


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, body, timeout_seconds):
        self.calls.append((method, url, body, timeout_seconds))
        if not self.responses:
            raise AssertionError("unexpected transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(payload, status=200, content_type="application/json"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return HttpResponse(status_code=status, body=body, content_type=content_type)


def workflow():
    return TrustedWorkflow(
        reference="lookdev.lighting-visibility.v1",
        checksum_sha256=CHECKSUM,
        graph=deepcopy(WORKFLOW_GRAPH),
        bindings=[
            WorkflowBinding(source="prompt", node_id="1", input_name="text"),
            WorkflowBinding(source="negative_prompt", node_id="2", input_name="text"),
            WorkflowBinding(source="seed", node_id="3", input_name="seed"),
            WorkflowBinding(source="model_reference", node_id="4", input_name="ckpt_name"),
            WorkflowBinding(source="aov.depth", node_id="5", input_name="image"),
        ],
        allowed_model_references=["models/lookdev-v1.safetensors"],
    )


def command(mode="live", request_id="req_1"):
    return ComfyEnqueueCommand(
        request_id=request_id,
        render_job_id="rjob_1",
        workflow_reference="lookdev.lighting-visibility.v1",
        workflow_checksum_sha256=CHECKSUM,
        model_reference="models/lookdev-v1.safetensors",
        seed=42,
        prompt="warm target light",
        negative_prompt="camera move",
        aov_artifact_ids={"depth": "artifact_depth"},
        execution_mode=mode,
    )


def adapter(transport, **changes):
    kwargs = {
        "endpoint": "http://127.0.0.1:8188",
        "workflows": TrustedWorkflowRegistry([workflow()]),
        "artifact_resolver": Resolver(),
        "enqueue_ledger": InMemoryEnqueueLedger(),
        "allow_ephemeral_ledger": True,
        "retry_policy": RetryPolicy(
            max_attempts=3,
            request_timeout_seconds=1.0,
            backoff_seconds=0.0,
        ),
        "transport": transport,
        "sleeper": lambda _seconds: None,
    }
    kwargs.update(changes)
    return ComfyUIAdapter(**kwargs)


class ComfyUIAdapterTests(unittest.TestCase):
    def test_enqueue_binds_only_trusted_inputs(self):
        transport = FakeTransport([response({"prompt_id": "prompt_1"})])
        result = adapter(transport).enqueue(command())
        self.assertEqual(result.prompt_id, "prompt_1")
        self.assertEqual(result.execution_mode, "live")
        graph = transport.calls[0][2]["prompt"]
        self.assertEqual(graph["1"]["inputs"]["text"], "warm target light")
        self.assertEqual(graph["3"]["inputs"]["seed"], 42)
        self.assertEqual(graph["5"]["inputs"]["image"], "scene/depth.exr")
        self.assertNotIn("workflow", command().model_dump())

    def test_untrusted_workflow_or_model_is_rejected_without_network(self):
        transport = FakeTransport([])
        unsafe = command().model_copy(update={"workflow_checksum_sha256": "f" * 64})
        with self.assertRaisesRegex(ComfyAdapterError, "not configured") as error:
            adapter(transport).enqueue(unsafe)
        self.assertEqual(error.exception.code, "WORKFLOW_NOT_ALLOWED")
        self.assertEqual(transport.calls, [])

        unsafe_model = command().model_copy(update={"model_reference": "models/unknown"})
        with self.assertRaises(ComfyAdapterError) as error:
            adapter(transport).enqueue(unsafe_model)
        self.assertEqual(error.exception.code, "MODEL_NOT_ALLOWED")

    def test_artifact_path_traversal_is_rejected(self):
        transport = FakeTransport([])
        instance = adapter(transport, artifact_resolver=Resolver({"artifact_depth": "../secret.exr"}))
        with self.assertRaises(ComfyAdapterError) as error:
            instance.enqueue(command())
        self.assertEqual(error.exception.code, "AOV_INPUT_REJECTED")
        self.assertEqual(transport.calls, [])

    def test_remote_endpoint_requires_explicit_host_allowlist(self):
        with self.assertRaisesRegex(PermissionError, "not allowlisted"):
            ComfyUIAdapter(
                endpoint="https://render.example.test",
                workflows=TrustedWorkflowRegistry([workflow()]),
                artifact_resolver=Resolver(),
            )

    def test_live_adapter_requires_durable_ledger_by_default(self):
        with self.assertRaisesRegex(ValueError, "durable enqueue ledger"):
            ComfyUIAdapter(
                endpoint="http://127.0.0.1:8188",
                workflows=TrustedWorkflowRegistry([workflow()]),
                artifact_resolver=Resolver(),
            )
        with self.assertRaisesRegex(PermissionError, "test-only opt-in"):
            ComfyUIAdapter(
                endpoint="http://127.0.0.1:8188",
                workflows=TrustedWorkflowRegistry([workflow()]),
                artifact_resolver=Resolver(),
                enqueue_ledger=InMemoryEnqueueLedger(),
            )

    def test_health_reports_offline_after_bounded_retries(self):
        transport = FakeTransport(
            [TransportFailure("offline"), TransportFailure("offline"), TransportFailure("offline")]
        )
        health = adapter(transport).health_check()
        self.assertEqual(health.state, HealthState.OFFLINE)
        self.assertEqual(health.error_code, "INTEGRATION_OFFLINE")
        self.assertEqual(len(transport.calls), 3)

    def test_transient_read_failure_retries_health_check(self):
        transport = FakeTransport(
            [response({"error": "busy"}, status=503), response({"system": "ready"})]
        )
        health = adapter(transport).health_check()
        self.assertEqual(health.state, HealthState.ONLINE)
        self.assertEqual(len(transport.calls), 2)

    def test_enqueue_transport_failure_is_not_retried_or_replayed_blindly(self):
        transport = FakeTransport([TransportFailure("connection reset after send")])
        instance = adapter(transport)
        with self.assertRaises(ComfyAdapterError) as error:
            instance.enqueue(command())
        self.assertEqual(error.exception.code, "DELIVERY_UNCERTAIN")
        self.assertEqual(len(transport.calls), 1)
        with self.assertRaises(ComfyAdapterError) as second:
            instance.enqueue(command())
        self.assertEqual(second.exception.code, "IDEMPOTENCY_UNCERTAIN")
        self.assertEqual(len(transport.calls), 1)

    def test_request_id_is_idempotent_and_conflicts_are_rejected(self):
        transport = FakeTransport([response({"prompt_id": "prompt_once"})])
        instance = adapter(transport)
        first = instance.enqueue(command())
        second = instance.enqueue(command())
        self.assertFalse(first.reused_request)
        self.assertTrue(second.reused_request)
        self.assertEqual(len(transport.calls), 1)
        with self.assertRaises(ComfyAdapterError) as error:
            instance.enqueue(command().model_copy(update={"prompt": "different"}))
        self.assertEqual(error.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_shared_ledger_prevents_enqueue_replay_after_adapter_restart(self):
        ledger = InMemoryEnqueueLedger()
        first_transport = FakeTransport([response({"prompt_id": "prompt_once"})])
        first = adapter(first_transport, enqueue_ledger=ledger).enqueue(command())
        second_transport = FakeTransport([])
        second = adapter(second_transport, enqueue_ledger=ledger).enqueue(command())
        self.assertEqual(first.prompt_id, second.prompt_id)
        self.assertTrue(second.reused_request)
        self.assertEqual(second_transport.calls, [])

    def test_sqlite_ledger_survives_process_style_reconstruction(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "enqueue.sqlite3"
            first_transport = FakeTransport([response({"prompt_id": "prompt_durable"})])
            first = adapter(
                first_transport,
                enqueue_ledger=SQLiteEnqueueLedger(path),
                allow_ephemeral_ledger=False,
            ).enqueue(command())
            second_transport = FakeTransport([])
            second = adapter(
                second_transport,
                enqueue_ledger=SQLiteEnqueueLedger(path),
                allow_ephemeral_ledger=False,
            ).enqueue(command())
            self.assertEqual(first.prompt_id, second.prompt_id)
            self.assertTrue(second.reused_request)
            self.assertEqual(second_transport.calls, [])

    def test_invalid_success_response_is_persistently_uncertain(self):
        ledger = InMemoryEnqueueLedger()
        first_transport = FakeTransport([response({})])
        with self.assertRaises(ComfyAdapterError) as first:
            adapter(first_transport, enqueue_ledger=ledger).enqueue(command())
        self.assertEqual(first.exception.code, "DELIVERY_UNCERTAIN")
        second_transport = FakeTransport([])
        with self.assertRaises(ComfyAdapterError) as second:
            adapter(second_transport, enqueue_ledger=ledger).enqueue(command())
        self.assertEqual(second.exception.code, "IDEMPOTENCY_UNCERTAIN")
        self.assertEqual(second_transport.calls, [])

    def test_wait_timeout_is_structured(self):
        transport = FakeTransport(
            [response({"prompt_id": "prompt_timeout"}), response({})]
        )
        ticks = iter([0.0, 1.0])
        instance = adapter(transport, clock=lambda: next(ticks))
        instance.enqueue(command())
        with self.assertRaises(ComfyAdapterError) as error:
            instance.wait_for_completion(
                "prompt_timeout", timeout_seconds=1.0, poll_interval_seconds=0.1
            )
        self.assertEqual(error.exception.code, "INTEGRATION_TIMEOUT")
        self.assertTrue(error.exception.retryable)

    def test_cancelled_wait_deletes_queued_prompt(self):
        transport = FakeTransport(
            [response({"prompt_id": "prompt_cancel"}), response({"ok": True})]
        )
        instance = adapter(transport)
        instance.enqueue(command())
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(ComfyAdapterError) as error:
            instance.wait_for_completion(
                "prompt_cancel", timeout_seconds=1.0, cancellation=token
            )
        self.assertEqual(error.exception.code, "RUN_CANCELLED")
        self.assertEqual(transport.calls[-1][1], "http://127.0.0.1:8188/queue")
        self.assertEqual(transport.calls[-1][2], {"delete": ["prompt_cancel"]})

    def test_cancelled_prompt_state_cannot_regress_on_poll(self):
        transport = FakeTransport(
            [response({"prompt_id": "prompt_cancelled"}), response({"ok": True})]
        )
        instance = adapter(transport)
        instance.enqueue(command())
        instance.cancel("prompt_cancelled")
        event = instance.progress("prompt_cancelled")
        self.assertEqual(event.state, PromptState.CANCELLED)
        self.assertEqual(len(transport.calls), 2)

    def test_running_cancel_uses_interrupt(self):
        transport = FakeTransport(
            [
                response({"prompt_id": "prompt_running"}),
                response({
                    "prompt_running": {
                        "status": {"completed": False, "status_str": "running"}
                    }
                }),
                response({"ok": True}),
            ]
        )
        instance = adapter(transport, allow_global_interrupt=True)
        instance.enqueue(command())
        progress = instance.progress("prompt_running")
        self.assertEqual(progress.state, PromptState.RUNNING)
        instance.cancel("prompt_running")
        self.assertEqual(transport.calls[-1][1], "http://127.0.0.1:8188/interrupt")
        self.assertEqual(instance.capabilities().running_cancel_scope, "global")

    def test_running_global_interrupt_is_disabled_by_default(self):
        transport = FakeTransport(
            [
                response({"prompt_id": "prompt_safe"}),
                response({
                    "prompt_safe": {
                        "status": {"completed": False, "status_str": "running"}
                    }
                }),
            ]
        )
        instance = adapter(transport)
        instance.enqueue(command())
        instance.progress("prompt_safe")
        with self.assertRaises(ComfyAdapterError) as error:
            instance.cancel("prompt_safe")
        self.assertEqual(error.exception.code, "CANCEL_SCOPE_UNSAFE")
        self.assertEqual(instance.capabilities().running_cancel_scope, "disabled")
        self.assertEqual(len(transport.calls), 2)

    def test_output_retrieval_validates_paths(self):
        history = {
            "prompt_output": {
                "status": {"completed": True, "status_str": "success"},
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "result.png", "subfolder": "sceneops", "type": "output"}
                        ]
                    }
                },
            }
        }
        transport = FakeTransport(
            [
                response({"prompt_id": "prompt_output"}),
                response(history),
                response(history),
                response(b"png-bytes", content_type="image/png"),
            ]
        )
        instance = adapter(transport)
        instance.enqueue(command())
        descriptors = instance.list_outputs("prompt_output")
        metadata, content = instance.retrieve_output(descriptors[0])
        self.assertEqual(content, b"png-bytes")
        self.assertEqual(metadata.byte_count, 9)
        self.assertIn("filename=result.png", transport.calls[-1][1])

        unsafe = OutputDescriptor(
            prompt_id="prompt_output",
            node_id="9",
            filename="../secret.png",
        )
        with self.assertRaises(ComfyAdapterError) as error:
            instance.retrieve_output(unsafe)
        self.assertEqual(error.exception.code, "OUTPUT_PATH_REJECTED")

    def test_output_descriptor_must_belong_to_prompt_history(self):
        history = {
            "prompt_output": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "result.png", "subfolder": "sceneops", "type": "output"}
                        ]
                    }
                }
            }
        }
        transport = FakeTransport(
            [response({"prompt_id": "prompt_output"}), response(history)]
        )
        instance = adapter(transport)
        instance.enqueue(command())
        forged = OutputDescriptor(
            prompt_id="prompt_output",
            node_id="9",
            filename="other.png",
            subfolder="sceneops",
        )
        with self.assertRaises(ComfyAdapterError) as error:
            instance.retrieve_output(forged)
        self.assertEqual(error.exception.code, "OUTPUT_NOT_OWNED")

    def test_http_and_mock_adapters_reject_mislabeled_commands(self):
        with self.assertRaises(ComfyAdapterError) as error:
            adapter(FakeTransport([])).enqueue(command(mode="mock"))
        self.assertEqual(error.exception.code, "EXECUTION_MODE_MISMATCH")

    def test_prompt_id_and_endpoint_credentials_are_rejected(self):
        transport = FakeTransport([response({"prompt_id": "../unsafe"})])
        with self.assertRaises(ComfyAdapterError) as error:
            adapter(transport).enqueue(command())
        self.assertEqual(error.exception.code, "DELIVERY_UNCERTAIN")
        self.assertEqual(error.exception.details["cause_code"], "PROMPT_ID_REJECTED")
        with self.assertRaisesRegex(ValueError, "credentials"):
            ComfyUIAdapter(
                endpoint="http://user:secret@127.0.0.1:8188",
                workflows=TrustedWorkflowRegistry([workflow()]),
                artifact_resolver=Resolver(),
            )

        mock = DeterministicMockComfyAdapter(
            workflows=TrustedWorkflowRegistry([workflow()]),
            artifact_resolver=Resolver(),
            output_checksum_sha256=OUTPUT_CHECKSUM,
        )
        with self.assertRaises(ComfyAdapterError) as error:
            mock.enqueue(command(mode="live"))
        self.assertEqual(error.exception.code, "EXECUTION_MODE_MISMATCH")

    def test_trusted_workflow_checksum_and_binding_semantics_are_verified(self):
        changed = workflow().model_copy(deep=True)
        changed.graph["1"]["inputs"]["text"] = "drifted"
        with self.assertRaisesRegex(ValueError, "checksum"):
            TrustedWorkflowRegistry([changed])

        unsafe_graph = deepcopy(WORKFLOW_GRAPH)
        unsafe_graph["6"] = {"class_type": "ExecuteShell", "inputs": {"command": ""}}
        unsafe = TrustedWorkflow(
            reference="unsafe",
            checksum_sha256=compute_workflow_checksum_sha256(unsafe_graph),
            graph=unsafe_graph,
            bindings=[
                WorkflowBinding(source="prompt", node_id="6", input_name="command")
            ],
            allowed_model_references=["models/lookdev-v1.safetensors"],
        )
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            TrustedWorkflowRegistry([unsafe])

    def test_deterministic_mock_is_explicit_and_repeatable(self):
        mock = DeterministicMockComfyAdapter(
            workflows=TrustedWorkflowRegistry([workflow()]),
            artifact_resolver=Resolver(),
            output_checksum_sha256=OUTPUT_CHECKSUM,
        )
        first = mock.enqueue(command(mode="mock"))
        second = mock.enqueue(command(mode="mock"))
        self.assertEqual(first.prompt_id, second.prompt_id)
        self.assertTrue(second.reused_request)
        self.assertEqual(mock.progress(first.prompt_id).state, PromptState.RUNNING)
        self.assertEqual(mock.progress(first.prompt_id).state, PromptState.SUCCEEDED)
        output = mock.output(first.prompt_id)
        self.assertEqual(output.execution_mode, "mock")
        self.assertEqual(output.checksum_sha256, OUTPUT_CHECKSUM)
        self.assertEqual(mock.health_check().execution_mode, "mock")
        self.assertEqual(mock.capabilities().execution_mode, "mock")

    def test_deterministic_mock_cancel_is_explicit(self):
        mock = DeterministicMockComfyAdapter(
            workflows=TrustedWorkflowRegistry([workflow()]),
            artifact_resolver=Resolver(),
            output_checksum_sha256=OUTPUT_CHECKSUM,
        )
        enqueued = mock.enqueue(command(mode="mock", request_id="req_cancel_mock"))
        cancelled = mock.cancel(enqueued.prompt_id)
        self.assertEqual(cancelled.state, PromptState.CANCELLED)
        self.assertEqual(cancelled.execution_mode, "mock")
        self.assertEqual(mock.progress(enqueued.prompt_id).state, PromptState.CANCELLED)


if __name__ == "__main__":
    unittest.main()
