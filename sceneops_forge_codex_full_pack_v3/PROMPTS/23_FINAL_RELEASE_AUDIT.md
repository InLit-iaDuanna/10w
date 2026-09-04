# 23 — Final Release Audit and Completion Decision

## Recommended agent / model

Use principal on Astra and invoke `sceneops-release-review`; reviewers remain read-only until fixes are assigned.

## Objective

Determine objectively whether SceneOps Forge is complete, reproducible, reusable, secure, documented, and ready for competition delivery.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

The principal may update status/release documents and coordinate module-owner fixes. Reviewers do not modify code directly.

## Tasks

1. Verify every item in DEFINITION_OF_DONE.md with direct evidence.
2. Verify fresh launch is chat-only and all four edges work.
3. Verify every declared function belongs to one module folder and manifests match implementation.
4. Verify the hero brief-to-release flow and issue-to-verified-fix loop.
5. Verify at least one Blender and Unity step are live.
6. Verify render writeback, build, structured playtest, backpin, regression, release, and rollback.
7. Verify Warehouse Escape without platform source changes.
8. Verify all Live/Cached/Mock labels and provenance.
9. Verify setup on a clean environment or documented reproducible environment.
10. Verify Judge Mode, reset, offline/cached fallback, and demo materials.
11. Run parallel architecture, security, test, frontend UX, docs, and reuse reviews.
12. Fix all blockers, rerun tests, and write `FINAL_VERIFICATION_REPORT.md`.
13. If any criterion is missing, mark the project incomplete and list the exact gap—do not soften the conclusion.

## Acceptance criteria

- FINAL_VERIFICATION_REPORT.md contains evidence, commands, results, screenshots/artifacts where available, and unresolved risks.
- STATUS.md matches reality.
- The delivery package is reproducible.
- No critical claim lacks evidence.
- The final completion decision is explicit and objective.

## Required tests

Run every release-blocking suite listed in DEFINITION_OF_DONE.md and record exact versions and results. Re-run from a clean state where feasible.

## Do not

- Do not declare success based on module summaries.
- Do not omit failed tests.
- Do not change acceptance criteria at the end.
- Do not hide blocked live integrations.
- Do not present planned features as completed.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
