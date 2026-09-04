# Integration Center Module Rules

- This module owns vendor-neutral integration/worker health views, compatibility evaluation, circuit state, recovery commands, and Judge Mode health summaries.
- It must never import a Blender, Unity, ComfyUI, Git, or storage SDK. Tool-specific execution stays in adapter-owned modules.
- `observability` is consumed only through its public Python package or public frontend entrypoint.
- A connected result must come from a health probe executed for the current request. Static configuration is never reported as healthy.
- Retry and resume must carry idempotency keys and completed-step IDs. Blind retry of non-idempotent work is forbidden.
- Run backend tests with `PYTHONPATH=backend/src:../observability/backend/src python3 -m unittest discover -s backend/src/integration_center/tests -v`.
- Run frontend contract tests with `pnpm --dir frontend test`.
