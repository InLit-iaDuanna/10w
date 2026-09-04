# SceneOps Forge Subagent Orchestration

## 1. Principle

The principal agent owns architecture, contracts, integration, sequencing, and final quality. Subagents own bounded tasks with explicit file boundaries.

Parallelize read-heavy and independent work. Serialize shared-contract and cross-module writes.

## 2. Recommended agents

| Agent | Primary ownership | Model tier |
|---|---|---|
| `code_explorer` | read-only repository map and impact discovery | D |
| `forge_architect` | contracts, module boundaries, state machines, critical ADRs | A |
| `module_runtime_builder` | module schema, generator, registries, dependency validation | B/C |
| `shell_ui_builder` | chat-only home, edge pulls, Dockview, workspace persistence | B |
| `product_graph_builder` | project, feature, task, production-thread modules | B/C |
| `asset_blender_builder` | asset library/factory, Blender add-on/adapter, stable export | A/B |
| `character_animation_builder` | character and animation module | B |
| `world_logic_builder` | world, annotations, gameplay graph, code change flow | A/B |
| `render_ops_builder` | AOV, ComfyUI, recipes, writeback, validation | B |
| `unity_engine_builder` | Unity package, ID mapping, import, tests, build | A/B |
| `playtest_builder` | AI actions, telemetry, evidence, backpin, regression | A/B |
| `collaboration_release_builder` | version, review, approval, release | B/C |
| `qa_reviewer` | correctness, tests, maintainability | A read-only |
| `security_reviewer` | command/path/tool boundary review | A read-only |
| `docs_maintainer` | docs synchronization and examples | D |
| `fixture_worker` | deterministic mock/cached fixtures | D |

## 3. File ownership

Before spawning write agents, the principal records ownership in `STATUS.md`:

```text
Agent: shell_ui_builder
Owns:
- apps/web/src/shell/**
- modules/conversation-home/frontend/**
- modules/forge-shell/**
- related tests/docs
Must not edit:
- core contracts
- Blender/Unity integrations
```

No two write agents edit the same files concurrently.

## 4. Worktrees

Use worktrees or isolated branches for parallel write tasks when supported.

Naming:

```text
agent/<agent-name>/<task-slug>
```

Each agent:

- starts from the recorded base commit;
- commits only owned files;
- runs module-local tests;
- writes a handoff summary;
- does not merge itself.

The principal reviews and merges.

## 5. When to spawn

Good parallel candidates:

- repository exploration;
- module READMEs after contracts freeze;
- independent UI editors;
- fixtures;
- unit tests for separate modules;
- docs and license inventory;
- read-only architecture/security reviews.

Poor parallel candidates:

- core contracts;
- global migrations;
- module registry format;
- stable ID mapping;
- shared event envelope;
- shell state architecture;
- integration of a hero flow across many modules.

## 6. Spawn prompt structure

Every delegation includes:

1. role;
2. exact goal;
3. files allowed;
4. files forbidden;
5. contracts to consume;
6. acceptance criteria;
7. commands to run;
8. expected return format;
9. instruction to stop if a public contract must change unexpectedly.

## 7. Review pattern

For high-risk work:

```text
explorer maps path
→ builder implements
→ test agent validates
→ security/reviewer inspects read-only
→ principal integrates
```

## 8. Handoff artifact

Each subagent writes or returns:

```markdown
# Handoff

## Scope
## Base commit
## Changed files
## Public contracts changed
## Tests and results
## Manual verification
## Known risks
## Required integration steps
## Suggested next task
```

## 9. New conversation continuation

When the main context becomes noisy, start a new conversation using `TEMPLATES/NEW_CONVERSATION_HANDOFF.md` and attach/reference:

- current commit;
- `STATUS.md`;
- `EXECUTION_PLAN.md`;
- relevant ADRs;
- failed test logs;
- exact module ownership.

Do not rely on unstated chat memory.

## 10. Stop conditions

A subagent stops and reports instead of improvising when:

- required public contract is missing or inconsistent;
- another agent owns the required file;
- a destructive operation requires approval;
- external tool credentials are missing;
- the task would violate module dependency rules;
- a test reveals an architectural issue outside scope.
