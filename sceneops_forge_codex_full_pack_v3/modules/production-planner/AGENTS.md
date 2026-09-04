# Production Planner Module Rules

## Ownership

This module owns production-plan drafts, task dependencies, milestones, estimates,
assignments, risks, blockers, acceptance links, planner editors, and planner commands.

It does not own Feature Specs, shared ChangeSet/approval internals, workspace layout,
artifact storage, version control, or any production-tool execution.

## Invariants

- Consume Feature Specs only through `FeatureSpecProjection` or a future declared
  public design-room service that returns the same planner projection.
- Generated plans and assignments are unconfirmed until a human approves the plan.
- Keep predicted estimates beside measured run observations; never overwrite either.
- Reject dependency cycles, missing task/output prerequisites, and impossible
  milestone states before advancing work.
- A task cannot complete until its dependencies, acceptance evidence, and required
  approval are satisfied.
- Opening a task emits a typed `workbench.open_editor` command. It never imports or
  invokes another module's implementation.
- This module never executes Blender, Unity, render, build, test, shell, Git, or file
  mutations.
- Every plan, graph, evidence item, and command result exposes its execution mode.

## Commands

From `modules/production-planner`:

```text
PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/sceneops_production_planner/tests -v
node --experimental-strip-types --test frontend/src/tests/*.test.ts
PYTHONPATH=backend/src python3 backend/scripts/export_contracts.py --check
```

## Generated files

- `contracts/openapi.json`
- `contracts/manifests/feature-planning-snapshot.schema.json`
- `contracts/manifests/production-plan.schema.json`
- `contracts/manifests/production-graph-view.schema.json`
- `contracts/events/production-plan.drafted.v1.schema.json`
- `contracts/events/production-plan.approved.v1.schema.json`
- `contracts/examples/key-door-production-plan.mock.json`
- `frontend/src/generated/contracts.ts`

Regenerate them with `backend/scripts/export_contracts.py`; do not hand-edit them.

## Integration contracts

- Requires future public `core-kernel`, `module-runtime`, and `design-room` modules.
- Receives actor/mode/ChangeSet only from an injected trusted context provider.
- Verifies Approval and measured run timing through typed providers; stores stable references only.
- Repositories use create-if-absent and compare-and-swap plan versions.
- Uses the shell-owned `workbench.open_editor` command for editor handoff.
- The backend Pydantic models and generated OpenAPI document are the network source
  of truth.

## Acceptance tests

Do not remove or weaken the generation fixture, cycle, missing prerequisite,
transition, assignment, estimate provenance, evidence, feature-impact, API failure,
editor-state, or chat/button parity tests.
