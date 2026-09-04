# 09 — World Composer, 3D Annotations, Paths, and Level Production

## Recommended agent / model

Use `world_logic_builder` with Astra/high for identity/annotation semantics and Sol/high for UI implementation.

## Objective

Build the central 3D world-production module for scene understanding, object placement, spatial annotations, regions, paths, navigation, lighting, graybox, and level validation.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/world-composer/**
- packages/scene-viewer/** assigned sections
- world-specific Blender/Unity adapter commands through approved public protocols
- docs/tests/fixtures

Do not own gameplay code generation internals.

## Tasks

1. Build 3D Viewport, Scene Outliner, Object Inspector, Annotation List, World Graph, Path/Region, NavMesh, and Lighting editors.
2. Implement Stable Scene ID loading and selection synchronization.
3. Support object pin, surface pin, point, region volume, path trace, relation link, state annotation, sketch annotation, and voice-to-draft annotation.
4. Store object/local/world position, normal, camera, scene version, author, problem, intent, constraints, acceptance, evidence, and game state.
5. Implement object placement from Asset Browser through a typed ChangeSet.
6. Build scene graph, zones, interaction regions, path data, lighting targets, and navigation overlays.
7. Add fixed-camera capture, issue camera restoration, synchronized comparison view, and overlay registry.
8. Support graybox and procedural placement only through clear recipes/constraints.
9. Add level checks for missing collider, overlapping spawn, unreachable target, NavMesh break, invalid scale, and missing interaction relationship.
10. Integrate the key placement and home entrance in the hero flow.

## Acceptance criteria

- The 3D viewport is the dominant professional editor when opened.
- An annotation carries enough context for AI and humans to act without a separate screenshot explanation.
- Asset drag/drop creates a reviewable ChangeSet and preserves identity.
- An Issue can restore scene, object, camera, path, and evidence.
- Hidden or inactive viewports suspend rendering.
- The module works with both demo projects.

## Required tests

- ID selection and rename/copy behavior
- all annotation types serialize/restore
- local/world conversion and normal
- camera restoration
- context follow/pin
- drag asset to scene ChangeSet
- overlay registry
- NavMesh/path issue fixture
- 3D resize/hidden suspension
- scene gate pass/fail

## Do not

- Do not store annotations only as screenshots or world coordinates.
- Do not mutate Unity/Blender directly from the viewer.
- Do not keep WebGL resources in global serializable state.
- Do not create procedural content without a reproducible recipe.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
