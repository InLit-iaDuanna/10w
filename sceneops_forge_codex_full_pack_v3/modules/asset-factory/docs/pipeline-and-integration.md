# Asset pipeline and integration contract

The workflow consumes `asset_library.AssetSpec`, `SourceAsset`, and catalog
publication through their public package. It consumes Blender solely through
`sceneops_blender` typed commands. No Blender SDK type crosses into Asset Library.

## State machine

```text
queued -> planning -> planned
      \-> waiting_approval
      \-> running -> succeeded
                     \-> failed
                     \-> cancelled
                     \-> timed_out
                     \-> rolled_back
      \-> blocked
```

Each processing step retains its attempts, timestamps, progress, execution mode,
structured logs, artifacts, and explicit skip reason. Human approval is a real
pause. Retrying starts a new run ID and references the prior run; cancellation is
checked before and during adapter work; timeout is enforced at both pipeline and
Blender process layers. Event delivery is observational: a callback failure is
recorded as `EVENT_DELIVERY_FAILED` and cannot undo or strand the authoritative
run/publication result. Production composition should replace the callback with
a durable outbox.

The API does not accept a project filesystem root. The composition root maps the
project ID to a trusted root, supplies the approval authority, artifact verifier,
request ledger, and finalized-candidate store, and chooses an adapter already
bound to that root. Approval covers the entire ChangeSet plus normalized Blender
operations, targets, paths, and parameters. Publication resolves its candidate
from finalized-run storage rather than from the caller. Final version paths are
immutable: run-staged exports are promoted with exclusive creation and are
removed if the catalog transaction rejects them.

## Integration sequence after parallel prerequisites land

1. Map `AssetChangeSet` to the core ChangeSet envelope without weakening fields.
2. Register module router/jobs through generated module-runtime catalogs.
3. Generate the shared TypeScript client from FastAPI OpenAPI and replace the
   temporary frontend command contract names.
4. Replace the local artifact verifier, request ledger, and candidate store with
   durable artifact-store/outbox, distributed idempotency, and finalized-run
   implementations.
5. Let the Unity module consume only the published manifest/event.

Until those steps happen, their status is `planned`; mock fixtures remain `mock`.
