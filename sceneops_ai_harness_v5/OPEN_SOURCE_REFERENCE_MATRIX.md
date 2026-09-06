# Open-Source Reference and Ownership Matrix

Version: 5.0

SceneOps uses open source selectively. The product must not become a thin wrapper around one repository.

---

## 1. Decision categories

| Category | Meaning |
|---|---|
| Direct dependency | Mature library used as an internal implementation detail |
| Adapter/fork candidate | Useful connector, but wrapped by SceneOps contracts and conformance tests |
| Architecture reference | Study patterns; do not depend on runtime code |
| SceneOps-owned | Core competitive differentiation and public contracts |

---

## 2. Recommended projects

| Area | Project | Category | Use | Do not outsource |
|---|---|---|---|---|
| Agent graph | LangGraph | Direct dependency behind interface | persistence, branching, interrupts, subgraphs | product Pipeline schema, capability model, recovery policy |
| Docking UI | Dockview | Direct dependency | split/tab/float/popout/layout serialization | conversation-first product behavior, Editor registry semantics |
| Pipeline canvas | React Flow / xyflow | Direct dependency | graph visualization and editing | runtime execution semantics |
| Browser 3D | Three.js + React Three Fiber | Direct dependency | viewport and interaction substrate | stable identity, context packet, QA rules |
| glTF | glTF Validator + glTF-Transform | Direct dependency | validation, transform and optimization | project asset policy and evidence |
| Blender AI bridge | `PatrykIti/blender-ai-mcp` | Adapter/fork candidate and architecture reference | curated tools, goal-first routing, inspection/assertion patterns | SceneOps local contract, safety policy, fixture and test gates |
| Blender broad MCP | `ahujasid/blender-mcp` | Reference only by default | installation/socket patterns and feature survey | unrestricted Python execution or telemetry defaults |
| Unity AI bridge | `CoplayDev/unity-mcp` | Optional adapter/fork candidate | Editor connection, tool grouping, test/build ideas | SceneOps capability contract, project isolation and safe mutation policy |
| Unity CI | GameCI Builder/Test Runner | Optional remote CI mirror | later GitHub CI execution | mandatory local Unity verification |
| Unity testing | Unity Test Framework | Direct project dependency | EditMode and PlayMode tests | product-specific test bridge and AI telemetry |
| Agent observability | OpenTelemetry | Direct dependency | traces, metrics and correlation | evidence semantics and claim audit |
| AI render | ComfyUI | External service adapter | graph-based generative image workflows | RenderRecipe contract, write-back, deterministic validation |
| Image/colour | OpenImageIO/OpenColorIO/OIDN | Direct/optional dependencies | image I/O, color and denoise | visual acceptance policy |
| Versioned large files | Git LFS | Direct dependency when needed | store large source/asset files | semantic/visual/behavior Diff |

---

## 3. SceneOps-owned competitive core

These must be designed and maintained by SceneOps:

1. `ProductionIntent` and Execution Contract.
2. Context Engine with canonical-source awareness.
3. Capability Registry and typed capability contracts.
4. Pipeline Compiler and deterministic validation.
5. Runtime Agent roles and handoff contracts.
6. Model Router and budget/escalation policy.
7. Run Observer, RCA and Recovery Planner.
8. Run Distiller and WorkBuddy template/Skill generation.
9. `sceneops_id` cross-tool identity contract.
10. ChangeSet, approval and rollback semantics.
11. Evidence Ledger and multi-level acceptance.
12. Local Blender and Unity conformance suites.
13. Conversation-first Harness UX.
14. Other-game reuse protocol.

---

## 4. Open-source acceptance procedure

Before adding or forking a project:

1. Pin a release or commit; never depend permanently on `main`.
2. Verify license and record it in `THIRD_PARTY_NOTICES.md`.
3. Run a security and subprocess review.
4. Put it behind a SceneOps adapter.
5. Add capability conformance tests.
6. Disable telemetry and external download defaults unless explicitly approved.
7. Reject unrestricted code execution from the product-facing surface.
8. Verify startup, timeout, cancellation, repeated use and shutdown locally.
9. Record exactly which behavior is borrowed and which remains custom.
10. Ensure the adapter can be replaced without changing product contracts.

---

## 5. Blender connector decision

Preferred approach:

- build a small SceneOps Blender add-on and headless CLI test runner;
- borrow architecture and audited components from `blender-ai-mcp` where useful;
- optionally support compatible third-party MCP connectors through an adapter;
- never expose arbitrary Python as a default product capability.

The reason is not ideological: local tool reliability, stable contracts, deterministic inspection and exact evidence are part of the product's differentiation.

---

## 6. Unity connector decision

Preferred approach:

- build a small SceneOps UPM package for identity, inspection, typed changes, tests, builds and telemetry;
- use official Unity batchmode/Test Framework for conformance;
- optionally connect to `unity-mcp` for broader interactive authoring;
- use GameCI later as an additional remote runner, never as a substitute for local pass/fail.

---

## 7. Agent framework decision

Use LangGraph through a SceneOps `AgentGraphRuntime` interface.

Do not let:

- graph state become the database schema;
- agent node names become Pipeline Step IDs;
- framework checkpoints replace evidence or run records;
- LLM-generated graph code execute unchecked.

The deterministic Pipeline Compiler produces a SceneOps-owned `PipelineDefinition`; the agent framework helps propose, observe and adapt it.
