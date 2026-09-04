# Render Ops integration contract

## Inputs

The caller supplies stable project, scene, camera, and `sceneops_id` object IDs,
plus explicit version tokens. Artifact storage supplies immutable AOV and output
references with externally calculated SHA-256 checksums. Render Ops validates
and preserves checksums; it does not access another module's files directly.

## ComfyUI boundary

Render Ops constructs `ComfyEnqueueCommand` values. The adapter accepts a
trusted workflow reference/checksum pair and binds only prompt, negative prompt,
seed, and pre-staged AOV artifact IDs into allowlisted node inputs. Arbitrary
workflow JSON, workflow paths, node paths, and filesystem paths are not command
fields.

The integration must provide health, capabilities, enqueue, progress, cancel,
retry, history/output retrieval, structured errors, and execution provenance.
See `../../../integrations/comfyui-adapter/README.md`.

Read-only HTTP calls may retry transient failures. Prompt enqueue is not
automatically retried after uncertain delivery because ComfyUI has no native
request-ID idempotency contract. Running cancellation uses a global ComfyUI
interrupt and is disabled unless the endpoint is a dedicated worker and the
operator explicitly enables it; queued cancellation remains prompt-scoped.

## Blender and Unity writeback extension

The missing Blender or Unity owner implements the public
`SceneWritebackAdapter` protocol without importing Render Ops internals. The
adapter receives only a validated `WritebackProposal` with:

- approved state and non-empty ChangeSet ID;
- exact base scene version;
- originating brief ID plus the brief-owned stable target object allowlist;
- `blender` or `unity` target;
- allowlisted property and prior/proposed values;
- validation and rollback plans.

The adapter must expose capability reporting, durable lookup by ChangeSet ID,
dry-run, apply, and validation capture. Supported property families are light intensity/color/temperature,
object visibility, material scalar/color/PBR texture, exposure/post, and camera
settings. The concrete adapter may advertise a strict subset.

The Render Ops executor revalidates the immutable approval snapshot, asks the
core-provided `ChangeSetApprovalVerifier` to confirm the ChangeSet and approver
permissions, checks for an already applied ChangeSet, and only then calls
dry-run before apply. The adapter must reject a stale base version, durably
deduplicate ChangeSet IDs across restarts, return its true execution mode, and
capture fixed-camera validation evidence immediately after apply. A mock
adapter may be used for tests but its result stays `mock`.

## Validation capture

After a successful live apply, capture the same scene version successor,
camera ID/version, renderer version, resolution, recipe, and deterministic pass
set. Validation passes only when:

- changed object/property scope is a subset of the approved operations;
- geometry and fixed camera revisions are unchanged unless explicitly approved;
- protected-region difference stays at or below the declared threshold;
- required AOVs are present and identity-compatible.

Pixel metrics are reported as evidence, never as an artistic-quality score.

## Current status

The protocol, allowlist, mock tests, and validation logic are implemented.
Concrete Blender/Unity adapter extension points and live credentials are absent
from this baseline, so real writeback is `blocked`. Module-runtime catalog and
OpenAPI registration are `planned` until their owning tasks land.
