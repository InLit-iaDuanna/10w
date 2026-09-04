# Asset Library Module Rules

## Ownership

This module owns asset catalog records, searchable read models, publication policy,
usage/build references, and the Asset Browser/Inspector contribution. Blender
processing belongs to `asset-factory` and `integrations/blender-addon`.

## Invariants

- `asset_id`, `source_asset_id`, `sceneops_id`, `asset_version_id`, and
  `scene_instance_id` are distinct identities.
- Published versions are immutable. A change creates a new version.
- A blocking failed quality gate can never be published.
- Every artifact and UI state exposes `live`, `cached`, `mock`, `planned`, or
  `blocked` truthfully.
- Other modules may import only `asset_library.__init__` or
  `frontend/src/index.ts`.

## Commands

```text
PYTHONPATH=modules/asset-library/backend/src python3 -m unittest discover -s modules/asset-library/backend/tests -v
node --test modules/asset-library/frontend/src/tests/*.test.ts
```

## Acceptance

The module must answer an asset's origin, published versions, scene instances,
Unity status, and including builds; browser filtering and all visible failure
states must remain deterministic.
