# Asset Factory

Asset Factory turns a canonical AssetSpec and source `.blend` file into reviewed,
validated GLB/FBX artifacts and an immutable AssetVersion. One versioned workflow
is reused by the Find My Way Home key and Warehouse Escape obstacle fixtures.

## Workflow

```text
preflight -> clean -> uv/material -> LOD -> collider -> turntable/AOV
          -> validate -> export -> publish
```

Optional LOD/collider nodes report a state and reason; they never silently skip.
Geometry, UV/material, and stable-identity gates are blocking. Failed gates stop
before export and publication.

## Mutation safety

Every execution accepts an `AssetChangeSet` carrying base version, previous and
proposed values, rationale, impact/risk, validation, rollback, and approval
requirements. `dry_run=true` produces a `planned` preview and does not call an
adapter. A non-dry run pauses in `waiting_approval` unless the ChangeSet is
approved. Before any Blender call, the service verifies the complete ChangeSet
and normalized command scope against a server-owned approval record and resolves
the project root from trusted project metadata. Before mutation, a versioned
`.blend` snapshot is created. Failures after that point trigger a typed rollback
command.

Blender exports first land under the run-owned `.sceneops/asset-factory/`
directory. Publication validates those bytes, creates the final GLB, FBX, and
manifest with no-clobber semantics, verifies them through the catalog artifact
boundary, and removes only newly created files if catalog publication fails.
Failed publication also discards its finalized candidate so a corrected retry is
not poisoned by stale metadata.

Idempotency is explicit: the service requires an injected request-ledger port.
The bundled in-memory implementation atomically reserves run IDs and caller keys,
and replays a prior terminal result only for the exact same validated request.
Reusing a key for different input fails with `IDEMPOTENCY_CONFLICT`; cancellation
is accepted only for a reserved run, so an unknown ID cannot plant a future
cancel. The Blender worker separately binds retry records to the complete command
in server-owned operation storage outside project content.

## Public surface

- Python: `asset_factory` exports pipeline contracts, `AssetPipelineService`,
  request-ledger/finalized-candidate ports and in-memory adapters, jobs, and
  `create_router`.
- TypeScript: `frontend/src/index.ts` exports the lazy Asset Factory/Validation
  contributions and visible run-state builder.
- Blender: only the public `sceneops_blender` typed adapter is accepted.
- Asset catalog: only public `asset_library` models/service are used.

## Execution modes

- `live`: bundled bridge actually invoked Blender now.
- `cached`: a result loaded from trusted live-run storage, keyed by workflow slot
  plus operation, and bound to the normalized full command and current source
  checksum. Verified blobs materialize each new run's working/output paths and
  are checked for size and checksum before use.
- `mock`: deterministic fixture adapter; Blender not invoked.
- `planned`: dry-run only.
- `blocked`: requested Blender integration is unavailable.

Selection is explicit. The live service does not silently auto-fallback.

## Tests

```text
PYTHONPATH=modules/asset-library/backend/src:integrations/blender-addon/src:modules/asset-factory/backend/src python3 -m unittest discover -s modules/asset-factory/backend/tests -v
node --test modules/asset-factory/frontend/src/tests/*.test.ts
```

## Known limitations

This starting commit had no core ChangeSet package, module runtime, durable run
ledger, remote artifact store, API composition root, generated TypeScript client,
Unity module, or Blender executable. The module-local Pydantic ChangeSet is an
explicit public asset-domain contract pending core adoption; distributed
idempotency and finalized-candidate persistence, shell/OpenAPI/Unity wiring, and
a filesystem-isolated Blender worker are `planned`. Direct subprocess transport
refuses project `.blend` inputs; the current host reports Blender `blocked`
unless an executable is explicitly configured.
