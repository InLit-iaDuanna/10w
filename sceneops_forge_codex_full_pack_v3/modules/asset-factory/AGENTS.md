# Asset Factory Module Rules

## Ownership

This module owns AssetSpec-to-publication orchestration, asset ChangeSets,
processing state, quality-gate aggregation, and the Asset Factory/QA editor. The
asset catalog is consumed only through `asset_library`'s public surface; Blender
is consumed only through `sceneops_blender`'s public typed adapter.

## Invariants

- Dry-run is `planned` and never invokes Blender.
- Mutations require an approved ChangeSet and adapter authorization.
- Caller idempotency keys cannot be reused with different requests.
- A rollback snapshot precedes the first mutating operation.
- Failed blocking gates stop before export/publication.
- Live, cached, mock, planned, and blocked are never interchangeable.

## Commands

```text
PYTHONPATH=modules/asset-library/backend/src:integrations/blender-addon/src:modules/asset-factory/backend/src python3 -m unittest discover -s modules/asset-factory/backend/tests -v
node --test modules/asset-factory/frontend/src/tests/*.test.ts
```

## Acceptance

The hero key and Warehouse Escape obstacle must run through the same recipe. A
failure preserves logs and completed steps; retry, cancellation, timeout,
rollback, and publication gates have independent tests.
