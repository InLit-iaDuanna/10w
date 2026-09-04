# 12 — RenderOps, AOV, AI LookDev, Writeback, and Validation

## Recommended agent / model

Use `render_ops_builder` with Sol/high and a read-only `security_reviewer` for external workflow boundaries.

## Objective

Build a production-oriented render module that uses deterministic 3D context, AI-assisted variants, approval, editable writeback, and validation rather than a screenshot-to-image toy.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/render-ops/**
- integrations/comfyui-adapter/**
- assigned render workers and Blender/Unity render commands
- render docs/tests/fixtures

Do not edit general Blender/Unity adapter internals outside assigned extension points.

## Tasks

1. Define RenderBrief, RenderRecipe, deterministic pass set, RenderJob, variant, comparison, writeback proposal, validation result, and RenderManifest.
2. Build Render Viewer, AOV Viewer, Recipe, Queue, comparison, and provenance editors.
3. Capture Beauty, Depth, Normal, Albedo, Object ID/Mask, and optional Material ID from a versioned scene/camera.
4. Integrate ComfyUI or compatible service via HTTP adapter with workflow reference/hash, enqueue, progress, cancel, output retrieval, and errors.
5. Implement recipes: asset turntable, material variant, lighting/target visibility, fixed-camera regression, and marketing still; at least lighting/visibility must be live or cached-real.
6. Constrain variants with depth/normal/object masks where relevant.
7. Convert approved variants into typed editable proposals: light intensity/color/temperature, material parameters/PBR textures, exposure/post, or camera settings.
8. Apply only through ChangeSet and adapter allowlists.
9. Run deterministic validation render and compare scope, protected regions, and visual differences.
10. Add dependency-aware cache: prompt-only changes reuse AOV; geometry/camera changes invalidate required passes.

## Acceptance criteria

- AI rendering is linked to exact scene version, camera, object IDs, recipe, workflow, model, seed, prompt, outputs, checksum, and approval.
- At least one approved result changes real editable Blender or Unity data.
- A deterministic validation render proves what changed.
- Cancel/retry/cache and offline behavior work.
- The same recipes can be used by the second game.

## Required tests

- RenderManifest schema
- invalid/missing AOV
- Comfy offline/timeout/cancel/retry
- cache invalidation matrix
- live/mock/cached labels
- writeback allowlist and approval
- protected-region/geometry unchanged check
- fixed-camera diff
- provenance completeness
- hidden editor queue persistence

## Do not

- Do not treat an AI image as a scene change without writeback.
- Do not allow unrestricted Comfy workflow file execution from untrusted input.
- Do not lose model/workflow/seed/prompt provenance.
- Do not rerender all passes when inputs prove they are reusable.
- Do not claim pixel difference alone measures artistic quality.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
