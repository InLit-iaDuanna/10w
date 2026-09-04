# World mutation adapter protocol

World Composer exposes `WorldMutationAdapter` from its public frontend entry as a vendor-neutral typed port. Editor code does not import Unity, Blender, shell or file-system APIs.

An implementation must provide:

- health and versioned capability report;
- allowlisted mutation kinds;
- required dry-run;
- core ChangeSet/Approval references;
- AbortSignal cancellation and explicit timeout policy;
- bounded retry policy with command-ID idempotency;
- progress events and structured UTC logs;
- mapped, retryable error codes;
- result provenance and validation;
- snapshot-scoped rollback/compensation.

Allowed v1 mutation kinds are `world.scene-object.place`, `world.graph.update`, `world.graybox.apply`, `world.procedural-placement.apply`, and `world.lighting-target.apply`. Actual Unity or Blender implementations belong in their integration-owned paths and consume this protocol; do not place vendor SDK calls in this module.

`DeterministicMockWorldMutationAdapter` is the only current implementation. It mutates no external data and every result remains `mock`.
