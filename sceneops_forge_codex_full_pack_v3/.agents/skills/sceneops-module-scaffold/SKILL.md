---
name: sceneops-module-scaffold
description: Create or repair one SceneOps Forge feature module with its manifest, nested guidance, frontend/backend entrypoints, tests, fixtures, and docs.
---

# SceneOps Module Scaffold

Use this skill when creating a new feature module or bringing an existing module into compliance.

## Procedure

1. Read root `AGENTS.md`, `MODULE_CONTRACT.md`, and the target module specification.
2. Confirm the module owns a single coherent product capability.
3. Create `modules/<module-id>/` with only the subfolders the capability needs.
4. Add:
   - `module.yaml`;
   - concise module `AGENTS.md`;
   - `README.md`;
   - frontend/backend public entrypoints as required;
   - deterministic fixtures;
   - manifest and dependency tests;
   - module-local usage docs.
5. Declare all module and integration dependencies.
6. Register contributions through generated catalogs, not manual shell switch statements.
7. Run module validation, type checks, tests, and dependency-cycle checks.
8. Return a module handoff with public contracts and next integration step.

## Constraints

- Do not create empty folders for appearance.
- Do not copy root rules into the nested `AGENTS.md`.
- Do not import another module's internals.
- Do not create public abstractions without a consumer.
- Stop if the module requires an unplanned core-contract change.
