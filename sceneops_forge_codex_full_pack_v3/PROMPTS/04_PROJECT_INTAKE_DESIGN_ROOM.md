# 04 — Project Intake, Project Bible, GDD, and Feature Specs

## Recommended agent / model

Use `product_graph_builder` or `module_builder` with Terra/medium; use `forge_architect` for public contract changes.

## Objective

Create the project-entry and design modules that turn a conversation brief or imported project into structured, editable, versioned production intent.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/project-intake/**
- modules/design-room/**
- related domain contracts approved by principal
- module docs/tests/fixtures

Do not edit asset, Unity, or Blender integrations.

## Tasks

1. Support new-project and existing-project intake.
2. Capture target platform, engine, DCC, project roots, team roles, style goals, performance budgets, and integration requirements.
3. Build Project Bible editor for game goal, player, core loop, visual/audio/interaction rules, naming, platform budgets, prohibited changes, and approved decisions.
4. Build GDD and Feature Spec editors with structured states, inputs, outputs, dependencies, edge cases, acceptance criteria, required assets, scenes, scripts, UI, audio, VFX, and tests.
5. Convert conversation actions into draft specs, never directly into production mutations.
6. Add decision records showing accepted/rejected alternatives and rationale.
7. Link imported project scan results without leaking adapter SDK types.
8. Add version history and diff for Project Bible and Feature Specs.
9. Create fixtures for Find My Way Home and Warehouse Escape.
10. Emit typed events consumed by production planning.

## Acceptance criteria

- A user can create a project entirely from chat and then open structured editors.
- A user can import/scan an existing project and see clearly which fields are inferred, confirmed, or missing.
- Feature Specs are actionable and linked to acceptance criteria and downstream requirements.
- No AI-generated assumption is silently marked confirmed.
- Specs are versioned and diffable.

## Required tests

- new-project flow
- existing-project partial scan
- validation for missing target platform/root
- inferred vs confirmed fields
- Feature Spec version/diff
- decision accept/reject
- conversation-to-draft command
- permission and integration-offline states
- module-disabled behavior

## Do not

- Do not turn GDD into a single unstructured markdown blob.
- Do not let project intake edit production files.
- Do not infer critical platform or path settings without confirmation.
- Do not duplicate task-planning behavior owned by production-planner.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
