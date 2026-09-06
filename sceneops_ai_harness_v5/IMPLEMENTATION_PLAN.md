# SceneOps AI Production Harness Implementation Plan

Version: 5.0  
Approach: retrofit the existing prototype; do not start a parallel application

---

## 1. Planning rules

1. Preserve the working conversation-only shell, four-edge reveal, docking and module folders.
2. Freeze and tag the current baseline before changing runtime semantics.
3. Build the AI Control Plane underneath the current UI rather than adding more UI-only modules.
4. Promote Pipeline from one module to the core runtime object.
5. Make existing modules register typed Capabilities.
6. A capability is not `Live` until its local tool test has passed in the current environment.
7. Use open source for infrastructure, patterns and optional connectors; keep the domain contracts and control loop owned by SceneOps.
8. Do not defer all real integration until the end. Local Blender and Unity gates enter early.
9. Maintain truthful status: `Live`, `Cached`, `Mock`, `Partial`, `Blocked`, `Missing`.
10. Every phase ends with a runnable vertical slice and evidence.

---

## 2. Baseline deliverables

Before implementation, create:

- `STATUS.md`;
- `PROTOTYPE_GAP_MATRIX.md`;
- `CURRENT_CAPABILITY_CATALOG.md`;
- `CURRENT_AI_USAGE_AUDIT.md`;
- `PROTECTED_BASELINE.md`;
- `HARNESS_MIGRATION_DECISIONS.md`;
- baseline test and production-build evidence;
- Git tag `prototype-shell-baseline`.

The gap matrix classifies every current feature as:

- UI only;
- deterministic capability;
- AI planning;
- AI execution assistance;
- AI evaluation;
- AI recovery;
- governance/evidence.

---

## 3. Dependency order

```text
Baseline Audit
      ↓
Contracts + Capability Registry + Harness Kernel
      ↓
Intent + Context + Pipeline Compiler
      ↓
Agent Runtime + Model Router + Observer
      ↓
Local Blender Conformance
      ↓
Local Unity Conformance
      ↓
Asset-to-Engine Live Pipeline
      ↓
AI Render + Visual Verification
      ↓
Build + AI Playtest + Issue Backpin
      ↓
Recovery + Same-Test Regression
      ↓
Run Distillation + Warehouse Escape
      ↓
Full Modules + Collaboration + Release + WorkBuddy
```

---

## 4. Phase plan

## Phase 0 — Audit and freeze current prototype

### Work

- run existing lint, typecheck, unit, E2E and production build;
- record exact commands, versions and failures;
- capture real-browser screenshots of the conversation-only home and docking behavior;
- inventory module manifests and public APIs;
- identify UI-only features and duplicated contracts;
- identify existing Blender/Unity/ComfyUI connectors;
- tag current baseline;
- archive conflicting old architecture documents without deleting history.

### Exit gate

- current behavior is reproducible;
- no claimed capability lacks a status;
- protected baseline is explicit;
- migration path is approved.

### Suggested agents

- `repo_explorer`: read-only;
- `qa_reviewer`: read-only;
- principal integrates findings.

---

## Phase 1 — Freeze contracts and build Harness Kernel

### Work

Create canonical contracts:

- `ProductionIntent`;
- `ContextBundle`;
- `CapabilityDefinition`;
- `CapabilityInvocation`;
- `PipelineDefinition`;
- `PipelineStage`;
- `PipelineStep`;
- `PipelineRun`;
- `StepRun`;
- `AgentTask`;
- `AgentResult`;
- `AgentHandoff`;
- `ModelRoutingDecision`;
- `StepEvaluation`;
- `FailureAnalysis`;
- `RecoveryPlan`;
- `DistilledWorkflow`;
- `RuntimeBudget`.

Implement:

- capability registry;
- connector registry;
- pipeline/run store;
- explicit state transitions;
- approval and policy gates;
- checkpoints and rollback references;
- local process locks;
- structured event stream;
- API/OpenAPI-generated frontend client.

### Exit gate

- a deterministic Mock Pipeline can compile, pause for approval, resume, retry, fail and roll back;
- state survives API restart;
- module capability manifests validate;
- contract, state-machine and boundary tests pass.

### Suggested agents

- principal architect owns contracts;
- one kernel agent owns `packages/harness-kernel`;
- one independent reviewer checks state semantics.

---

## Phase 2 — Convert modules into Capability Providers

### Work

For each existing module:

- retain Editor registration;
- add capability declarations;
- define input/output schemas;
- declare risk and permissions;
- add preconditions/postconditions;
- declare evidence, timeout, retry and rollback;
- add capability health and conformance tests.

Start with:

- Project/System;
- Source Registry;
- Asset;
- Blender;
- Render;
- Unity;
- Build;
- Playtest;
- Version/Evidence.

### Exit gate

The registry can answer:

- what can be done;
- which connector is required;
- whether it is callable locally;
- what evidence it produces;
- whether it can mutate, dry-run and roll back.

No core Pipeline code imports module internals.

---

## Phase 3 — AI Intent, Context and Pipeline Compilation

### Work

Implement:

- `ai-intent-compiler`;
- `ai-context-engine`;
- `ai-pipeline-compiler`.

The first conversation response for a production goal is:

1. interpreted goal;
2. canonical context used;
3. proposed Pipeline;
4. assigned Agents and model tiers;
5. estimated duration/cost;
6. approvals;
7. risks;
8. acceptance criteria.

The deterministic compiler verifies:

- schema;
- capability availability;
- permissions;
- dependency cycles;
- budgets;
- required sources;
- rollback points.

### Exit gate

The user can request:

> Add a key and unlock-home feature.

The product returns a valid Pipeline without the user manually choosing modules.

Mock execution completes the entire flow.

---

## Phase 4 — Agent Runtime and Model Router

### Work

Implement runtime Agents:

- Producer;
- Game Design;
- Technical Art;
- Blender;
- Unity Engineer;
- Render;
- QA;
- AI Player;
- Recovery;
- Reviewer.

Implement:

- typed tasks and handoffs;
- per-Agent capability allowlists;
- context policies;
- model-tier policies;
- budgets;
- agent result validation;
- product-visible routing decisions;
- escalation rules.

### Exit gate

- each Pipeline Agent step shows its task, context, model decision and result;
- an Agent cannot call a denied capability;
- two failures cause an explicit escalation or human interrupt;
- no uncontrolled Agent group chat exists.

---

## Phase 5 — Local Blender conformance and Live adapter

### Work

- detect configured Blender executable and version;
- create reproducible fixture `.blend`;
- build SceneOps Blender add-on/bridge;
- implement headless CLI runner;
- implement stable identity;
- implement read-only inspection;
- implement typed mutations with pre-change snapshot;
- export GLB and manifests;
- render fixed passes;
- produce EvidenceBundle.

### Required local tests

- version and startup;
- add-on import;
- fixture scan;
- duplicate ID detection/repair;
- transform/material/light ChangeSet;
- dry run and rejection;
- rollback;
- GLB export and reinspection;
- fixed camera beauty/depth/normal/object mask;
- timeout/cancel/cleanup.

### Exit gate

`blender.*` critical capabilities are `Live` on the local machine, with current logs and hashes.

No arbitrary Python capability is public.

---

## Phase 6 — Local Unity conformance and Live adapter

### Work

- detect Unity project version and matching executable;
- create or validate a Unity fixture project;
- build the SceneOps UPM package;
- implement `SceneOpsIdentity`;
- implement project/scene scan and identity mapping;
- implement typed component changes;
- implement EditMode and PlayMode tests;
- implement build CLI;
- implement player telemetry/test bridge;
- use an isolated project copy for batchmode.

### Required local tests

- package compile/import;
- project scan;
- identity mapping;
- Prefab import/update;
- component ChangeSet;
- EditMode tests;
- PlayMode tests;
- compile failure handling;
- missing reference gate;
- local player build;
- player launch and report;
- timeout/cancel/cleanup;
- rollback.

### Exit gate

`unity.*` and `build.*` critical capabilities are `Live` locally.

A real player artifact is generated and its exact filename, size and SHA-256 are recorded.

---

## Phase 7 — Live Asset-to-Engine Pipeline

### Work

Compose:

```text
AssetSpec
→ inspect source
→ Blender process
→ asset gates
→ GLB/FBX publish
→ Unity import
→ identity map
→ Prefab
→ scene placement
→ Unity tests
```

Use the key asset from the main demo.

### Exit gate

- one actual Blender-derived asset reaches a Unity Prefab and scene instance;
- stable ID is preserved or explicitly mapped;
- source, generated, runtime and cache paths are separated;
- every step has evidence;
- rerunning with unchanged inputs uses correct cache behavior.

---

## Phase 8 — AI Render and visual feedback loop

### Work

- deterministic context passes;
- constrained AI LookDev;
- variant evaluation;
- write-back mapping;
- human approval;
- Blender or Unity parameter ChangeSet;
- deterministic validation render;
- visual Diff and acceptance.

### Exit gate

At least one AI visual proposal changes editable scene data and is verified by a new render. A generated image alone does not pass.

---

## Phase 9 — Observer, RCA and Recovery

### Work

Implement:

- `ai-run-observer`;
- `ai-recovery-planner`;
- structured facts versus interpretation;
- log/artifact correlation;
- change impact lookup;
- recovery budget;
- alternative capability/model routing;
- human escalation.

Create deterministic faults:

- invalid asset scale/ID;
- Unity compile or missing reference;
- collider/navigation issue;
- target visibility issue.

### Exit gate

A failing Pipeline does not simply stop. It produces:

- facts;
- candidate causes;
- proposed recovery;
- budget and risk;
- a changed execution path;
- a final result or explicit block.

---

## Phase 10 — Build, AI playtest, backpin and regression

### Work

- Build A;
- deterministic smoke test;
- goal-driven AI player;
- structured PlaytestStep;
- Issue generation;
- exact scene/object/camera backpin;
- approved fix;
- Build B;
- identical test rerun;
- semantic, visual and behavior comparison.

### Exit gate

The system proves a fix with the same test configuration and current evidence.

---

## Phase 11 — Run Distillation and reusable templates

### Work

Implement `ai-run-distiller`.

Generate from successful runs:

- Pipeline Template;
- Skill;
- Agent roster/config;
- context contract;
- parameters;
- cache rules;
- approval policy;
- recovery strategy;
- acceptance criteria;
- limitations.

### Exit gate

The `Asset to Engine` and `Issue to Verified Fix` templates can be loaded without reconstructing prompts manually.

---

## Phase 12 — Full 3D production expansion

Complete real vertical capabilities for:

- Design Room and FeatureSpec;
- Production Graph;
- Concept Lab;
- Asset Factory;
- Character/Animation;
- World Composer;
- Logic Studio;
- UI Studio;
- Audio Studio;
- VFX/Shader;
- Render Stage;
- Build/Release.

Each module must have at least one real output, not only a placeholder Editor.

### Exit gate

The main demo traverses every promised category, while the core release does not depend on unfinished optional nodes.

---

## Phase 13 — Warehouse Escape reuse proof

### Work

Run the same templates on a second game:

```text
build
→ playtest
→ collider/navigation Issue
→ backpin
→ fix
→ rebuild
→ regression
```

### Exit gate

- no platform source changes for the second game;
- only project configuration, assets, context and tests differ;
- reuse time and manual interventions are recorded.

---

## Phase 14 — Collaboration, version, evidence and release

### Work

- comments, assignment and approval;
- file, semantic, visual and behavior Diff;
- Evidence Ledger;
- capability matrix;
- final package gate;
- exact release archive, unpack/smoke, offline/fresh-browser validation;
- claim audit.

### Exit gate

No `completed`, `fixed`, `offline`, `uploaded` or `published` claim exists without current evidence.

---

## Phase 15 — WorkBuddy and competition delivery

Package:

- WorkBuddy instance;
- Skills and prompts;
- runtime Expert/Agent definitions;
- Connectors/MCP mappings;
- prebuilt workflows;
- other-game demo;
- documentation;
- two-page capability summary;
- three-minute video script;
- five-minute pitch;
- one-click Judge Mode reset.

---

## 5. Workstream ownership

| Workstream | Owned paths | Preferred agent tier |
|---|---|---|
| Contracts and Kernel | `packages/contracts`, `packages/harness-kernel` | strongest |
| AI Control Plane | `modules/ai-*` | strongest for design, standard for implementation |
| Shell/UX | conversation and workspace modules | strong UI/coding |
| Blender | Blender module, fixture and worker | strongest |
| Unity | Unity module, UPM package and fixture | strongest |
| Render | Render module and Comfy adapter | strong |
| Playtest | Playtest module and runtime bridge | strong |
| Evidence/Release | provenance, version, release | standard + strong review |
| Full modules | one module per writer | standard |
| QA/Docs | read-only reviewers and docs agent | fast/standard |

Rules:

- one writing agent per module folder;
- shared contracts have one owner per phase;
- read-only reviewers can run in parallel;
- principal merges one module at a time after local tests.

---

## 6. Model routing during product development

| Task | Model tier |
|---|---|
| repository scans, fixtures, docs | fast |
| ordinary module implementation | standard |
| pipeline compiler, contracts, recovery | strongest reasoning |
| Blender/Unity integration | strongest coding/reasoning |
| visual/editor QA | vision-capable reviewer |
| final security/architecture review | strongest independent reviewer |

Within the product runtime, use abstract tiers (`fast`, `standard`, `reasoning`, `vision`, `player`) and configure providers separately.

---

## 7. Quality gates per phase

Every phase must pass:

1. success path;
2. representative failure path;
3. visible user failure state;
4. current evidence;
5. module-disable/startup test;
6. API/contracts generated and synchronized;
7. documentation update;
8. exact Live/Cached/Mock status;
9. no regression to conversation-only first screen;
10. no arbitrary code execution exposed.

---

## 8. Release-blocking E2E tests

- conversation goal → Pipeline plan;
- Pipeline approval and run;
- local Blender conformance;
- local Unity EditMode/PlayMode/build;
- Asset-to-Engine;
- AI Render write-back;
- Build A → playtest → Issue backpin;
- recovery → Build B → same-test regression;
- run distillation;
- Warehouse Escape reuse;
- Judge Mode reset;
- final package inspection.

---

## 9. Metrics to collect

Do not hard-code values.

- Time to Pipeline;
- Time to First Playable;
- Issue to Verified Fix;
- autonomous step ratio;
- human approval count;
- recovery success rate;
- model escalation count;
- run cost;
- cache reuse rate;
- template reuse time;
- local Blender/Unity success rate;
- unsupported claim count.

---

## 10. Immediate next actions

1. Tag the current prototype.
2. Run baseline tests/build and create the gap matrix.
3. Freeze the V5 contracts.
4. Implement Capability Registry and deterministic Mock Pipeline.
5. Implement Intent → Context → Pipeline planning.
6. Build local Blender conformance suite.
7. Build local Unity conformance suite.
8. Complete the Live Asset-to-Engine vertical slice.
9. Add Observer/Recovery around a deliberately failing step.
10. Complete Build A/B and same-test regression.

Do not add another large Editor before actions 1–8 work.
