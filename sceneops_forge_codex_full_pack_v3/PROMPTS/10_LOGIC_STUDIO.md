# 10 — Gameplay Logic, State Graph, Quests, Dialogue, and Code Change Flow

## Recommended agent / model

Use `world_logic_builder` with Astra/high for state and safety; use Terra for normal editors/APIs.

## Objective

Create a logic-production module that turns approved Feature Specs into inspectable gameplay graphs, typed component changes, reviewed code diffs, tests, quests, and dialogue state.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/logic-studio/**
- logic-specific contracts/workflows/tests/docs
- assigned Unity code-generation adapter interfaces

Do not bypass engine-unity safety boundaries.

## Tasks

1. Define GameplayGraph nodes/edges, state variables, events, conditions, effects, interaction relationships, quest nodes, dialogue nodes, code-change proposal, and generated-test references.
2. Build Feature, State Graph, Interaction Graph, Quest/Dialogue Graph, Code Diff, and Test Case editors.
3. Compile common interactions to data-driven configurations where possible.
4. When C# is needed, generate a branch/diff ChangeSet, run compile/tests, require approval, and preserve rollback.
5. Implement the key pickup, inventory, locked door, quest progress, feedback, and ending behavior for the hero flow.
6. Detect unreachable states, dead branches, cycles without exit, missing references, conflicting effects, and unsatisfied acceptance criteria.
7. Link every state/interaction to scene objects through stable IDs.
8. Generate Edit Mode, Play Mode, and structured behavior tests.
9. Keep model explanations separate from deterministic graph validation.
10. Support Warehouse Escape switch-door logic through the same templates.

## Acceptance criteria

- The hero gameplay can be represented, edited, validated, tested, and built.
- Graph changes produce meaningful diffs.
- Code changes are never silently written or merged.
- Deterministic validators find unreachable or inconsistent states.
- A second project reuses the same interaction templates.

## Required tests

- graph serialization/versioning
- unreachable/dead-state detection
- condition/effect validation
- stable object linkage
- C# ChangeSet approval
- compile/test failure
- rollback
- key-door behavior test
- warehouse switch-door test
- conversation command to open relevant logic

## Do not

- Do not generate arbitrary C# and execute it without review.
- Do not use an LLM as the only graph validator.
- Do not hard-code hero-project object names in templates.
- Do not create duplicate state sources in code and graph without an explicit compilation relationship.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
