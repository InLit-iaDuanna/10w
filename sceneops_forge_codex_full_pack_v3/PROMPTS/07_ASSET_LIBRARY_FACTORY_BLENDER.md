# 07 — Asset Library, Asset Factory, and Blender Pipeline

## Recommended agent / model

Use `asset_blender_builder` with Astra/high. Assign fixtures to `fixture_worker` and final security review to `security_reviewer`.

## Objective

Build the game-ready 3D asset pipeline from AssetSpec through Blender processing, validation, versioned publication, and engine-ready outputs.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/asset-library/**
- modules/asset-factory/**
- integrations/blender-addon/**
- Blender adapter files assigned by principal
- related workers/workflows/docs/tests

Coordinate core contract changes with the principal. Do not edit Unity internals.

## Tasks

1. Define AssetSpec, source asset, published AssetVersion, processing step, quality gate, usage reference, and provenance relationships.
2. Build searchable Asset Browser/Inspector with source, version, dimensions, triangles, materials, textures, UV, rig, animations, LOD, collider, license, AI provenance, scenes, and Unity status.
3. Implement safe Blender health, scene/object scan, stable ID assignment, object inspection, transform, normals, material/light parameters, context capture, AOV render, geometry checks, LOD/collider generation where feasible, and export manifest.
4. Restrict all paths to project roots and all operations to typed allowlists. Remove/disable arbitrary Python execution.
5. Create processing workflows: preflight, clean, UV/material check, LOD, collider, turntable/AOV, validate, publish.
6. Generate GLB/FBX plus versioned manifest and checksums.
7. Preserve source asset/object identity and distinguish scene instances.
8. Implement dry-run, approval, progress, cancellation, retry, rollback snapshot, and structured logs.
9. Build live path when Blender is available and deterministic mock/cached path otherwise.
10. Produce the hero key asset and a warehouse obstacle asset fixture.

## Acceptance criteria

- A real or imported key asset reaches a published AssetVersion.
- At least one Blender operation is Live and visible when the tool is available.
- Stable IDs survive export and load into the web viewer.
- Failed blocking quality gates prevent publication.
- Asset records answer where the asset came from, where it is used, and which build includes it.
- The same pipeline accepts another-game assets.

## Required tests

- Blender offline/online health
- path boundary and invalid command
- ID assignment, rename, copy, export/import
- preflight pass/fail
- cancellation/timeout/retry/idempotency
- rollback snapshot
- manifest/checksum/provenance
- publish blocked by gate
- asset browser filters and integration states
- live contract smoke test where available

## Do not

- Do not expose execute-python.
- Do not promise automatic production-quality retopology for arbitrary assets without evidence.
- Do not overwrite source assets without version/snapshot.
- Do not conflate asset identity with scene-instance identity.
- Do not publish failed assets as approved.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
