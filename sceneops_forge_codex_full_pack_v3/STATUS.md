# SceneOps Forge Status

## Active task

- Prompt: `PROMPTS/03_FORGE_SHELL_EDGE_DOCKING.md`
- Base commit: `1d4f0f3`
- State: implementation complete; full verification pending explicit test approval

## Ownership

### Agent: shell_ui_builder (completed)

Owns:

- `modules/forge-shell/**`
- `apps/web/src/shell/**`
- `apps/web/src/registries/**`
- shell-specific tests and documentation under those paths

Must not edit:

- feature editor internals
- external-tool integrations
- core public contracts outside the typed shell contracts owned by `forge-shell`
- other feature-module directories

### Agent: qa_reviewer (completed, read-only)

Audited core contracts, persistence, command safety, Dockview integration, edge UI, and application registries, then completed a second read-only final pass. No files were changed by QA. The principal addressed the reported acceptance blockers in owned paths, including dirty reset protection without lock-in, mutation customization flags, cross-container targeting/no-op rejection, explicit Dockview Peek, and partition-validated snapshot reconstruction.

### Agent: principal (completed)

Owns:

- task coordination and architecture review
- root package/bootstrap files required to run the shell module tests
- `STATUS.md` and `EXECUTION_PLAN.md`
- final integration, verification, documentation truthfulness, and commit

## Execution truth

- `live`: pinned Dockview v8.2 production adapter, edge groups, mutation reconciliation, command/persistence/runtime code, and two post-fix smoke checks.
- `mock`: deterministic editor definitions and shell fixtures used by tests and examples.
- `cached`: none.
- `planned`: generated module-catalog and real feature-editor composition.
- `blocked`: real browser visual/E2E and popout-window verification require the missing application bootstrap. Full tests also require explicit authorization under the current testing rule.

## Completed scope

- Dockview-backed grid, tab, split, edge, floating, popout, maximize, close/reopen, switch, and restore paths.
- Four full-edge pull zones with hidden/Peek/pinned states, resize persistence, pointer cancellation, global Escape, keyboard/menu alternatives, and visible Judge handles.
- Typed editor/workspace/command/event/context contracts, runtime-bound module commands, lazy loading/error recovery, availability states, and hidden-render suspension.
- Atomic replace, dirty confirmation, pane-level lock protection, one-action Judge self-reset, assistant preview/approval boundary, native/programmatic Dockview topology reconciliation, and history frames that include recently closed editors.
- Layout schema v3 validation, v1/v2 migration, invalid-document fallback, invalid-Dockview-snapshot metadata reconstruction with a visible notice, enabled-editor hydration, versioned JSON Schemas, eleven presets, and conversation-only initial Home.

## Verification truth

Before the latest QA-driven changes and before the reduced-test authorization took effect:

- `pnpm run typecheck` — passed.
- `pnpm test` — 19 passed, 0 failed.
- `pnpm run test:bridge` — 2 passed, 0 failed.
- YAML identity and public-entry checks — passed.

After the earlier QA corrections and after the reduced-test rule took effect, only the currently authorized smoke checks were run:

- public entry import — passed.
- Home → open registered tool → validate → save/restore — passed.

Those two smokes predate the final static-review corrections listed above. The expanded module and bridge suites, including all newly added regression cases, are **not run — pending explicit approval**.
