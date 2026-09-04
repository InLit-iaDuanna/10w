# Logic Studio Module Rules

## Ownership

This module owns gameplay graphs, deterministic graph validation and simulation,
logic editor contributions, generated-test plans, and reviewed Unity C# change
proposals. It does not own Unity project mutation, builds, or ForgeShell layout.

## Invariants

- `GameplayGraph` is the canonical gameplay source; generated configuration,
  tests, and code proposals must name its graph and version.
- Scene links use declared `sceneops_id` values. Display names and paths are not
  identity.
- Deterministic validators never delegate correctness to an LLM.
- C# remains a proposal until a typed ChangeSet is dry-run, explicitly approved,
  applied by an allowlisted Unity adapter, and compile/test validated.
- Execution mode is always one of `live`, `cached`, `mock`, `planned`, or
  `blocked`.

## Public boundaries

- Frontend consumers import only `frontend/src/index.ts`.
- Backend consumers import only `logic_studio` or the documented adapter
  protocol in `adapters/unity_code_generation.py`.
- Do not import another module's internal path.

## Commands

```text
cd modules/logic-studio/frontend && npm test
cd modules/logic-studio/backend && PYTHONPATH=src python3 -m unittest discover -s src/logic_studio/tests -t src -v
```

## Generated files

No checked-in file is generated in this baseline. When the shared OpenAPI client
exists, generated network types must replace any host-facing compatibility types;
do not hand-edit generated output.

## Acceptance

Run both module-local test commands. Verify manifest/event schemas, both example
bindings, graph diagnostics, ChangeSet approval/rollback, all editor states, and
conversation-to-editor command creation.
