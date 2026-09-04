# Asset Library

Asset Library is the canonical catalog and publication boundary for SceneOps 3D
assets. It keeps source assets, source objects, immutable published versions,
scene usage, Unity import state, including builds, licenses, and provenance in one
queryable record.

## Users and tools

Artists and technical artists use **Asset Browser** (`asset.browser`) to search
and filter assets. **Asset Inspector** (`asset.inspector`) exposes dimensions,
triangles, materials, textures, UV, rig, animations, LODs, collider, license,
AI provenance, scene instances, Unity state, and builds. The editors are lazy
module contributions and never open on the chat-only home automatically.

## Public surface

- Python: `asset_library` exports the Pydantic contract models,
  `InMemoryAssetRepository`, `AssetLibraryService`, and `create_router`.
- TypeScript: `frontend/src/index.ts` exports the module contribution, browser
  query model, filters, query keys, and inspector-state builder.
- Command intents: `asset.search`, `asset.version.publish`.
- Event: `asset.version.published@1`.

The module owns asset catalog records. It stores external scene, Unity, and build
identifiers as stable references; it does not mutate those systems.

## Publication rules

A version is publishable only when trusted finalized-run storage resolves the
exact `(asset_id, asset_version_id, change_set_id)` candidate, a server-owned
authority verifies its approval scope, trusted storage verifies every artifact
size/checksum, all catalog-owned required gates exist, and every blocking gate
passes. All three boundaries deny by default when the composition root omits
them. The public request carries IDs and approval evidence, never a caller-built
candidate. Publication inserts a new immutable `AssetVersion`; source files are
never overwritten.
Artifact SHA-256 values are required because immutable artifact verification and
provenance cannot be provided by a filename or database version alone.

## Integration and degraded behavior

`artifact-store` is required by the assembled application but the domain service
can be tested with the in-memory repository. Unity is optional. If it is absent,
the inspector displays `unavailable` rather than claiming import success.
Loading, empty, permission denied, disconnected, failed/retry, and success states
are explicit view models.

## Setup and tests

From the specification root:

```text
PYTHONPATH=modules/asset-library/backend/src python3 -m unittest discover -s modules/asset-library/backend/tests -v
node --test modules/asset-library/frontend/src/tests/*.test.ts
```

Fixture records are under `fixtures/` and are always labelled `mock`.

## Example

```python
from asset_library import AssetLibraryService, AssetSearchFilter

results = service.search(AssetSearchFilter(query="key", has_collider=True))
```

## Known limitations

The root module runtime, generated OpenAPI TypeScript client, artifact-store, and
Unity consumer were absent at this task's parallel starting commit. Their wiring
is therefore `planned`; no local result is represented as a live integration.
