# SceneOps AI Production Harness Architecture

Version: 5.0  
Status: Target architecture for retrofit of the existing prototype

---

## 1. Architecture decision

SceneOps is no longer defined as a Blender-like shell containing many AI tools.

It is defined as:

> **An AI-native production harness for 3D games: a user describes a playable goal; the system compiles a production pipeline, schedules specialist agents, invokes Blender and Unity through deterministic local adapters, observes every result, diagnoses failures, adapts the remaining run, and delivers a verified playable build.**

The Blender-like, conversation-first interface remains, but it is the **experience shell**, not the product core.

The product core is the loop:

```text
Intent
→ Context
→ Compile Pipeline
→ Schedule Agents and Models
→ Execute Capabilities
→ Observe
→ Diagnose
→ Recover or Continue
→ Verify
→ Distill into Template and Skill
```

The evidence system remains mandatory:

```text
Canonical Source
→ Operation Record
→ Output Artifact
→ Runtime Evidence
→ Functional / Visual / Performance / Package Verdicts
→ Claim Audit
```

---

## 2. Goals and non-goals

### Goals

1. Make the Pipeline the first-class runtime object.
2. Make every existing feature module an AI-callable Capability Provider, not only an Editor.
3. Use runtime specialist Agents inside the product; Codex development Subagents do not count as product AI.
4. Require real local Blender and Unity execution before claiming Live support.
5. Support human approval, retries, rollback, evidence and exact failure semantics.
6. Preserve a conversation-only first screen and four-edge dockable workspace.
7. Preserve vertical feature modules and clean frontend integration.
8. Run the same templates on at least two different games.

### Non-goals

- Replacing Blender or Unity.
- Building a general-purpose no-code automation platform.
- Letting an LLM execute arbitrary Python, C#, shell or filesystem operations.
- Treating a generated 2D render as an editable 3D result.
- Claiming AI playtesting replaces human player research.
- Using an open-source project as the entire product with a new skin.

---

## 3. System overview

```text
┌───────────────────────────────────────────────────────────────────┐
│ Experience Layer                                                  │
│ Conversation Canvas · Pipeline Studio · Dockable Editors          │
│ Agent Decisions · Approvals · Evidence · Version/Run Comparison   │
└──────────────────────────────┬────────────────────────────────────┘
                               │ typed commands / events
┌──────────────────────────────▼────────────────────────────────────┐
│ AI Control Plane                                                  │
│ Intent Compiler · Context Engine · Pipeline Compiler              │
│ Agent Runtime · Model Router · Observer/Evaluator                 │
│ RCA + Recovery Planner · Run Distiller                            │
└──────────────────────────────┬────────────────────────────────────┘
                               │ validated PipelineDefinition
┌──────────────────────────────▼────────────────────────────────────┐
│ Harness Kernel                                                    │
│ Capability Registry · Connectors · Environments · Secrets         │
│ Pipeline/Stage/Step Runtime · Policy Gates · Approval             │
│ Checkpoints · Retry · Cancellation · Rollback · Templates         │
└──────────────────────────────┬────────────────────────────────────┘
                               │ CapabilityInvocation
┌──────────────────────────────▼────────────────────────────────────┐
│ Deterministic Execution Plane                                     │
│ Blender Local Bridge · Unity Local Bridge · ComfyUI Adapter       │
│ Git/Artifact Store · Build Runner · Player/Test Runner            │
└──────────────────────────────┬────────────────────────────────────┘
                               │ facts / logs / artifacts
┌──────────────────────────────▼────────────────────────────────────┐
│ Governance, Evidence and Learning                                 │
│ Source Registry · Evidence Ledger · Visual QA · Capability Matrix │
│ Provenance · Release Gate · Claim Audit · Run Memory/Distillation │
└───────────────────────────────────────────────────────────────────┘
```

---

## 4. Hybrid runtime decision

SceneOps uses a hybrid runtime rather than delegating the entire system to one framework.

### 4.1 Agent control graph

Use LangGraph, or an equivalent stateful agent graph behind an internal interface, for:

- intent clarification;
- context selection;
- pipeline proposal;
- agent handoffs;
- observation and diagnosis loops;
- recovery planning;
- human interrupt and resume;
- run distillation.

Do not expose LangGraph types as public product contracts.

### 4.2 Deterministic pipeline runtime

Build a small SceneOps-owned runtime for:

- persisted Pipeline, Stage and Step state;
- external process execution;
- local Blender and Unity locks;
- typed CapabilityInvocation;
- retry, timeout and cancellation;
- artifact and log capture;
- approval gates;
- checkpoint and rollback references;
- evidence binding.

The product's canonical object is `PipelineDefinition`, not a LangGraph graph object.

### 4.3 Why hybrid

Agent reasoning and tool execution have different reliability requirements:

- AI graphs need state, branching, memory and human interrupts.
- Blender/Unity jobs need exact commands, process locks, filesystem isolation, logs, exit codes and reproducibility.
- Keeping the contracts separate allows replacing the agent framework without rewriting local tool adapters.

---

## 5. Core runtime contracts

### 5.1 ProductionIntent

```ts
interface ProductionIntent {
  id: string;
  projectId: string;
  goal: string;
  desiredOutcome: string;
  constraints: Constraint[];
  protectedBaseline: ResourceRef[];
  acceptanceCriteria: AcceptanceCriterion[];
  budget: RuntimeBudget;
  deadline?: string;
  allowedMutationScopes: MutationScope[];
  forbiddenMutationScopes: MutationScope[];
  requestedArtifacts: ArtifactRequest[];
}
```

### 5.2 CapabilityDefinition

```ts
interface CapabilityDefinition {
  id: string;
  providerModuleId: string;
  title: string;
  purpose: string;
  inputSchema: JsonSchema;
  outputSchema: JsonSchema;
  mode: "read" | "plan" | "mutate" | "validate" | "build" | "test";
  risk: "low" | "medium" | "high" | "critical";
  requiredContext: ContextRequirement[];
  requiredIntegrations: string[];
  requiredPermissions: string[];
  preconditions: Condition[];
  postconditions: Condition[];
  evidenceProduced: EvidenceType[];
  supportsDryRun: boolean;
  supportsRollback: boolean;
  timeoutSeconds: number;
  retryPolicy: RetryPolicy;
  estimatedDuration?: Estimate;
  estimatedCost?: Estimate;
}
```

### 5.3 PipelineDefinition

```ts
interface PipelineDefinition {
  id: string;
  schemaVersion: number;
  projectId: string;
  intentId: string;
  stages: PipelineStage[];
  inputs: Record<string, unknown>;
  policies: PolicyRef[];
  budget: RuntimeBudget;
  rollbackStrategy: RollbackStrategy;
  templateSource?: TemplateRef;
}
```

### 5.4 PipelineStep

A step is one of:

- `agent`;
- `tool`;
- `approval`;
- `policy_gate`;
- `evaluator`;
- `fan_out`;
- `fan_in`;
- `sub_pipeline`;
- `retry`;
- `rollback`.

Every step declares:

- input/output schema;
- capability or agent;
- model policy;
- conditions;
- acceptance criteria;
- failure strategy;
- evidence requirements;
- checkpoint behavior.

### 5.5 AgentTask and AgentResult

Agents communicate through typed tasks and handoffs, not uncontrolled group chat.

```ts
interface AgentTask {
  id: string;
  agentRole: string;
  objective: string;
  contextRefs: string[];
  constraints: Constraint[];
  expectedOutputs: OutputRequirement[];
  acceptanceCriteria: AcceptanceCriterion[];
  allowedCapabilities: string[];
  budget: RuntimeBudget;
}
```

### 5.6 StepEvaluation

Separate facts from inference:

```ts
interface StepEvaluation {
  stepRunId: string;
  deterministicFacts: Fact[];
  aiInterpretation?: Interpretation;
  acceptanceResults: AcceptanceResult[];
  deviations: Deviation[];
  confidence?: number;
  evidenceRefs: string[];
  nextDisposition: "continue" | "recover" | "await_human" | "abort";
}
```

### 5.7 RecoveryPlan

```ts
interface RecoveryPlan {
  causeCandidates: CauseCandidate[];
  selectedAction:
    | "retry"
    | "retry_adjusted"
    | "add_context"
    | "upgrade_model"
    | "switch_capability"
    | "split_step"
    | "rollback"
    | "ask_human"
    | "abort";
  proposedChanges: RecoveryChange[];
  newBudgetImpact: Estimate;
  requiresApproval: boolean;
  maximumAdditionalAttempts: number;
}
```

---

## 6. Pipeline state machines

### PipelineRun

```text
draft
→ compiling
→ awaiting_approval
→ queued
→ running
→ observing
→ recovering
→ verifying
→ completed | blocked | failed | cancelled | rolled_back
```

### StepRun

```text
pending
→ ready
→ assigned
→ running
→ evaluating
→ succeeded | failed | waiting_approval | skipped | cancelled
```

### ChangeSet

```text
draft
→ planned
→ dry_run_ready
→ awaiting_approval
→ approved
→ executing
→ validating
→ completed | rejected | failed | rolled_back
```

State transitions occur through explicit domain methods and are persisted before side effects.

---

## 7. Runtime AI modules

Each module owns one vertical product capability.

```text
modules/
├─ ai-intent-compiler/
├─ ai-context-engine/
├─ ai-pipeline-compiler/
├─ ai-agent-runtime/
├─ ai-model-router/
├─ ai-run-observer/
├─ ai-recovery-planner/
└─ ai-run-distiller/
```

### Intent Compiler

- converts conversation into `ProductionIntent`;
- identifies missing facts;
- requests only bounded clarification;
- never starts mutation before the intent contract is confirmed.

### Context Engine

- retrieves Project Bible, GDD, assets, scenes, code, issues, prior runs and evidence;
- resolves canonical sources;
- minimizes repeated user explanation;
- records why each context item was included.

### Pipeline Compiler

- selects capabilities from the registry;
- generates dependencies, approvals, gates and recovery strategy;
- validates cycles, permissions, budgets and unavailable connectors deterministically.

### Agent Runtime

Initial runtime agents:

- Producer Agent;
- Game Design Agent;
- Technical Art Agent;
- Blender Agent;
- Unity Engineer Agent;
- Render Agent;
- QA Agent;
- AI Player Agent;
- Recovery Agent;
- Reviewer Agent.

### Model Router

Routes by capability tier, not hard-coded vendor name:

- `fast`;
- `standard`;
- `reasoning`;
- `vision`;
- `player`.

Records selection reason, tokens, latency, cost, result and escalation.

### Observer and Recovery

The observer evaluates every step against facts, output schemas, expected artifacts and acceptance criteria. The recovery planner may alter the remaining run, but cannot bypass policies or approvals.

### Run Distiller

A successful run may produce:

- Pipeline Template;
- Skill;
- Agent configuration;
- required-context contract;
- cache rules;
- approval policy;
- failure strategies;
- limits and examples.

---

## 8. Harness kernel

The Harness Kernel is product-owned and framework-independent.

```text
packages/harness-kernel/
├─ pipeline/
├─ capability-registry/
├─ connector-registry/
├─ policy-engine/
├─ approval/
├─ run-store/
├─ checkpoints/
├─ budgets/
├─ locks/
└─ templates/
```

### First-class resources

- Project;
- Environment;
- Connector;
- Capability;
- Agent;
- Model Profile;
- Secret Reference;
- Pipeline Template;
- Pipeline Definition;
- Pipeline Run;
- Policy;
- Approval;
- Artifact;
- Evidence Bundle;
- Release Candidate.

### Runtime guarantees

- idempotency key per step;
- local process lock per Unity project and Blender instance;
- durable run state;
- bounded retries;
- explicit timeout and cancellation;
- no silent skip;
- no implicit source-path resolution;
- exact Live/Cached/Mock execution mode;
- every critical step emits evidence.

---

## 9. Existing modules become Capability Providers

Every existing module registers both Editors and Capabilities.

Example Blender manifest fragment:

```yaml
capabilities:
  - id: blender.scene.inspect
    mode: read
    risk: low
  - id: blender.asset.apply_transform
    mode: mutate
    risk: medium
    supportsDryRun: true
    supportsRollback: true
  - id: blender.asset.export_glb
    mode: build
    risk: medium
  - id: blender.render.context_passes
    mode: validate
    risk: low
```

A module with only an Editor is a UI module, not a Harness execution node.

---

## 10. Modular repository structure

```text
sceneops/
├─ apps/
│  ├─ web/                    # composition root only
│  ├─ api/                    # API composition root only
│  └─ worker-host/            # worker bootstrap only
├─ packages/
│  ├─ contracts/
│  ├─ harness-kernel/
│  ├─ agent-runtime/
│  ├─ module-sdk/
│  ├─ command-bus/
│  ├─ event-bus/
│  ├─ api-client/
│  ├─ design-system/
│  ├─ evidence/
│  └─ test-kit/
├─ modules/
│  ├─ core-conversation/
│  ├─ workspace-shell/
│  ├─ project-system/
│  ├─ workflow-orchestrator/
│  ├─ ai-intent-compiler/
│  ├─ ai-context-engine/
│  ├─ ai-pipeline-compiler/
│  ├─ ai-agent-runtime/
│  ├─ ai-model-router/
│  ├─ ai-run-observer/
│  ├─ ai-recovery-planner/
│  ├─ ai-run-distiller/
│  ├─ asset-factory/
│  ├─ scene-viewport/
│  ├─ world-composer/
│  ├─ blender-bridge/
│  ├─ render-stage/
│  ├─ logic-studio/
│  ├─ unity-bridge/
│  ├─ build-release/
│  ├─ ai-playtest/
│  ├─ version-review/
│  └─ artifact-provenance/
├─ fixtures/
│  ├─ blender/
│  └─ unity/
├─ demos/
│  ├─ find-my-way-home/
│  └─ warehouse-escape/
└─ evidence/
```

Rules:

- app shells contain no feature logic;
- one writing agent owns one module folder;
- cross-module imports use public exports only;
- modules communicate through contracts, commands, events and registered services;
- modules can be disabled without breaking startup.

---

## 11. Conversation-first UX

The first screen remains conversation-only.

A production request returns a Pipeline Plan rather than only opening tools:

```text
Goal
Context used
Stages and Steps
Assigned Agents
Model tiers
Capabilities
Estimated time and cost
Approvals
Risks
Acceptance criteria
```

Actions:

- Review Pipeline;
- Run;
- Edit Constraints;
- Cancel.

After confirmation, the shell automatically opens:

- center: Pipeline Run;
- left: Context and Production Graph;
- right: Agent decisions and approvals;
- bottom: Logs, evidence, builds and playtest.

The user can still rearrange every Editor.

---

## 12. Local Blender architecture

Blender support has two execution paths behind one adapter.

### 12.1 Interactive bridge

Used when the user has Blender open:

```text
SceneOps Blender Add-on
↔ localhost RPC
↔ BlenderAdapter
```

Responsibilities:

- inspect current scene;
- resolve active objects;
- provide viewport captures;
- execute approved, typed operations on Blender's main thread;
- return structured results.

### 12.2 Headless CLI worker

Used for reproducible tests, validation, export and render:

```text
blender --background
→ version-pinned test script
→ JSON report + artifacts + exit code
```

### 12.3 Allowed operation surface

Read:

- scan scene;
- inspect object, mesh, materials, UV, transforms and hierarchy;
- capture camera and context passes;
- validate identity and dependencies.

Mutate through ChangeSet:

- assign/repair `sceneops_id`;
- apply transform;
- recalculate normals;
- set allowed light/material properties;
- generate known LOD operation;
- export GLB;
- save approved derived `.blend`.

No arbitrary `bpy` execution is exposed to the product runtime.

### 12.4 Local Blender fixture

`fixtures/blender/sceneops_fixture.blend` contains:

- `Key_Source`;
- `Door_Target`;
- `Entrance_Light`;
- parent hierarchy;
- shared mesh instances;
- one deliberately invalid transform or duplicate ID;
- camera for fixed render;
- material and UV data.

The fixture must be generated by a committed script so it can be recreated.

---

## 13. Local Unity architecture

Unity support also has two paths.

### 13.1 Editor bridge

A custom UPM package provides:

- `SceneOpsIdentity` component;
- project/scene scan;
- typed object/component inspection;
- approved property changes;
- test and build commands;
- Game View capture;
- playtest telemetry bridge.

An open-source Unity MCP may be supported as an optional connector, but SceneOps uses its own narrow capability contracts and does not expose unrestricted script execution.

### 13.2 Batchmode runner

Used for reproducible local verification:

```text
Unity -batchmode -projectPath ... -runTests / -executeMethod ...
```

It performs:

- package compile/import smoke;
- EditMode tests;
- PlayMode tests;
- scene identity audit;
- build;
- build manifest and logs.

A Unity project cannot be simultaneously used by the interactive Editor and a batchmode process. The test runner therefore creates or uses an isolated test copy/worktree.

### 13.3 Local Unity fixture

`fixtures/unity/SceneOpsHarnessFixture/` contains:

- one room;
- key asset placeholder/import target;
- locked door;
- inventory state;
- pickup interaction;
- goal marker;
- test controller;
- telemetry reporter;
- deterministic designed fault.

The package tests must compile on the repository's pinned Unity version.

---

## 14. Mandatory local end-to-end pipeline

```text
ProductionIntent: add a key and unlock-home feature
→ AI compiles Pipeline
→ Blender fixture/source scanned locally
→ approved Blender operation executed locally
→ GLB/asset manifest exported
→ Unity isolated project imports asset locally
→ Prefab and identity mapping validated
→ EditMode and PlayMode tests run locally
→ Build A produced locally
→ Player launched or WebGL served locally
→ AI/deterministic playtest records evidence
→ Issue backpins to sceneops_id
→ Recovery Agent proposes ChangeSet
→ approved Unity or Blender fix executed locally
→ Build B produced locally
→ identical test reruns
→ semantic, visual and behavior comparison
→ Distiller creates reusable template
```

A UI simulation cannot satisfy this gate.

---

## 15. AI rendering architecture

The Render Stage separates deterministic truth from generative proposals.

```text
Scene Snapshot
→ beauty/depth/normal/object-mask
→ vision analysis
→ AI LookDev candidates
→ editable write-back proposal
→ human approval
→ Blender/Unity ChangeSet
→ deterministic validation render
```

Initial write-back types:

- light intensity/color/temperature;
- material base color/roughness/emission;
- post-processing exposure;
- approved generated texture asset;
- camera parameter.

The AI image is never the final proof. The validation render of the modified scene is the proof.

---

## 16. AI playtest architecture

### Test modes

- deterministic smoke agent;
- goal-driven model agent;
- later: explorer and destructive agents.

### Runtime bridge

```text
ResetEpisode
GetObservation
GetAvailableActions
ExecuteAction
GetGameState
GetGoalProgress
CaptureEvidence
EndEpisode
```

### Evidence per step

- screenshot;
- position/rotation;
- visible/interactable object IDs;
- available and chosen action;
- game-state snapshot;
- goal progress;
- action result;
- timing and failure signals.

The AI generates interpretations and decisions; Unity records the deterministic state.

---

## 17. Source and evidence architecture

Logical zones:

```text
sources/
working/
generated/
optimized/
runtime/
cache/
fixtures/
deliveries/
evidence/
release/
manifests/
```

Every critical claim links an `EvidenceBundle` containing:

- source snapshot and hashes;
- exact environment;
- operation and exit status;
- logs;
- output files, size and SHA-256;
- runtime evidence;
- functional, visual, performance, package and publication verdicts;
- limitations and staleness state.

---

## 18. Observability

Use structured logs and OpenTelemetry-compatible traces.

Trace hierarchy:

```text
PipelineRun
└─ StageRun
   └─ StepRun
      ├─ AgentCall
      ├─ CapabilityInvocation
      ├─ ExternalProcess
      └─ EvidenceCapture
```

Required dimensions:

- project;
- pipeline/run/stage/step;
- agent;
- model tier/provider/model;
- capability;
- connector;
- source version;
- execution mode;
- duration;
- cost;
- retry/recovery count;
- result.

---

## 19. Security boundaries

1. Local bridges bind to loopback by default.
2. Paths are normalized and checked against configured project roots.
3. External commands use argument arrays, not interpolated shell strings.
4. AI cannot directly invoke arbitrary code execution.
5. Mutations require typed ChangeSet and approval based on risk.
6. Pre-change snapshots are required for medium/high-risk mutations.
7. Credentials are referenced by secret ID and never added to prompts or logs.
8. Model-generated fixes cannot bypass policy gates.
9. Open-source connectors are pinned and wrapped by conformance tests.
10. Every local tool has timeout, cancellation and process cleanup.

---

## 20. Open-source boundary

### Use as dependencies where appropriate

- Dockview for docking UI;
- React Flow/xyflow for Pipeline visualization;
- Three.js/React Three Fiber for browser 3D;
- glTF Validator/Transform for asset validation and optimization;
- LangGraph behind the agent-runtime abstraction;
- OpenTelemetry SDKs for traces.

### Use as optional adapters or references

- `blender-ai-mcp`: reference goal-first routing, curated tools and deterministic verification; reuse only audited Apache-licensed portions or run behind an adapter.
- `unity-mcp`: optional local connector/reference; SceneOps owns the narrow command schema and safety rules.
- GameCI: optional remote CI mirror after local Unity tests pass.

### Must remain SceneOps-owned

- Capability Registry;
- Pipeline schema and runtime semantics;
- Context Engine;
- Agent definitions and handoffs;
- Model Router;
- Observer/Evaluator;
- Recovery Planner;
- Stable scene identity contract;
- Evidence Ledger;
- local Blender/Unity conformance tests;
- product UX and WorkBuddy templates.

---

## 21. Deployment modes

### Local Development

- full source;
- local Blender and Unity;
- development model provider;
- verbose evidence and logs.

### Local Live Demo

- pinned tool paths and fixture projects;
- real local Blender/Unity steps;
- cached expensive AI/render outputs only when labelled;
- one-click reset.

### Judge Offline/Cached Mode

- deterministic fixtures;
- no external API required;
- clearly labelled Mock/Cached steps;
- never presented as current Live execution.

### Optional Remote Workers

A later capability. Local execution remains the mandatory conformance baseline.

---

## 22. Product templates

Initial templates:

1. `Brief to Playable`
2. `Asset to Engine`
3. `AI LookDev and Apply`
4. `Issue to Verified Fix`
5. `Release Candidate`

The main hero flow composes templates 2 and 4 inside template 1.

---

## 23. Architecture acceptance

The architecture is implemented only when:

- a natural-language goal produces a validated Pipeline;
- the Pipeline assigns runtime Agents and model tiers;
- modules expose typed Capabilities, not only Editors;
- Blender and Unity local conformance suites pass;
- at least one real cross-tool pipeline passes;
- a failed step is observed and diagnosed;
- a RecoveryPlan changes the execution path;
- the identical test verifies the fix;
- the run becomes a reusable template;
- the second game uses that template without platform source changes;
- evidence and release claims remain accurate.
