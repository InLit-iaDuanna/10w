---
name: sceneops-contract-first
description: Define or change SceneOps API, event, manifest, identity, or job contracts with compatibility, generation, and tests before implementation.
---

# SceneOps Contract-First Change

1. Identify the owning module and affected consumers.
2. Check whether the change can remain private. Prefer private change.
3. If public, define the smallest schema and invariant.
4. Update Pydantic/OpenAPI or versioned JSON Schema as appropriate.
5. Add compatibility, serialization, invalid-input, and migration tests.
6. Generate frontend types; do not hand-edit generated code.
7. Update producers, consumers, examples, API/event docs, and module manifests.
8. Run cross-module contract tests.
9. Record breaking or high-impact decisions in an ADR.

Never change stable IDs, units, coordinate systems, event envelopes, or state-machine semantics casually.
