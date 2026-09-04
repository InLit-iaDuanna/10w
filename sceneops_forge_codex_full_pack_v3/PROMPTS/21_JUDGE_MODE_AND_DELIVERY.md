# 21 — Judge Mode, One-Click Demo, WorkBuddy Packaging, and Competition Delivery

## Recommended agent / model

Use `module_builder`/`docs_maintainer`; final verification by `qa_reviewer`.

## Objective

Create a stable competition-facing experience that demonstrates the complete workbench quickly, truthfully, and recoverably while packaging reusable skills, docs, and the other-game demo.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/judge-demo/**
- demo fixtures and layouts
- WorkBuddy package/skills
- docs/demo.md, docs/judge-mode.md
- delivery scripts and materials templates

Do not alter core behavior just to fake a smooth demo.

## Tasks

1. Build a one-action Judge Mode from the chat-only home.
2. Make the four edge handles discoverable and provide a guided 60–90 second interaction.
3. Preload the exact editors needed for the hero flow and lock only critical ones.
4. Use cached real artifacts for long renders/builds and run at least one short live operation where available.
5. Show Live/Cached/Mock on every step and artifact.
6. Add one-click reset, deterministic fixture reset, and offline package.
7. Package WorkBuddy Skills, expert roles, connectors/MCP descriptions, and workflows.
8. Include the Warehouse Escape demo and documentation.
9. Generate/update two-page distillation draft, three-minute video shot list, five-minute pitch structure, and booth quick-start.
10. Rehearse failure modes: Blender offline, Unity compile failure, render timeout, playtest timeout, corrupted layout.
11. Record exact setup and reset time.
12. Keep package size and startup practical for the target environment.

## Acceptance criteria

- A stranger can start, pull a tool, inspect evidence, approve one action, and see regression results without author guidance.
- Judge Mode resets in one action.
- Long steps never create awkward unexplained waiting.
- Offline/cached path still demonstrates the production thread honestly.
- WorkBuddy package includes skills/prompts/workflows/docs and the other game.
- Demo materials match the actual implementation.

## Required tests

- Judge Mode E2E
- one-click reset
- cached artifact integrity
- live step fallback
- integration-offline flow
- layout recovery
- clean browser/session run
- other-game launch
- package validation
- docs/demo command verification

## Do not

- Do not hide execution mode.
- Do not rely on the author manually arranging windows.
- Do not require judges to install Blender/Unity/ComfyUI.
- Do not use hard-coded fake measured data.
- Do not sacrifice the normal product for a one-off demo branch.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
