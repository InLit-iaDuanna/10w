# 02 — Chat-Only Home and Typed Assistant Actions

## Recommended agent / model

Use `shell_ui_builder` for UI and `forge_architect` only if command contracts need review.

## Objective

Implement the initial SceneOps experience in which the fresh home contains only the conversation editor and subtle four-edge pull affordances.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/conversation-home/**
- assistant action contracts assigned by the principal
- conversation fixtures/tests/docs
- minimal app boot integration needed to show the conversation editor

Do not implement general docking internals owned by `forge-shell`.

## Tasks

1. Build `assistant.conversation` as a registered lazy editor.
2. Create the zero-dashboard empty state, conversation history, composer, project/scene context chips, file/project drop, cancel, and accessible keyboard behavior.
3. Define typed assistant actions for opening tools, creating projects/features, running workflows, opening artifacts/issues, and requesting approvals.
4. Route every action through the same WorkbenchCommandBus used by buttons and menus.
5. Add layout-action preview and explicit confirmation for material workspace rearrangement.
6. Support structured progress, artifact, error, approval, and “open in tool” cards.
7. Add slash-command and command-search handoff without duplicating command definitions.
8. Persist conversation per project and preserve a temporary pre-project conversation.
9. Add Live/Mock/Cached mode display.
10. Ensure no module auto-opens on fresh launch without saved layout, deep link, or Judge Mode.

## Acceptance criteria

- Fresh launch shows conversation only, not a dashboard/sidebar/inspector/console.
- A user can ask “open the 3D view on the right,” preview the change, confirm, and invoke the typed command.
- Failed and unavailable actions explain permissions/integrations and offer valid next actions.
- Assistant actions cannot bypass approval or permissions.
- Conversation remains usable when docked, tabbed, resized, or maximized.

## Required tests

- chat-only initial fixture
- typed action validation
- command parity between chat and button
- layout-change confirmation
- action permission/integration failure
- stream cancel/retry
- project and pre-project persistence
- mock/cached/live labels
- accessibility keyboard flow

## Do not

- Do not add a dashboard.
- Do not implement tool behavior inside chat.
- Do not let natural-language text directly execute shell/tool commands.
- Do not silently rearrange a saved workspace.
- Do not create a second command system for assistant actions.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
