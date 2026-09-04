# AI Playtest Module Rules

## Ownership

This module owns bounded playtest configuration, agent action selection, telemetry-derived observations, evidence, issue detection, source backpinning, restoration context, and same-test regression comparison.

It does not own Unity runtime implementation, project source edits, ChangeSet execution, build production, or release decisions.

## Invariants

- Every runtime call goes through `PlaytestRunnerAdapter`.
- A run and every evidence artifact expose `live`, `cached`, `mock`, `planned`, or `blocked` mode.
- Actions must be both runtime-advertised and permitted by the `TestCase` controls.
- Destructive mode requires an explicit contained-test opt-in.
- A backpin is evidence with confidence, not proof; ambiguous and rejected states remain visible.
- Fixes leave this module only as a typed `changeset.propose` request.
- Regression direction and tolerance come from the test configuration; the module never invents improvement criteria.
- AI playtesting is pre-screening and regression assistance, never a substitute for human playtesting.

## Commands

```bash
python3 -m unittest discover -s modules/ai-playtest/backend/tests -v
node --experimental-strip-types --test modules/ai-playtest/frontend/src/tests/*.test.ts
```

## Generated files

`contracts/events/*.schema.json` and `contracts/manifests/*.schema.json` are generated from Pydantic models by `backend/scripts/export_contract_schemas.py`. Do not edit them independently of the models.

## Integration contracts

- Unity or another runtime implements the public `PlaytestRunnerAdapter` protocol.
- Core/module runtime consumes only `backend/src/ai_playtest/__init__.py` and `frontend/src/index.ts`.
- Change proposals are dispatched to the owning module through `changeset.propose`; this module never executes them.

## Acceptance tests

The module-local suites cover schema validation, deterministic modes/replay, limits, telemetry recovery, all required detectors, issue/backpin states, restoration, ChangeSet proposals, exact-config regression, build mismatch, visible editor states, and limitation labels.
