# 14 — Versioning, Collaboration, Review, and Four-Layer Diff

## Recommended agent / model

Use `collaboration_release_builder` with Terra/high; use `forge_architect` for diff contracts and `qa_reviewer` before merge.

## Objective

Build a team review layer over Git/LFS that connects comments, assignments, approvals, decisions, asset locks, semantic/visual/behavior diffs, and rollback.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/version-collaboration/**
- Git/LFS adapter integration assigned by principal
- review/collaboration editors/tests/docs

Do not build a new VCS or edit other modules private storage.

## Tasks

1. Integrate Git status, branches, commits, file changes, LFS pointers, and base-version references.
2. Define review sessions, comments, assignments, decisions, approvals, locks, ChangeSet history, and activity timeline.
3. Implement four-layer diff:
   - file diff;
   - semantic 3D/Unity diff;
   - fixed-camera visual diff;
   - behavior/playtest diff.
4. Let comments bind to asset, scene object, code range, render, build, playtest step, or issue.
5. Support follow/pin contexts for side-by-side review editors.
6. Implement safe rollback proposal and approval, not silent reset.
7. Detect conflicts such as changed base version, locked binary asset, deleted target, or incompatible schema.
8. Support asynchronous collaboration; optionally add presence/comments sync if the base is stable.
9. Provide one clear Review workspace and conversation summaries.
10. Link every approved change to evidence and resulting release.

## Acceptance criteria

- A reviewer can understand what changed in files, scene semantics, images, and player behavior.
- Binary files use lock/branch/review rather than unsupported merge magic.
- Approvals and decisions are immutable/auditable.
- Rollback creates a reviewable action and preserves history.
- Review works across the hero and second game.

## Required tests

- Git offline/dirty/conflict states
- LFS pointer metadata
- semantic diff fixtures
- fixed-camera visual diff
- behavior diff
- comment anchors
- approval history
- stale-base rejection
- asset lock
- rollback proposal and execution

## Do not

- Do not replace Git/Perforce.
- Do not claim real-time binary merging.
- Do not allow comments to lose their version/object anchor.
- Do not execute rollback without explicit approval.
- Do not use raw Git output as the only user-facing explanation.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
