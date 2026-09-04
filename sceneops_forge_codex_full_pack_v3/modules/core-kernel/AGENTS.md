# core-kernel module rules

- Own only cross-module state-machine and mutation-safety policy; domain entities stay in feature modules.
- Public frontend imports go through `frontend/src/index.ts` only.
- Public backend imports go through `core_kernel/__init__.py` only.
- `frontend/src/generated/module-manifest.ts` and `backend/src/core_kernel/generated_manifest.py` are generated.
- Run `scripts/module-test core-kernel` and `scripts/module-validate` before handoff.
