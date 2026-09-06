# SceneOps Forge — Apply V5 AI Production Harness Architecture and Plan

You are the principal engineering agent for the existing SceneOps prototype repository.

This task edits the current architecture and implementation plan and then begins implementation. Do not create a parallel app.

## Read first

Read completely:

- root `AGENTS.md`;
- current product, design, module and frontend documents;
- current `STATUS.md` and tests;
- `docs/sceneops-harness-v5/ARCHITECTURE.md`;
- `docs/sceneops-harness-v5/IMPLEMENTATION_PLAN.md`;
- `docs/sceneops-harness-v5/LOCAL_BLENDER_UNITY_TEST_PLAN.md`;
- `docs/sceneops-harness-v5/OPEN_SOURCE_REFERENCE_MATRIX.md`;
- `docs/sceneops-harness-v5/AGENTS_HARNESS_PATCH.md`.

Merge the patch rules into the nearest applicable `AGENTS.md` without duplicating existing rules.

## Product correction

The current prototype may already have:

- a conversation-only home;
- four-edge tool reveal;
- docking and modular Editors;
- 3D tools;
- source/evidence/release concepts.

Preserve working behavior.

The missing core is an AI production Harness:

```text
Intent
→ Context
→ Compile Pipeline
→ Schedule Agents and Models
→ Execute Capabilities
→ Observe
→ Diagnose
→ Adapt
→ Verify
→ Distill
```

Do not count Codex Subagents as product-runtime AI.

## Mandatory first actions

1. Create a Git baseline tag or documented baseline commit.
2. Run existing tests and production build.
3. Create/update:
   - `STATUS.md`;
   - `PROTOTYPE_GAP_MATRIX.md`;
   - `CURRENT_CAPABILITY_CATALOG.md`;
   - `CURRENT_AI_USAGE_AUDIT.md`;
   - `PROTECTED_BASELINE.md`;
   - `HARNESS_MIGRATION_DECISIONS.md`.
4. Classify every current capability:
   - UI only;
   - deterministic capability;
   - AI planning;
   - AI evaluation;
   - AI recovery;
   - governance/evidence.
5. Mark state:
   - Live;
   - Cached;
   - Mock;
   - Partial;
   - Blocked;
   - Missing.
6. Do not stop after planning. Continue into Phase 1 after recording the baseline.

## Architecture migration

### Promote Pipeline to the core

Implement SceneOps-owned contracts and state machines for:

- ProductionIntent;
- ContextBundle;
- CapabilityDefinition;
- CapabilityInvocation;
- PipelineDefinition;
- PipelineStage;
- PipelineStep;
- PipelineRun;
- StepRun;
- ProductionAgentDefinition;
- AgentTask;
- AgentResult;
- AgentHandoff;
- ModelRoutingDecision;
- StepEvaluation;
- FailureAnalysis;
- RecoveryPlan;
- DistilledWorkflow;
- RuntimeBudget.

### Add runtime AI modules

Create vertical modules:

- `ai-intent-compiler`;
- `ai-context-engine`;
- `ai-pipeline-compiler`;
- `ai-agent-runtime`;
- `ai-model-router`;
- `ai-run-observer`;
- `ai-recovery-planner`;
- `ai-run-distiller`.

Use LangGraph or an equivalent library only behind an internal `AgentGraphRuntime` interface. The public Pipeline schema and deterministic runtime remain SceneOps-owned.

### Convert existing modules

Every operational module must register typed Capabilities. An Editor-only module does not count as an execution node.

A Capability declares schemas, risk, permissions, context, evidence, dry-run, rollback, timeout, retry, duration and cost estimates.

## Mandatory local Blender tests

Implement the repository commands and evidence structure specified in `LOCAL_BLENDER_UNITY_TEST_PLAN.md`.

At minimum, in the current local environment:

- detect Blender executable/version;
- run headless smoke;
- install/probe SceneOps add-on;
- inspect reproducible fixture `.blend`;
- assign/preserve `sceneops_id`;
- dry-run, approve and execute one material/light/transform ChangeSet;
- roll it back;
- export GLB and verify actual contents;
- render beauty/depth/normal/object-mask;
- test timeout, cancellation and stale session cleanup.

No Blender capability is `Live` until the relevant local tests pass in this session.

Do not expose arbitrary Python execution.

## Mandatory local Unity tests

Implement the repository commands and evidence structure specified in `LOCAL_BLENDER_UNITY_TEST_PLAN.md`.

At minimum:

- detect the project Unity version and matching Editor;
- use an isolated fixture/project copy for batchmode;
- import and compile the SceneOps UPM package;
- run EditMode tests;
- run PlayMode tests;
- verify `sceneops_id` mapping;
- import/update the key Prefab;
- execute a typed component ChangeSet;
- handle compile and Missing Reference failures;
- create a real local Player build;
- launch the Player with a test plan and collect telemetry;
- test cancellation, timeout, process locks and rollback.

No Unity or Build capability is `Live` until the relevant local tests pass in this session.

Do not expose arbitrary C# execution.

## Open-source policy

You may use or study:

- LangGraph;
- Dockview;
- React Flow;
- Three.js/R3F;
- glTF Validator/Transform;
- blender-ai-mcp;
- unity-mcp;
- Unity Test Framework;
- GameCI;
- OpenTelemetry;
- ComfyUI and image pipeline tools.

But:

- pin versions or commits;
- record licenses;
- wrap connectors in SceneOps adapters;
- run local conformance tests;
- disable unrestricted code execution and unwanted telemetry;
- do not replace SceneOps-owned contracts, control loop, identity, evidence or recovery with third-party abstractions.

## First Live vertical slice

Implement:

```text
User goal: add a key and unlock-home feature
→ Intent Compiler
→ Context Engine
→ Pipeline Compiler
→ runtime Agent assignment and model routing
→ local Blender inspect/change/export
→ asset validation
→ local Unity import/Prefab/scene/logic
→ EditMode and PlayMode tests
→ local Build A
→ goal-driven playtest
→ real designed Issue
→ backpin
→ Observer/RCA
→ RecoveryPlan
→ approved real fix
→ local Build B
→ identical regression test
→ semantic/visual/behavior comparison
→ Run Distiller
```

The AI must be visible in at least:

- intent compilation;
- context selection;
- Pipeline generation;
- Agent assignment;
- model routing;
- implementation/asset planning;
- test generation;
- playtest decisions;
- root-cause diagnosis;
- recovery planning;
- final evaluation;
- workflow distillation.

Do not satisfy this by adding generic AI buttons to Editors.

## Required open-source comparison note

Create `docs/open-source-adoption.md` listing:

- project and pinned version/commit;
- license;
- direct dependency, adapter, fork or reference;
- what is reused;
- what remains custom;
- security changes;
- local conformance result;
- replacement path.

## Required tests

Release blockers:

- contract/state-machine tests;
- capability registry tests;
- Pipeline compiler/cycle/budget tests;
- Agent permission and handoff tests;
- model routing/escalation tests;
- local Blender B0–B8;
- local Unity U0–U8;
- cross-tool X1–X4;
- hero E2E;
- Warehouse Escape E2E;
- Judge Mode reset;
- evidence and claim audit.

## Subagents

Use read-only agents first for repository, AI-usage, integration and security audits.

Assign one writing agent per module folder. The principal owns shared contracts, migration and final integration.

Use the strongest available reasoning/coding model for contracts, Pipeline Compiler, recovery, Blender/Unity and final review. Use standard/fast models for isolated modules, fixtures and docs.

## Completion

Do not declare completion until:

- a user goal compiles into a valid Pipeline;
- product-runtime Agents and model routing are visible;
- local Blender and Unity gates pass;
- at least one Blender-to-Unity path is Live;
- a failure is diagnosed and Recovery alters the path;
- the same test verifies the fix;
- the run is distilled into a reusable template;
- Warehouse Escape reuses it without platform-source changes;
- current evidence supports every claim;
- the conversation-only home and modular shell remain intact.

Begin now with the baseline audit and continue into implementation.
