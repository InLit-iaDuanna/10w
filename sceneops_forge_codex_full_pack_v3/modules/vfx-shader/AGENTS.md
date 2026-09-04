# VFX/Shader Module Rules

## Ownership

Only VFX/shader recipes, parameter schemas, preview plans, budgets, event bindings,
publication orchestration, fixtures, and module-local UI belong here. Do not import
another module's internal files.

## Invariants

- An AI-created visual remains a proposal until its referenced ChangeSet is approved.
- Publication requires an approved ChangeSet and a healthy Unity adapter.
- Preview fixtures are deterministic and always labelled `mock`.
- VFX is optional: any preview or publication failure reports `blocks_core_build=false`.
- Stable asset and scene object IDs are identifiers; names and paths are locators only.
- Unity/render calls go through the public `Protocol` boundaries in `adapters.py`.

## Commands

```bash
cd backend
python3 -m unittest discover -s tests -v
cd ../frontend
npm test
```

## Generated files

None. JSON fixtures are authored deterministic examples.

## Acceptance

The independent test suite must cover the manifest/public API, schemas, parameters,
quality tiers, budgets, bindings, enabled/disabled paths, degraded UI states,
provenance, adapter boundaries, approval, success, and representative failure.
