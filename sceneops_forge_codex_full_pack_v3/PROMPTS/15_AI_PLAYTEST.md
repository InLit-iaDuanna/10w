# 15 — Structured AI Playtest, Telemetry, Issue Backpin, and Regression

## Recommended agent / model

Use `playtest_builder` with Astra/high. Use `qa_reviewer` for test validity and limitations.

## Objective

Build continuous playtesting that records bounded actions and observations, creates reproducible issues, backpins them to production sources, and reruns identical tests after fixes.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/ai-playtest/**
- assigned Unity runtime telemetry/playtest extension points
- playtest workers, tests, fixtures, docs

Do not edit engine-unity internals outside agreed public interfaces.

## Tasks

1. Define TestCase, AgentMode, Observation, AvailableAction, PlaytestStep, GoalProgress, FailureSignal, EvidenceBundle, Issue, Backpin, and RegressionComparison.
2. Implement deterministic smoke, goal-driven, explorer, and destructive modes; persona modes may remain heuristic and clearly labelled.
3. Bounded actions include movement, look, interact, use item, confirm, cancel, and project-specific registered actions.
4. Record timestamp, build, scene, pose, camera/screenshot, game state, goal, available actions, selected action, target sceneops_id, result, progress, and failure signal for every step.
5. Create Game View, Agent Monitor, Trajectory, Step Log, Issue Browser, and Regression editors.
6. Detect stalls, soft locks, unreachable goals, repeated failed interactions, navigation/collider errors, missing feedback, quest-state mismatch, runtime errors, and performance regressions.
7. Resolve an issue to scene object, asset, component, script, feature, or acceptance criterion with confidence and evidence.
8. Clicking an issue restores scene/object/camera/trajectory/time.
9. Generate a ChangeSet proposal through the owning module, never edit directly.
10. Rerun the exact test configuration and compare before/after without hard-coded improvement.

## Acceptance criteria

- The hero AI player attempts the key-and-door goal and produces structured evidence.
- At least one issue backpins to a real scene or component source.
- The same test reruns after a fix and produces an honest comparison.
- Deterministic smoke tests are stable.
- AI testing is described as pre-screening/regression, not a human replacement.
- Warehouse Escape has its own reusable test configuration.

## Required tests

- action/observation schema
- deterministic seed/replay
- timeout/stall/soft-lock detection
- telemetry loss recovery
- issue creation/backpin
- camera/path restoration
- false/ambiguous backpin state
- same-test regression
- before/after comparison
- build mismatch rejection
- AI limitation labels

## Do not

- Do not output only prose reviews.
- Do not allow unbounded input automation without test controls.
- Do not claim fun, accessibility, or human preference from AI alone.
- Do not hard-code success metrics.
- Do not create fixes inside playtest module.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
