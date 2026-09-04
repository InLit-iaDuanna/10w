# SceneOps Forge Definition of Done

## 1. Module DoD

A module is done only when:

- `module.yaml` validates;
- dependencies are declared and acyclic;
- module-level `AGENTS.md` and README exist;
- public frontend/backend entrypoints are explicit;
- editors/commands/jobs/events are registered;
- module can be disabled;
- missing integrations have a visible degraded state;
- success and failure paths work;
- deterministic fixtures exist;
- module tests pass independently;
- public contracts and docs are current;
- live/mock/cached behavior is honest;
- no internal cross-module imports exist.

## 2. Shell DoD

- fresh launch is conversation-only;
- four edges can be pulled open;
- drawers support hidden/peek/pinned;
- tools can open from chat, menu, command search, and Tool Library;
- editors can tab, split, move, float, pop out, maximize, close, and restore;
- layout saves, migrates, imports, exports, and resets;
- assistant cannot silently rearrange custom layouts;
- Judge Mode is one-click and resettable;
- hidden 3D views suspend rendering;
- invalid layout recovers safely.

## 3. Full-chain DoD

- project can be created or imported;
- Project Bible, GDD, Feature Spec, and tasks are connected;
- concept can produce an AssetSpec;
- an asset reaches a published version;
- Blender performs at least one live, safe, audited operation;
- stable identity survives export and web display;
- Unity imports and maps the asset;
- world and gameplay logic form a playable task;
- AI render creates variants and writes approved editable data back;
- Unity produces a real playable build;
- AI playtest records structured steps and evidence;
- an issue backpins to a real source object/component/script;
- a typed fix is approved and executed;
- the same test reruns and produces before/after evidence;
- merge, release candidate, and rollback paths work.

## 4. Reuse DoD

- Warehouse Escape uses the same modules and workflows;
- platform source code is unchanged;
- only project data, recipes, assets, policies, and tests differ;
- the second game produces a real build;
- its issue/fix/regression flow works.

## 5. Integration DoD

Each external adapter has:

- health check;
- capability report;
- allowlisted commands;
- dry-run;
- timeout/cancel/retry;
- error mapping;
- deterministic mock;
- provenance;
- tests;
- setup and troubleshooting docs.

## 6. Test DoD

Release blockers:

- all contract tests;
- module manifest/dependency tests;
- identity-chain tests;
- shell/docking tests;
- adapter tests;
- ChangeSet approval tests;
- render provenance/writeback tests;
- build tests;
- playtest event/backpin/regression tests;
- main hero-flow E2E;
- other-game E2E;
- Judge Mode cached E2E;
- offline integration recovery E2E.

## 7. Documentation DoD

- root setup and architecture docs current;
- every module README current;
- frontend tool/module extension guide current;
- API and event docs generated/current;
- Blender, Unity, render, build, playtest docs current;
- third-party licenses recorded;
- demo script and reset steps tested;
- no documentation claims unsupported behavior.

## 8. Honesty DoD

- no mock or cached result shown as live;
- no hard-coded performance improvement presented as measured;
- no AI evaluation described as a human study;
- no unrestricted code execution hidden behind an adapter;
- no “complete” label while a declared critical flow is only a static page.
