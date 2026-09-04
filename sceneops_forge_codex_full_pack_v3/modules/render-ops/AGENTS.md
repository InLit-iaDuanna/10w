# Render Ops Module Rules

## Ownership

This directory owns RenderBrief/recipe/job/manifest contracts, AOV planning and
validation, render queue behavior, AI variant review, approved editable
writeback proposals, deterministic visual validation, render editors, fixtures,
tests, and module-local documentation.

The ComfyUI transport implementation is owned by
`../../integrations/comfyui-adapter/`. Blender and Unity internals remain owned
by their integrations; this module may only call their declared typed adapter
interfaces.

## Invariants

- Every artifact and run carries an explicit `live`, `cached`, `mock`,
  `planned`, or `blocked` execution mode.
- Beauty, depth, normal, albedo, and object-ID passes are the deterministic
  baseline. Material ID is recipe-dependent.
- Scene, camera, object identity, recipe, workflow, model, prompt, seed, and
  checksums remain attached to every AI variant.
- An AI image is never a scene mutation. Only an approved ChangeSet containing
  allowlisted editable properties may reach a Blender or Unity adapter.
- Prompt-only changes reuse compatible AOVs. Geometry or camera changes
  invalidate all required passes.
- Fixed-camera pixel metrics are evidence of visual difference, not a measure
  of artistic quality.

## Commands

Run backend tests from the repository root:

```bash
PYTHONPATH=modules/render-ops/backend/src:integrations/comfyui-adapter/src \
  python3 -m unittest discover \
  -s modules/render-ops/backend/src/render_ops/tests -v
```

Run frontend contract/editor tests:

```bash
node --experimental-strip-types --test \
  modules/render-ops/frontend/src/tests/*.test.ts

pnpm --dir modules/render-ops/frontend typecheck
```

## Generated files

`contracts/manifests/render-manifest.v1.schema.json` is generated from
`render_ops.schemas.RenderManifest` by `render_ops.schema_export`. Never edit it
by hand.

## Acceptance boundary

The module tests may use deterministic mock adapters, but documentation and UI
must not call those runs live. A real writeback is complete only when an
approved ChangeSet is executed by a connected Blender or Unity adapter and a
live validation capture passes.
