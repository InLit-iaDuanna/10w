# Build Release Module Rules

## Ownership

This module owns build matrices, recorded build manifests, release gates,
release candidates, patch notes, local or Judge deployment records, feedback
links, and approved rollback plans.

It does not own Unity build execution, source-control mutation, ChangeSet
approval, playtest execution, asset validation, or the application shell.
Those capabilities are consumed only through typed public records and adapter
ports.

## Invariants

- A release candidate never becomes ready from dirty or unidentified source.
- Every required blocking gate is present, current for the candidate commit,
  backed by available evidence, and passed before deployment.
- Deploy and rollback actions always require explicit role-based approval.
- Live/cached source and live mutations fail closed unless a trusted
  `ReleaseAuthority` verifies source attestation and approval records.
- Patch-note change entries retain an approved ChangeSet ID; human edits may
  change wording, not provenance.
- `live`, `cached`, `mock`, `planned`, and `blocked` labels describe what
  actually happened. Cached Judge evidence never becomes a live deployment.
- Paths accepted by the local deployment adapter are relative to configured
  roots, cannot escape them, and isolate active state by target, project, game,
  and build target.
- SHA-256 is used only for the specified manifest and artifact-integrity
  boundary, where ordinary IDs cannot detect stale or altered bytes.

## Public surfaces

- Backend: `backend/src/build_release/__init__.py`
- Frontend: `frontend/src/index.ts`
- On-disk contracts: `contracts/`

Do not expose repositories or adapter internals as cross-module APIs.

## Commands

```text
PYTHONPATH=modules/build-release/backend/src python3 -m unittest discover \
  -s modules/build-release/backend/tests -p 'test_*.py'
node --experimental-strip-types --test \
  modules/build-release/frontend/src/tests/*.test.ts
```

## Integration state

The standalone module ships deterministic test adapters and a safe local-file
deployment adapter. The real Unity artifact producer, generated host module
catalog, persistent database, event transport, and shell registry are upstream
integration points and must remain `planned` or `blocked` until supplied.
