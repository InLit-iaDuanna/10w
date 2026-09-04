# 13 — Unity EngineOps, Identity Mapping, Prefabs, Tests, Profiling, and Builds

## Recommended agent / model

Use `unity_engine_builder` with Astra/high. Use `security_reviewer` after the adapter and package are complete.

## Objective

Build the safe Unity integration and engine module that turns published assets and gameplay specs into mapped Prefabs, playable scenes, tests, profiles, and real builds.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/engine-unity/**
- integrations/unity-package/**
- Unity adapter and build-worker files assigned by principal
- Unity docs/tests/fixtures

Coordinate cross-module contracts through principal. Do not edit Blender or render internals.

## Tasks

1. Implement Unity Package with SceneOpsIdentity, source asset/version references, scene-instance identity, import hooks, telemetry bridge, and command handlers.
2. Implement safe adapter commands: health, scan project, import asset, map identity, create/update Prefab, inspect GameObject, set allowlisted component property, add/update collider, NavMesh operation, enter/exit play, capture, read console, run tests, profiler snapshot, build.
3. Disable arbitrary C# execution.
4. Validate target project root, command schemas, permissions, and version compatibility.
5. Map Blender/export manifest to Unity assets/Prefabs/GameObjects and preserve relationships.
6. Build asset import settings, material mapping, collider/LOD/component setup, and meaningful errors.
7. Implement Edit Mode/Play Mode test integration and build artifact manifest.
8. Implement hero key Prefab, scene placement, logic linkage, and Build A/B.
9. Implement Warehouse Escape build.
10. Support dry-run, approval, cancellation, timeout, retry, logs, and rollback/restore proposal.

## Acceptance criteria

- Unity produces at least one real playable build.
- Identity maps from published asset to Prefab and scene instance, and appears in telemetry.
- Unsafe commands are impossible through the application interface.
- Compile/test/build failures are visible, retryable where valid, and preserve logs.
- Builds have immutable manifests linking source, assets, settings, and tests.
- The module works with both example games.

## Required tests

- health/capability/version
- project-root path boundary
- command allowlist
- import identity mapping
- rename/copy/prefab instance relationships
- missing material/script/reference
- component ChangeSet dry-run/approval
- compile/test failure
- build cancel/retry
- build manifest/provenance
- real smoke test where Unity is available

## Do not

- Do not expose execute-C#.
- Do not commit Unity Library or caches.
- Do not mutate a project without a ChangeSet and base version.
- Do not identify objects by names alone.
- Do not call a build real if it is only a UI fixture.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
