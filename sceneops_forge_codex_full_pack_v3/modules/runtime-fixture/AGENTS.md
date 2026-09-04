# runtime-fixture module rules

- This tiny module exists only to prove module registration and deterministic Mock outcomes.
- Do not add business behavior or external tool calls.
- Public frontend imports go through `frontend/src/index.ts`; public backend imports go through `runtime_fixture/__init__.py`.
- `frontend/src/generated/module-manifest.ts` and `backend/src/runtime_fixture/generated_manifest.py` are generated.
- Run `scripts/module-test runtime-fixture` before handoff.
