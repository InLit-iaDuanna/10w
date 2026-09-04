# 00 — Repository Audit and Execution Plan

## Recommended agent / model

Use `code_explorer` in parallel for read-only mapping, then `forge_architect` for architecture consolidation. Principal agent owns all writes.

## Objective

Create an evidence-based map of the existing repository and a phase-by-phase execution plan for the complete SceneOps Forge product.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Allowed writes:
- STATUS.md
- EXECUTION_PLAN.md
- docs/decisions.md
- docs/risk-register.md
- docs/module-map.md
- THIRD_PARTY_NOTICES.md

Do not edit product code in this task.

## Tasks

1. Map every existing app, service, package, module, integration, test, script, and document.
2. Identify duplicated or conflicting architecture from earlier prototypes.
3. Classify every declared product feature as live, cached, mock, planned, blocked, or absent.
4. Map current module ownership and detect code that belongs in a feature module but lives in the shell/shared folders.
5. Identify current stack, build commands, test commands, generated files, and external-tool assumptions.
6. Inventory third-party dependencies, licenses, versions, and unpinned references.
7. Create an ordered dependency graph for the full module catalog.
8. Define phase exit gates and release blockers.
9. List host-level actions that may later require the user: Blender add-on install, Unity package import, ComfyUI launch, credentials, build target modules.
10. Do not merely list files; trace the current execution path from app boot to one user action.

## Acceptance criteria

- STATUS.md is truthful and evidence-based.
- EXECUTION_PLAN.md contains module owners, dependencies, phases, test gates, and a critical path.
- No product code is changed.
- Risks are prioritized by impact and likelihood.
- The next coding task is unambiguous.

## Required tests

- Verify every referenced path exists.
- Run existing read-only status, lint, type-check, and test discovery commands when safe.
- Do not “fix” failures in this task; record exact commands and output summaries.

## Do not

- Do not guess that an empty-looking module works.
- Do not label static UI as implemented backend behavior.
- Do not create a new stack before identifying the current one.
- Do not edit files owned by future implementation agents.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
