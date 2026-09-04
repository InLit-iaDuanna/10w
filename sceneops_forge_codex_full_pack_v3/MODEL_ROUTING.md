# Codex Model Routing for SceneOps Forge

## 1. Goal

Use expensive reasoning only where it changes correctness. Use faster models for bounded, repetitive, or read-heavy work. The principal agent may adjust models based on actual availability, but must preserve the difficulty tiers.

## 2. Recommended routing

| Tier | Preferred model | Effort | Use |
|---|---|---|---|
| A — Critical | `gpt-6-astra` | high or xhigh | system architecture, module contracts, stable ID, cross-tool semantics, security, final integration |
| B — Complex implementation | `gpt-5.6-sol` | high | docking shell, 3D editor, graphs, render pipeline, difficult module implementation |
| C — Standard implementation | `gpt-5.6-terra` | medium | APIs, database, normal React components, adapters with clear contracts, tests |
| D — Fast support | `gpt-5.6-luna` | low or medium | exploration, fixtures, docs cleanup, repetitive UI, data migration, catalog generation |
| E — Instant micro-task | `gpt-5.3-codex-spark` when available | low | tiny focused iterations with strong tests; never architecture or security |

Fallbacks:

- Astra unavailable → Sol at highest available effort.
- Sol unavailable → Terra at high effort.
- Luna/Spark unavailable → Terra at low/medium effort.

## 3. Route by task, not prestige

Use Astra for:

- module dependency architecture;
- production digital thread;
- Blender/glTF/Web/Unity stable identity;
- ChangeSet and approval invariants;
- job retry/idempotency/rollback semantics;
- security boundaries;
- multi-module integration failures;
- final release review.

Use Sol for:

- chat-first docking shell;
- 3D selection/annotation/camera behavior;
- render and AOV orchestration;
- complex graph editors;
- character/animation integration;
- playtest evidence and backpin UI.

Use Terra for:

- CRUD APIs;
- module routers/services/repositories;
- normal editor components;
- module manifests;
- query hooks;
- standard adapters after contract is frozen;
- unit and integration tests.

Use Luna/Spark for:

- codebase mapping;
- fixture creation;
- docs tables;
- repetitive state components;
- storybook/catalog examples;
- formatting and generated-file checks;
- isolated bug fixes with exact reproduction.

## 4. Mandatory escalation

Escalate to a stronger model when:

- more than two modules require public-contract changes;
- an identity mapping is ambiguous;
- a migration can lose data;
- an adapter can edit/delete production files;
- retries may duplicate side effects;
- a security boundary is unclear;
- the same integration test fails for two different suspected reasons;
- the proposed fix changes architecture to avoid one bug.

## 5. Mandatory de-escalation

Do not use Astra for:

- formatting;
- straightforward fixtures;
- renaming files;
- simple CRUD after contracts are fixed;
- repetitive component states;
- basic documentation cleanup;
- running already-defined test commands.

## 6. Principal-agent model

Run the main orchestration task with Astra when available. If cost or availability is constrained, use Sol high and invoke Astra only for architecture and final review subagents.

## 7. Subagent output contract

Every subagent returns:

```text
Scope completed
Files changed
Contracts changed
Tests run and exact result
Live/Mock/Cached behavior
Risks and assumptions
Integration instructions
Recommended next agent/model
```

Raw logs should remain in artifacts or files, not flood the main thread.
