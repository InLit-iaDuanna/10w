# SceneOps Forge — Module Implementation Prompt Template

You own exactly one module for this task.

## Module

- ID: `<module-id>`
- Goal: `<one coherent product capability>`
- Allowed files: `modules/<module-id>/**` plus `<explicit shared files>`
- Forbidden files: `<other module internals and unassigned core files>`
- Required public contracts: `<list>`
- Required integrations: `<list>`
- Recommended agent/model: `<agent / tier>`

## Instructions

1. Read all root governing docs, current status/plan, and the module's nearest `AGENTS.md`, README, manifest, tests, and docs.
2. Audit existing module code and do not duplicate working behavior.
3. Implement one complete vertical slice, including:
   - module manifest contribution;
   - editor/command/API/job as required;
   - success, loading, empty, failure, offline, permission, retry states;
   - deterministic fixture;
   - tests;
   - module docs;
   - Live/Mock/Cached labels.
4. Use only public module interfaces. No internal cross-module imports.
5. Use generated network types and shared command/event/context contracts.
6. Do not change public contracts without stopping and requesting principal review.
7. Keep source files and functions focused; avoid speculative abstractions.
8. Run module validation, lint, type check, unit, integration, and relevant E2E tests.
9. Update STATUS.md only for facts verified by tests or direct execution.

## Acceptance criteria

- `<criterion 1>`
- `<criterion 2>`
- `<criterion 3>`

## Return

- scope completed;
- files changed;
- public contracts changed;
- tests and exact results;
- live/mock/cached behavior;
- known risks;
- integration instructions;
- next recommended task.
