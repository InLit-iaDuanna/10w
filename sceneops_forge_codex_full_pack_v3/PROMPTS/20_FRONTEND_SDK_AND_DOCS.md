# 20 — Frontend Module SDK, Tool-Window Developer Guide, and Documentation

## Recommended agent / model

Use `docs_maintainer` with Luna/medium and `shell_ui_builder` for code examples that must compile.

## Objective

Make the modular frontend genuinely easy to extend by delivering a small SDK, examples, scaffolding, and accurate integration documentation.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- packages/module-sdk or the approved equivalent
- frontend extension docs
- module template/example
- generated catalogs/examples
- documentation validation tests

Do not redesign product modules.

## Tasks

1. Document and implement the smallest supported public APIs for ModuleContribution, EditorDefinition, WorkbenchCommand, WorkbenchEvent, WorkbenchContext, ToolLibraryEntry, workspace preset contribution, editor-local state, and scene overlays.
2. Provide a scaffold command/skill for a new module and a new editor.
3. Create a minimal example module that opens from chat and an edge drawer, consumes context, calls a typed API, handles offline/failure, and saves local state.
4. Document how to add a module without editing ForgeShell.
5. Document how to add a workspace preset, command, event consumer, overlay, and integration requirement.
6. Include frontend/backend file map, generated-code boundaries, test commands, and troubleshooting.
7. Add API and event examples copied from actual schemas.
8. Validate code snippets in CI where feasible.
9. Explain how to modify design tokens and maintain accessibility.
10. Explain popout constraints and multi-window context synchronization.

## Acceptance criteria

- A new developer can add a module and tool window from docs without guessing shell internals.
- The example module compiles and tests.
- Generated files and hand-written files are clear.
- Every public extension point has one concise example.
- Documentation matches actual paths and commands.

## Required tests

- scaffold smoke test
- example module registration
- editor open from chat/drawer
- local state restore
- context follow/pin
- integration missing state
- docs link/path validation
- code example compilation where supported

## Do not

- Do not document planned APIs as real.
- Do not create a huge generic plugin framework.
- Do not make developers touch shell internals for normal additions.
- Do not duplicate generated API types in examples.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
