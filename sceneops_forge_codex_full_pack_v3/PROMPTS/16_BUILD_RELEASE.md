# 16 — Build, Release Candidate, Deployment, and Rollback

## Recommended agent / model

Use `collaboration_release_builder` or `module_builder` with Terra/high. Use Astra reviewer for release invariants.

## Objective

Build the final production stage that creates reproducible build matrices, release candidates, gates, deployment records, patch notes, and rollback paths.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/build-release/**
- assigned build/deployment adapter files
- release docs/tests/fixtures

Consume Unity build artifacts and cross-module evidence through public contracts.

## Tasks

1. Define BuildMatrix, BuildRun, BuildManifest, ReleaseCandidate, ReleaseGate, Deployment, PatchNote, FeedbackLink, and RollbackPlan.
2. Support Development, QA, Judge, and Release Candidate profiles.
3. Tie builds to commit, module catalog, Project Bible version, asset versions, scene snapshots, Unity version/packages, settings, tests, and checksums.
4. Aggregate blocking gates from asset, scene, code, render, Unity tests, performance, and AI regression.
5. Provide Build Matrix, Console, Gates, Release Center, and Patch Notes editors.
6. Require approvals appropriate to risk/profile.
7. Publish to a local/judge target and record deployment status.
8. Generate patch notes from approved ChangeSets, with human editing.
9. Implement rollback to previous known-good candidate through a typed approved action.
10. Support both example games and cached Judge Mode artifacts.

## Acceptance criteria

- Build A/B and a Release Candidate are reproducible and traceable.
- A blocking gate prevents release.
- Deployment and rollback produce evidence and history.
- Patch notes do not invent unapproved changes.
- Judge build can be opened without manual project repair.
- Second game has an independent release candidate.

## Required tests

- build manifest completeness
- gate aggregation/pass/fail
- stale or missing artifact
- approval requirements
- deployment failure/retry
- patch-note generation/edit
- rollback plan/execution
- previous known-good selection
- mock/cached/live labels
- both example games

## Do not

- Do not publish a release from a dirty or unidentified source state.
- Do not ignore failed blocking gates.
- Do not deploy or roll back without approval.
- Do not treat a cached artifact as a newly live build.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
