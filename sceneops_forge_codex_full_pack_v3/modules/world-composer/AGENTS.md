# World Composer Working Rules

## Ownership

- This module owns scene understanding, stable scene selection, spatial annotations, world graphs, paths, regions, navigation/lighting inspection, placement proposals, deterministic recipes, captures, issue restoration, and level gates.
- Gameplay implementation, asset publishing, shell layout mechanics, and Blender/Unity integration internals remain outside this module.

## Invariants

- `sceneops_id` is the only object identity. Display names and hierarchy paths are locators only.
- Canonical spatial data is meters in a right-handed, Y-up, negative-Z-forward frame; every serialized spatial value declares its frame.
- Viewer interactions create typed ChangeSets. They never directly mutate a DCC, engine, or project file.
- Voice input creates a draft annotation and cannot execute a mutation.
- Procedural or graybox output always records a versioned recipe, seed, and explicit constraints.
- Every result carries one of `live`, `cached`, `mock`, `planned`, or `blocked`.

## Public surfaces

- Frontend consumers import only `frontend/src/index.ts`.
- External integrations implement the documented `WorldMutationAdapter` protocol; vendor SDK types may not cross that boundary.
- Contract examples and JSON Schemas under `contracts/` are versioned public disk formats.

## Commands

```text
npm test --prefix modules/world-composer/frontend
```

Run the scene-viewer package tests separately when its public spatial primitives change.

## Acceptance

- Keep all required editor definitions lazy and preserve visible loading, empty, ready, failed, disconnected, and permission-denied states.
- Test stable selection, annotation round-trips, placement approval, camera restoration, overlay behavior, viewport suspension, both demo projects, and each level gate.
- Do not label deterministic fixtures or adapters as live.
