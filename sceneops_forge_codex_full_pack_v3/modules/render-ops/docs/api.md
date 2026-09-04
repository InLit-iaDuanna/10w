# Render Ops API

The backend public entrypoint is `render_ops.router`. The API composition root
can mount it without importing repositories or vendor adapters.

## `POST /api/v1/render/jobs/plan`

Accepts `RenderJobPlanRequest` and returns a queued `RenderJob` with an explicit
AOV cache plan. The request includes the complete `RenderBrief`, `RenderRecipe`,
recipe/sample/scene/camera dependency versions, prior immutable AOV references, prior
dependency snapshot, truthful execution mode, and UTC request time.

Planning does not execute Blender, Unity, ComfyUI, or filesystem operations.
Mock AOVs cannot be reused by a live/cached-real plan, and live/cached-real AOVs
cannot be relabelled as mock.

## `POST /api/v1/render/manifests/validate`

Accepts a complete `RenderManifest` and returns `ManifestSummary`. Pydantic
rejects missing or duplicate passes, identity drift, non-UTC timestamps,
incompatible execution modes, incomplete approval, or broken links between
brief, recipe, job, variants, comparisons, writebacks, and validations.
Approved writebacks are re-parsed against their immutable approval snapshot,
and each comparison must provide the exact protected-region threshold set from
the render brief.

The Pydantic models are the network source of truth. The module-runtime task
must generate the TypeScript client from the composed OpenAPI document; this
module does not hand-copy request/response DTOs.

The internal engine extension uses `SceneWritebackAdapter` and returns a
`WritebackExecution` containing both the writeback result and its validation
capture. `WritebackExecutor` cannot run without a core-backed
`ChangeSetApprovalVerifier`, and live adapters must advertise durable
ChangeSet-ID deduplication.

## Errors

FastAPI validation errors cover malformed request contracts. Runtime workers map
external failures to the shared structured error envelope when that core module
is available. Render Ops currently emits module-local structured `JobFailure`
objects with `code`, `message`, `retryable`, and `suggested_actions`; registering
the shared envelope is `planned`, not silently emulated here.
