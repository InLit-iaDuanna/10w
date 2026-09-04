# 05 — Production Planner and Task Dependency Graph

## Recommended agent / model

Use `product_graph_builder` with Sol or Terra/high.

## Objective

Turn Feature Specs into an editable production graph of tasks, dependencies, owners, agents, milestones, risks, estimates, and acceptance evidence.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/production-planner/**
- planner-specific contracts/events/workflows
- planner editors/tests/docs

Consume Feature Specs through public contracts only.

## Tasks

1. Define ProductionTask, TaskDependency, Milestone, Estimate, Risk, Assignment, Blocker, and Deliverable linkages.
2. Generate draft tasks from a Feature Spec for design, concept, asset, animation, world, logic, UI, audio, VFX, render, build, and test work.
3. Keep generated tasks editable and explicitly unconfirmed until approved.
4. Visualize dependency graph, critical path, blockers, human/agent assignment, and milestone readiness.
5. Support task comments, status transitions, approval requirements, and downstream artifact links.
6. Detect missing prerequisites and dependency cycles.
7. Use actual run data to update estimates; keep model estimates distinct from measured values.
8. Link every task to acceptance criteria and evidence.
9. Add a one-action “create production plan” command usable from chat.
10. Build the task plan for the key-and-door hero feature.

## Acceptance criteria

- The key-and-door feature expands into a coherent, editable task graph.
- Every task has owner, inputs, outputs, acceptance, and dependencies.
- Cycles and impossible milestone states are blocked.
- Estimates are labelled predicted or measured.
- Opening a task can summon the relevant editor through typed commands.

## Required tests

- task generation fixture
- cycle detection
- missing prerequisite
- status transition
- human/agent assignment
- predicted vs measured estimate
- acceptance evidence linkage
- feature change impact on plan
- chat command parity

## Do not

- Do not build a generic enterprise project-management clone.
- Do not fabricate exact productivity gains.
- Do not let planning tasks directly execute production tools.
- Do not duplicate version-control or approval internals.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
