# SceneOps Forge Module Contract

## 1. Why modules exist

Each capability is developed in its own folder so that:

- Codex can assign one bounded module to one conversation or subagent;
- ownership is clear;
- tests and docs stay next to the feature;
- modules can be disabled or replaced;
- frontend, backend, jobs, adapters, and workflows for one capability remain discoverable;
- the app shell does not become a monolith.

## 2. Required module layout

```text
modules/<module-id>/
├─ AGENTS.md
├─ README.md
├─ module.yaml
├─ contracts/
│  ├─ events/
│  ├─ manifests/
│  └─ examples/
├─ frontend/
│  ├─ package.json
│  └─ src/
│     ├─ index.ts
│     ├─ manifest.ts
│     ├─ editors/
│     ├─ components/
│     ├─ commands/
│     ├─ hooks/
│     ├─ state/
│     ├─ fixtures/
│     ├─ generated/
│     └─ tests/
├─ backend/
│  ├─ pyproject.toml
│  └─ src/<module_package>/
│     ├─ __init__.py
│     ├─ router.py
│     ├─ schemas.py
│     ├─ service.py
│     ├─ repository.py
│     ├─ jobs.py
│     └─ tests/
├─ workers/
├─ adapters/
├─ workflows/
├─ e2e/
└─ docs/
```

A module may omit unused folders. Do not create empty folders merely to appear complete.

## 3. Module manifest

`module.yaml` is required.

```yaml
schema_version: 1
id: asset-factory
version: 0.1.0
title: Asset Factory
description: Produces and publishes game-ready 3D assets.
status: active
feature_flag: asset_factory

requires:
  modules:
    - core-kernel
    - module-runtime
    - asset-library
  integrations:
    - blender
    - artifact-store
  optional_integrations:
    - comfyui
    - unity

contributes:
  editors:
    - asset.factory
    - asset.validation
  commands:
    - asset.spec.create
    - asset.process.run
    - asset.version.publish
  events:
    - asset.spec.created@1
    - asset.version.published@1
  jobs:
    - asset.preflight
    - asset.blender.process
    - asset.publish
  workflows:
    - concept-to-engine-asset
  policy_gates:
    - asset.geometry
    - asset.materials

permissions:
  - asset:read
  - asset:write
  - asset:publish

entrypoints:
  frontend: ./frontend/src/index.ts
  backend: asset_factory
```

## 4. Public surface

### Frontend

Only `frontend/src/index.ts` is public.

It may export:

- `moduleContribution`;
- editor definitions;
- command definitions;
- public hooks/types intended for declared consumers.

Do not expose internal components unless a real second module needs them.

### Backend

Only package `__init__.py` and documented service protocols are public.

Other modules must not import repositories or internal ORM models.

## 5. Contribution types

A module contribution can register:

```ts
interface ModuleContribution {
  manifest: ModuleManifest;
  editors?: EditorDefinition[];
  commands?: WorkbenchCommandDefinition[];
  eventHandlers?: WorkbenchEventHandler[];
  navigation?: ToolLibraryEntry[];
  workspacePresets?: WorkspacePresetContribution[];
  contextResolvers?: ContextResolver[];
}
```

Backend contribution concept:

```py
class BackendModuleContribution(Protocol):
    manifest: ModuleManifest
    router: APIRouter | None
    jobs: list[JobDefinition]
    event_handlers: list[EventHandler]
    policy_gates: list[PolicyGate]
```

## 6. Cross-module communication

Use, in order of preference:

1. stable entity IDs;
2. typed commands;
3. typed events;
4. declared public service protocols;
5. shared core contracts.

Never use:

- direct internal imports;
- shared mutable module state;
- hidden database joins against another module's private tables;
- DOM events as application-domain events;
- stringly typed command names without validation.

## 7. Dependency rules

- Dependencies are declared in `module.yaml`.
- Build fails on undeclared imports.
- Build fails on dependency cycles.
- Core modules cannot depend on production modules.
- Optional integrations may fail without disabling the entire module if a valid degraded mode exists.
- A module must explain missing integrations in the UI.

## 8. Module database ownership

- Each module owns its tables and migrations.
- Cross-module references store stable IDs, not foreign ORM objects.
- Cross-module read models may be built through events or explicit APIs.
- Modules cannot mutate another module's tables.
- Migration order follows module dependencies.

## 9. Module editor rules

Each editor definition includes:

- stable ID;
- title and icon;
- category;
- lazy component loader;
- default placement;
- minimum size;
- singleton or multi-instance behavior;
- required permissions;
- required and optional integrations;
- serializable local state;
- context binding support;
- empty, loading, failed, disconnected, and permission states.

## 10. Module command rules

Each command defines:

```ts
interface WorkbenchCommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  inputSchema: ZodSchema<TInput>;
  requiredPermissions: string[];
  requiredIntegrations?: string[];
  canExecute(context: WorkbenchContext, input: TInput): CommandAvailability;
  execute(context: CommandExecutionContext, input: TInput): Promise<TResult>;
}
```

Commands can be invoked from chat, buttons, menus, shortcuts, or workflows. There is one implementation.

## 11. Module event rules

- version schemas;
- use past-tense event names;
- include correlation and causation IDs;
- consumers are idempotent;
- module docs list producers and consumers;
- never change a published event payload incompatibly without a new version.

## 12. Module tests

Every module must include:

- manifest/schema test;
- public API test;
- success path;
- failure path;
- permission/integration-disabled state;
- deterministic fixture;
- module-level E2E if it has a critical editor flow;
- docs example validation where feasible.

Run convention:

```text
pnpm test:module <module-id>
uv run pytest modules/<module-id>/backend
pnpm e2e:module <module-id>
```

Codex should create equivalent scripts that fit the actual repository.

## 13. Module documentation

`README.md` answers:

- what problem the module solves;
- users;
- public editors;
- public commands/events;
- data owned;
- integrations;
- degraded behavior;
- setup;
- tests;
- examples;
- known limitations.

`docs/` contains deeper integration notes.

## 14. Module-level AGENTS.md

Each module has a short `AGENTS.md` with:

- ownership boundaries;
- module-specific commands;
- important invariants;
- files that are generated;
- integration contracts;
- acceptance tests.

Keep it focused. Do not duplicate the entire root file.

## 15. Module completion checklist

- [ ] manifest valid;
- [ ] no undeclared dependencies;
- [ ] no internal cross-module imports;
- [ ] public API documented;
- [ ] editor/command/job contributions registered;
- [ ] happy path works;
- [ ] failure path visible;
- [ ] integration-offline behavior works;
- [ ] fixtures deterministic;
- [ ] tests pass independently;
- [ ] module README current;
- [ ] root module map generated;
- [ ] Live/Mock/Cached correctly labelled.
