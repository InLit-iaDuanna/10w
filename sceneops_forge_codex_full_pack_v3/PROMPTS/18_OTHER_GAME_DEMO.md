# 18 — Other Game Demo: Warehouse Escape

## Recommended agent / model

Use a Terra module builder for project assets/config and Astra/Sol for integration failures. Do not change platform code casually.

## Objective

Prove reusability by running the same SceneOps Forge platform and workflows on a distinct compact 3D game without modifying product source code.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- examples/warehouse-escape/**
- project-specific configuration/fixtures/tests/docs
- no edits to SceneOps modules unless a genuine reusable defect is found and separately reviewed.

## Tasks

1. Create/import a minimal Unity game with room, switch, door, obstacle, exit, player controller, and victory condition.
2. Define Project Bible, Feature Specs, policies, assets, scene graph, and test cases using the same public schemas.
3. Publish or import assets through the same asset pipeline.
4. Build gameplay through the same interaction/state templates.
5. Produce a real build.
6. Run deterministic and goal-driven tests.
7. Introduce or use a controlled collider/NavMesh defect.
8. Create a structured issue and backpin to the obstacle/collider or navigation source.
9. Generate, approve, execute, rebuild, and regress the fix.
10. Record onboarding time and only measured results.
11. Add a one-click Judge Mode path and reset.
12. Document exactly which configuration differs from Find My Way Home.

## Acceptance criteria

- No platform source changes are needed for normal project onboarding.
- The game is visually/mechanically distinct enough to prove reuse.
- A real build and issue-to-fix regression exist.
- Same module/workflow IDs are used.
- Project-specific object names do not appear in platform templates.
- Setup and demo instructions are reproducible.

## Required tests

- project schema compatibility
- asset/scene import
- build smoke
- playtest test case
- controlled defect
- backpin/fix/regression
- one-click reset
- “no platform source changes” guard/diff check
- cached Judge Mode flow

## Do not

- Do not make a simple reskin of the hero game.
- Do not copy platform code into the example.
- Do not silently add project names to generic recipes.
- Do not claim reuse based only on configuration files without a running build.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
