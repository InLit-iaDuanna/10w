# 17 — Main Hero Flow Integration: Key to Release

## Recommended agent / model

Run with the principal agent using Astra. Spawn read-only explorers/reviewers and bounded module builders; principal owns integration.

## Objective

Integrate the complete Find My Way Home key-and-door feature from conversation brief to verified release candidate across all production modules.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

The principal may edit integration fixtures, workflow definitions, cross-module tests, and explicitly assigned public contracts. Module internals remain owned by their agents; request fixes through those owners when possible.

## Tasks

1. Enumerate the full command/event/artifact chain and correlation IDs.
2. Run the flow first with deterministic mock adapters.
3. Replace boundaries with live Blender, live Unity, and live/cached AI render one at a time.
4. Ensure conversation creates the feature and opens relevant tools.
5. Generate production tasks and concept/AssetSpec.
6. Publish the key AssetVersion and import/match it in Unity.
7. Place the key, wire gameplay, UI, audio, and optional VFX.
8. Render and review visibility.
9. Build A and run structured playtest.
10. Create/backpin a real or controlled issue.
11. Generate/approve/execute a fix.
12. Build B and rerun exactly the same test.
13. Produce four-layer before/after evidence.
14. Create Release Candidate and optional rollback proof.
15. Make every long step resumable and every mode truthful.
16. Build a Judge Mode cached path from real artifacts where available.

## Acceptance criteria

- The flow can be started from the chat-only home.
- Every major step opens in a dedicated modular editor on demand.
- The same correlation chain connects brief, task, asset, scene, build, playtest, issue, fix, and release.
- At least Blender and Unity have live steps.
- AI render produces editable writeback.
- Regression uses identical test configuration.
- Failure and resume paths are demonstrable.
- No module-specific hack is hidden in shell code.

## Required tests

- full Playwright hero flow in mock mode
- API/integration hero flow
- live Blender smoke path
- live Unity build path
- cached render path replay
- approval pause/resume
- external-tool offline and resume
- issue backpin
- same-test regression
- release/rollback
- Judge Mode reset

## Do not

- Do not bypass modules to make the demo work.
- Do not hard-code measured improvement.
- Do not hide failed or cached steps.
- Do not modify module public contracts ad hoc during integration.
- Do not call the project complete before this flow passes.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
