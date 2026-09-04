# ComfyUI HTTP Adapter

This integration gives Render Ops a typed, allowlisted ComfyUI boundary. A
render command selects a preconfigured workflow by reference and SHA-256
checksum. Only declared prompt, negative prompt, seed, model reference, and
pre-staged AOV artifact bindings can change. Commands cannot provide workflow
JSON, workflow files, local paths, node IDs, or output paths.

## Supported behavior

- health and capability reports;
- HTTP enqueue with durable request-ID idempotency;
- transient retry for read-only requests with a bounded pinned policy;
- progress/history polling;
- queued deletion and running interruption;
- timeout and cooperative cancellation;
- safe output descriptor parsing and byte retrieval;
- structured error codes and suggested actions;
- deterministic mock implementation with an explicit `mock` mode.

The concrete HTTP transport is implemented with the Python standard library.
Pydantic 2.13.2 is the only runtime dependency. ComfyUI itself must be installed
and pinned separately by the deployment owner; this repository does not fetch
or execute a workflow package.

## Configuration

The default endpoint is `http://127.0.0.1:8188`. Remote hosts are rejected unless
the composition root explicitly adds the exact hostname to `allowed_hosts`.
Provide `TrustedWorkflow` values from deployment-owned configuration and an
`ArtifactInputResolver` that maps stable artifact IDs to already staged relative
input names. The adapter rejects absolute paths, parent traversal, and backslash
paths returned by that resolver.

The registry recomputes the canonical workflow graph SHA-256 and rejects a
declared checksum that does not match. Every node class and each mutable binding
semantic is checked against code-owned allowlists; adding a deployment-specific
node class requires an explicit registry configuration change. The command can
never extend that binding map.

Live construction also requires an injected `EnqueueLedger`. Use
`SQLiteEnqueueLedger` (or a composition-root implementation with equivalent
atomic persistence) so request claims, uncertain deliveries, and successful
prompt IDs survive process restarts. `InMemoryEnqueueLedger` is rejected unless
`allow_ephemeral_ledger=True` is explicitly selected for tests. A claimed or
uncertain request is never blindly posted again, including when ComfyUI returns
a malformed 2xx response.

ComfyUI's running `/interrupt` endpoint is global rather than prompt-scoped.
Render Ops therefore disables it by default and reports
`CANCEL_SCOPE_UNSAFE`; deployments may explicitly set
`allow_global_interrupt=True` only for a dedicated worker. Queued prompts are
deleted by prompt ID. Mutating HTTP requests are never retried automatically
after an uncertain transport failure, preventing duplicate prompt submission;
the request is held in the durable ledger's uncertain state until the operator reconciles the
Comfy queue.

Output retrieval first re-reads the owning prompt history and accepts only an
exact descriptor emitted for that prompt, preventing cross-prompt filename
selection on a shared output root.

## Tests

From the repository root:

```bash
PYTHONPATH=integrations/comfyui-adapter/src \
  python3 -m unittest discover \
  -s integrations/comfyui-adapter/src/comfyui_adapter/tests -v
```

All tests inject a fake transport and run in `mock` test context. They do not
contact or claim a live ComfyUI service.

## Troubleshooting

- `INTEGRATION_OFFLINE`: start the configured pinned ComfyUI service and re-run
  health check.
- `WORKFLOW_NOT_ALLOWED`: configure the exact trusted reference/checksum pair;
  do not upload a workflow through the render command.
- `AOV_INPUT_REJECTED`: stage the artifact through artifact storage and return a
  safe relative input name.
- `INTEGRATION_TIMEOUT`: inspect ComfyUI queue/VRAM health, then retry with a new
  render-job attempt.
- `IDEMPOTENCY_UNCERTAIN`: inspect the ComfyUI queue before issuing a new
  request ID; the adapter intentionally did not replay the mutating request.
- `CANCEL_SCOPE_UNSAFE`: use a dedicated Comfy worker and explicitly allow its
  global interrupt, or let the current prompt finish.

## Current status

The adapter and deterministic test coverage are implemented. No ComfyUI host or trusted
production workflow is configured in this worktree, so live generation is
`blocked`. There is no prior live output for a truthful `cached` replay.
