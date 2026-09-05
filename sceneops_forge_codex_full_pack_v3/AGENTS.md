# SceneOps Forge Repository Rules

## 1. Product goal

Build an AI-native full-chain 3D game production workbench:

```text
brief -> design -> tasks -> concepts -> assets -> world -> logic -> render
-> Unity build -> AI playtest -> issue backpin -> verified fix -> release
```

The initial application view is chat-only. Tools are pulled from the top, bottom, left, or right and can be docked, split, tabbed, floated, popped out, and saved as workspaces.

The repository uses feature modules. Every independent product capability lives in its own folder under `modules/`.

## 2. Read-first order

Before changing code, read:

1. root `AGENTS.md`
2. `product.md`
3. `design.md`
4. `architecture.md`
5. `MODULE_CONTRACT.md`
6. `FRONTEND_INTEGRATION.md`
7. the nearest nested `AGENTS.md`
8. the target module README and manifest

The nearest `AGENTS.md` may add module-specific rules. It may not weaken root security, provenance, identity, truthfulness, or test rules.

## 3. Language

- Code, identifiers, API paths, schema fields, commits: English.
- User interface and primary user docs: Simplified Chinese.
- Short English subtitles are allowed where useful.
- Use explicit domain names. Avoid vague names such as `Manager`, `Helper`, `Thing`, `Data`, and catch-all `Utils`.

## 4. Module ownership

- Every feature belongs to exactly one module.
- `apps/web` contains bootstrapping and composition only.
- `services/api` contains bootstrapping and module registration only.
- A module may import core packages and another module's declared public API only.
- Never import another module's internal file path.
- Cross-module behavior uses typed commands, typed events, stable IDs, or explicit public service interfaces.
- Every module has `module.yaml`, `README.md`, tests, fixtures, and module-local docs.
- Every module can be disabled through a feature flag.
- Every module must run its tests independently.
- Do not place unrelated feature code in `shared`, `common`, or `utils` to avoid choosing ownership.

## 5. Code simplicity

- Prefer the smallest complete implementation.
- Abstract only after at least two real consumers exist.
- Prefer composition and explicit interfaces over inheritance.
- Ordinary functions should usually stay under 50 lines.
- Ordinary source files should usually stay under 400 lines.
- Generated files are exempt and must be marked generated.
- Keep one canonical implementation per behavior.
- Delete obsolete code instead of maintaining parallel implementations.
- Comments explain invariants, intent, coordinate conversions, safety, or non-obvious tradeoffs.
- Do not add a dependency when a short local implementation is clearer.

## 6. Contract ownership

- Backend Pydantic models and OpenAPI are the network-contract source of truth.
- Generate TypeScript network types. Do not hand-copy request or response types.
- On-disk manifests and events use versioned JSON Schemas.
- Public contract changes require compatibility tests and documentation updates.
- All timestamps use UTC ISO-8601.
- All checksums use SHA-256.
- Distances use meters unless explicitly declared otherwise.
- Coordinates always declare coordinate space and axis convention.

## 7. Stable identity

- Every asset, scene object, scene instance, build, run, and issue uses a stable ID.
- 3D scene objects use `sceneops_id`.
- Asset identity and scene-instance identity are distinct.
- The same object identity must survive Blender -> glTF/GLB -> Web Viewer -> Unity -> Runtime Telemetry -> Issue Backpin.
- Names, hierarchy paths, file paths, and indices are display or locator data, never the primary identity.
- Renames preserve IDs. Copies receive new IDs.
- Every identity conversion has tests.

## 8. Chat-first shell

- The first view contains only `assistant.conversation` and subtle edge pull handles.
- Do not add a dashboard, fixed navigation rail, fixed inspector, or fixed console to the initial state.
- Tools open through typed commands from chat, command search, menus, or edge drawers.
- Chat and buttons call the same command handlers.
- The assistant may propose layout changes but may not unexpectedly rearrange the workspace without confirmation.
- Use `dockview-react` as the only docking engine.
- Heavy editors are lazy-loaded.
- Hidden 3D tabs suspend rendering.

## 9. Frontend state

- TanStack Query owns server state.
- Small Zustand stores may own transient viewport, drag, selection, and local shell state only.
- Dock layout state is separate from domain state.
- No giant global store.
- React components never call Blender, Unity, ComfyUI, Git, shell, or file-system tools directly.
- All API calls use one generated typed client.
- All editor types use `EditorRegistry`.
- All module contributions use a manifest and static validated registry.
- All loading, empty, offline, permission, failed, retry, and disconnected states must be visible.

## 10. Mutation safety

No AI or user action may directly edit production tools or project files.

Every mutation first creates a typed `ChangeSet` containing:

- base version;
- target integration and objects;
- previous values;
- proposed values;
- rationale;
- expected result;
- impact scope;
- risk;
- validation plan;
- rollback plan;
- approval requirements.

All mutations support dry-run. Destructive, project-wide, scene-wide, merge, overwrite, and release actions require explicit approval.

Arbitrary Python, C#, shell, and unrestricted file-system execution are disabled in application runtime. Only allowlisted typed adapter commands are exposed.

## 11. Adapter rules

External tools live behind typed adapters:

- Blender
- Unity
- ComfyUI or render service
- Git / Git LFS
- Artifact storage
- LLM provider
- build runner
- playtest runner

Each adapter supplies:

- capability report;
- health check;
- timeout;
- cancellation;
- retry policy;
- progress events;
- structured logs;
- deterministic mock;
- error mapping;
- provenance;
- rollback or compensation where feasible.

Pin third-party versions or commits. Do not depend on an unpinned main branch.

## 12. Truthfulness

Every run and artifact is one of:

- `live`: actually executed now against the external tool;
- `cached`: reused from a prior real run;
- `mock`: deterministic local fixture;
- `planned`: not yet executed;
- `blocked`: unable to execute, with a reason.

The UI and reports always show this mode. Never present mock or cached output as live.

## 13. Jobs and workflows

- Jobs have explicit state machines.
- Jobs are observable, cancellable, retryable, and resumable.
- Same inputs plus same recipe version should be idempotent.
- Failed jobs preserve logs and completed intermediate artifacts.
- Cache keys include every behavior-changing input.
- Nodes never silently skip. They report a state and reason.
- Human approval is a first-class pause state, not a simulated delay.

## 14. Provenance

Every imported or generated artifact records:

- artifact ID and type;
- source project and source version;
- source commit if available;
- related `sceneops_id` values;
- producing module;
- tool and adapter version;
- recipe/workflow version;
- creator or agent;
- execution mode;
- timestamp;
- SHA-256 checksum;
- approval state.

AI outputs additionally record provider/model, workflow hash, prompt, negative prompt when used, seed, and relevant parameters.

## 15. Collaboration and versioning

- Git and Git LFS remain the file-version foundation.
- SceneOps adds semantic, visual, and behavior diffs.
- Collaboration supports comments, assignments, review sessions, approvals, decisions, and activity history.
- Do not attempt simultaneous binary merging of `.blend` or Unity scene files.
- Use locks, branches, review, and conflict warnings for binary production assets.

## 16. Tests

### 16.1 Test execution authorization

- Unless the user explicitly authorizes broader testing in the current conversation, run only the smallest relevant smoke test for the changed scope.
- Full unit, integration, end-to-end, security, performance, build, render, Unity, Blender, and playtest suites require explicit user permission before execution.
- Tests and fixtures must still be implemented and maintained where required, but unexecuted suites must be reported as `not run` or `pending approval`, never as passed.
- Permission to run one named test or smoke check does not authorize other suites.
- Smoke testing should be limited to startup/import validation and one minimal primary-path check, without long-running external-tool operations.

A feature is incomplete without:

1. a success-path test;
2. a representative failure-path test;
3. a visible user-facing failure state;
4. a deterministic fixture;
5. public contract documentation.

Required suites include:

- contract and schema tests;
- module manifest and dependency tests;
- state-machine tests;
- adapter contract tests;
- identity-chain tests;
- API integration tests;
- editor and shell component tests;
- layout persistence and migration tests;
- security tests for paths and command allowlists;
- hero-flow Playwright E2E;
- other-game E2E;
- cached judge-demo E2E.

Do not delete, weaken, or skip tests to claim success.

## 17. Documentation

Keep current:

- `README.md`
- `STATUS.md`
- `EXECUTION_PLAN.md`
- root architecture/product/design docs
- each module README and docs
- API and event docs
- frontend editor/module integration docs
- Blender, Unity, render, playtest, setup, demo, and troubleshooting docs
- `THIRD_PARTY_NOTICES.md`

Update documentation in the same change as the public behavior.

## 18. Subagents

- Delegate by non-overlapping module or file ownership.
- Prefer parallel agents for exploration, tests, docs, and independent modules.
- Be cautious with parallel write-heavy changes.
- Every subagent receives scope, allowed files, acceptance criteria, commands, and output format.
- Every subagent returns changed files, tests run, unresolved risks, and integration instructions.
- High-risk changes receive an independent read-only review.
- The principal agent owns final architecture and integration.

## 19. Git discipline

- Use small reviewable commits by vertical feature slice.
- Do not mix unrelated refactors.
- Run relevant lint, type checks, tests, and E2E before merge.
- Never commit secrets, model weights, Unity `Library`, build caches, Blender caches, or temporary renders.
- Record major dependency licenses and reasons.

## 20. Definition of done

A module is complete only when its manifest, public API, UI/editor contribution, backend behavior when needed, tests, fixtures, failure states, and docs are complete.

The product is complete only when:

- chat-only home works;
- four-edge pull-out workspace works;
- tools are modular and dockable;
- the main brief-to-release hero flow works;
- at least one Blender and one Unity path are live;
- AI render writes editable data back;
- AI playtest creates structured evidence and backpins an issue;
- regression and rollback work;
- the second game runs without platform source changes;
- live/mock/cached are honest;
- Judge Mode resets in one action;
- release-blocking tests pass.

## 21. V5 runtime additions

- Product-runtime experts are separate from Codex development subagents.
- `sceneops_harness` owns canonical Pipeline/Capability/Run contracts and durable lifecycle semantics; `sceneops_ai_provider` owns model transport and write-only provider configuration.
- A model proposes a plan, never its own permissions, approvals, mutation scope or budget policy. Plan generation and execution are separate explicit user actions.
- User-selected `bounded_calls` may permit unknown provider usage only within persisted call/attempt/time limits. Unknown cost is never displayed as verified zero; default policy requires reported usage before additional metered calls.
- Credentials are bound to an exact configured endpoint, never sent to another URL by default and never included in prompts, network responses, logs, artifacts or browser persistence.
- Source V5 documents are reference architecture, not authority to run their test/build/Blender/Unity commands. Section 16.1 and current user authorization still govern execution.
- Do not label the entire V5 architecture complete when only the planning/runtime/UI foundation is implemented. External Live chains require their own current authorized evidence.
