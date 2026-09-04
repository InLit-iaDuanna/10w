# Engine Unity Module Rules

## Ownership

This module owns Unity command contracts, adapter orchestration, identity mapping, build manifests, deterministic Unity fixtures, and its frontend contribution. The Unity-side implementation lives in `../../integrations/unity-package/`.

Do not edit Blender, rendering, playtest, shell, or shared core internals from this module.

## Invariants

- The public application surface exposes only the commands listed in `module.yaml`; arbitrary C# and arbitrary file execution are forbidden.
- All project and asset paths resolve beneath an explicitly configured Unity project root.
- Mutations require a typed `ChangeSet`, a matching base version, and approval when the command policy requires it.
- Asset, Prefab, and scene-instance identities are distinct. Renames retain IDs; copies receive a new scene-instance ID.
- Every result reports `live`, `cached`, `mock`, `planned`, or `blocked` truthfully.
- Build and test failures retain structured logs.

## Commands

Run backend and contract tests from this directory:

```text
PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/engine_unity/tests -v
node --test frontend/src/tests/*.test.mjs
```

Run the real Unity smoke flow only on a host with Unity 2022.3 available:

```text
python3 scripts/run_unity_smoke.py --unity /path/to/Unity
```

Unity `Library`, `Temp`, `Logs`, `obj`, and build output are generated and must not be committed.

## Acceptance

The module-local contract, adapter, identity, approval, cancellation/retry, build-manifest, frontend-state, and Unity package tests must pass. A missing Unity host is reported as blocked, never replaced with a mock claim.
