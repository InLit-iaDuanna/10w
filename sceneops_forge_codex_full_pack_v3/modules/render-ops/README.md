# Render Ops

Render Ops turns a versioned scene and camera into deterministic render passes,
traceable AI-assisted variants, reviewable editable changes, and a validation
render. It is intended for technical artists, lighting artists, reviewers, and
release owners; it does not treat an attractive image as a scene edit.

## Public surface

Editors:

- `render.viewer` — variant/output review with explicit execution mode;
- `render.aov-viewer` — Beauty, Depth, Normal, Albedo, Object ID, and optional
  Material ID inspection;
- `render.recipe` — portable recipe configuration;
- `render.queue` — persistent job state, cancellation, and retry;
- `render.comparison` — fixed-camera and protected-region evidence;
- `render.provenance` — scene, workflow, model, prompt, seed, output, checksum,
  and approval trace.

The public backend package exports the Pydantic contracts, cache planner,
orchestrator, validation functions, and typed writeback interfaces from
`render_ops.__init__`. The command, event, job, and workflow IDs are declared in
`module.yaml`.

Editor persistence stores layout, selection, filter, and context binding only.
Status, error, and execution mode are reapplied from the server snapshot through
`applyServerEditorState`; a restored local value cannot relabel a planned or
mock result as live.

## Data owned

The module owns render briefs, recipes, jobs, AOV references, AI variants,
comparisons, writeback proposals, validation results, and RenderManifest
documents. Source scenes, Blender files, Unity projects, and artifacts remain
owned by their source modules or integrations and are referenced by stable ID.

## Integrations and safety

- Artifact storage is required to retain immutable inputs and outputs.
- ComfyUI, Blender, and Unity are optional. Their absence keeps review and
  deterministic fixtures available while generation or writeback is shown as
  `blocked`.
- ComfyUI runs only a configured workflow reference and checksum through the
  typed adapter in `integrations/comfyui-adapter`; a user cannot submit a file
  path or arbitrary graph.
- Blender/Unity changes are represented as a ChangeSet-like
  `WritebackProposal`. Variant and writeback approvals each record an immutable
  content snapshot. The
  executor requires a core-backed approval verifier, a ChangeSet ID, a render
  brief-scoped object/property allowlist, adapter dry-run, durable ChangeSet
  deduplication, and a fixed-camera validation capture after apply.

## Recipes

`workflows/recipes.v1.json` defines asset turntable, material variant,
lighting/target visibility, fixed-camera regression, and marketing still
recipes. They accept stable scene/camera/object IDs, so Warehouse Escape can use
the same recipes without source changes.

## Execution truth

The committed fixture and tests are deterministic `mock` runs only. This
worktree has no connected Blender, Unity, artifact store, or ComfyUI host, and
contains no prior real render that could truthfully be labelled `cached`.
Consequently:

- schema, cache, queue, comparison, provenance, editor, and safety behavior:
  implemented with deterministic `mock` fixtures and test coverage;
- live ComfyUI generation: `blocked` until a configured service and trusted
  workflow are supplied;
- cached-real replay: `planned` because no prior live artifacts exist;
- live Blender/Unity lighting/visibility writeback and validation: `blocked`
  until those adapters expose the typed extension contract documented in
  `docs/integration.md`.

## Setup and tests

Python 3.9+ and Pydantic 2.13.2 are required. From the repository root:

```bash
PYTHONPATH=modules/render-ops/backend/src:integrations/comfyui-adapter/src \
  python3 -m unittest discover \
  -s modules/render-ops/backend/src/render_ops/tests -v

node --experimental-strip-types --test \
  modules/render-ops/frontend/src/tests/*.test.ts

pnpm --dir modules/render-ops/frontend typecheck
```

The ComfyUI adapter has its own independent test command in its README.

## Example

`contracts/examples/render-manifest.mock.json` demonstrates the complete
manifest chain for a fixed camera. Validate it with:

```bash
PYTHONPATH=modules/render-ops/backend/src \
  python3 -m render_ops.validate_manifest \
  modules/render-ops/contracts/examples/render-manifest.mock.json
```

## Limitations

- No live tool or artifact service was available in this worktree, so the
  required real editable Blender/Unity writeback and live-or-cached-real
  lighting recipe remain blocked rather than simulated.
- Pixel comparison reports deterministic difference and protected-region
  evidence only. Human review still decides artistic quality.
- Core module catalogs and the generated OpenAPI client do not yet exist in
  this standalone specification baseline; registration is declared locally and
  is ready for the module-runtime integration task.
- Live writeback stays blocked until core supplies an authoritative ChangeSet
  approval verifier and the engine adapter proves durable ChangeSet replay.

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。
