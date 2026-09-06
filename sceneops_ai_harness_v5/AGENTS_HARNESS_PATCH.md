# SceneOps AI Harness Rules — Merge into root AGENTS.md

## Product core

- SceneOps is an AI production Harness, not merely a dockable 3D editor.
- Pipeline is the first-class runtime object.
- Existing product modules must expose typed Capabilities in addition to Editors.
- Codex development Subagents are not product-runtime Agents.

## Runtime AI loop

Implement and preserve:

```text
Intent → Context → Plan → Schedule → Execute → Observe → Diagnose → Adapt → Verify → Distill
```

The product must contain runtime Intent, Context, Pipeline, Agent, Model Router, Observer, Recovery and Distiller modules.

## Deterministic execution

- AI proposes and evaluates; deterministic adapters execute.
- Blender and Unity operations must pass local conformance tests before being marked Live.
- No arbitrary Python, C#, shell or unrestricted filesystem operation is exposed to product workflows.
- All mutations use typed ChangeSet, dry-run, approval, validation and rollback.

## Local tool truth

- `Mock` and `Cached` do not satisfy local Blender/Unity Live gates.
- Each local invocation records executable, version, source hash, arguments, exit code, logs, artifacts and checksums.
- Unity batchmode tests use an isolated copy/worktree when the project may be open interactively.
- A UI result does not prove the external operation succeeded.

## Open source

- Open-source libraries and connectors may be used after license, security and conformance review.
- Wrap third-party connectors behind SceneOps contracts.
- Pin releases/commits; never rely indefinitely on `main`.
- Do not outsource SceneOps-owned contracts, recovery semantics, evidence, identity or local acceptance gates.

## Completion claims

Do not claim AI Harness completion until:

- natural language compiles to a valid Pipeline;
- runtime Agents and model routing are visible;
- at least one local Blender-to-Unity path is Live;
- a failure is observed and diagnosed;
- Recovery changes the path;
- the same test verifies the fix;
- the successful run is distilled into a reusable template;
- another game uses the template without platform-source changes.
