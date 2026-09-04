# 01 — Core Contracts, Module Runtime, and Scaffold

## Recommended agent / model

Use `forge_architect` for contracts and `module_runtime_builder` for implementation. Serialize writes to shared contracts.

## Objective

Establish the stable core kernel, module schema, generated registries, module scaffolding, and dependency validation that every later feature will use.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- packages/core-contracts/**
- packages/core-events/**
- modules/core-kernel/**
- modules/module-runtime/**
- scripts/module-*/**
- generated module catalog files
- related docs/tests

Do not edit business modules except to create minimal compliant manifests when required for registry tests.

## Tasks

1. Define core IDs, execution modes, standard errors, actor references, artifact/provenance, command/event envelopes, approval primitives, job/run primitives, and WorkbenchContext identifiers.
2. Keep domain-specific schemas out of core.
3. Define `module.yaml` JSON Schema and validation diagnostics.
4. Implement build-time module discovery and deterministic frontend/backend catalogs.
5. Validate duplicate IDs, missing entrypoints, undeclared dependencies, cycles, permissions, feature flags, editor IDs, command IDs, event versions, and job IDs.
6. Implement a module scaffold command that creates only needed folders and concise nested AGENTS.md/README templates.
7. Add public entrypoint rules and import-boundary enforcement.
8. Add module enable/disable and missing-integration metadata.
9. Generate `docs/module-map.md` from manifests.
10. Create sample modules for `core-kernel`, `module-runtime`, and one tiny fixture module to prove registration.

## Acceptance criteria

- A new module can be scaffolded, validated, registered, disabled, and tested independently.
- The app and API can consume generated catalogs without hard-coded feature switches.
- Dependency cycles and undeclared imports fail with readable messages.
- Core contracts are small, stable, versioned, and documented.
- Generated files are clearly marked and reproducible.

## Required tests

- schema valid/invalid fixtures
- duplicate ID tests
- dependency cycle tests
- missing entrypoint tests
- feature flag tests
- registry generation snapshot tests
- public import boundary tests
- event/version compatibility tests
- scaffold smoke test

## Do not

- Do not create an unrestricted runtime plugin loader.
- Do not put every domain entity in core.
- Do not hand-maintain duplicate frontend and backend catalogs.
- Do not use reflection or dynamic imports that hide build failures.
- Do not build business UI in this task.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
