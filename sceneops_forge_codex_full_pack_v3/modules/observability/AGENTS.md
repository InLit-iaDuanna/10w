# Observability Module Rules

- This module owns correlation-aware progress events, structured logs, reconnectable event delivery, redaction, and diagnostic bundles.
- It must not own integration-specific health logic, vendor SDK calls, or feature-domain state machines.
- Public Python consumers import only from `observability`; frontend consumers import only from `frontend/src/index.ts`.
- Redaction happens before persistence and again before diagnostic export. Correlation identifiers are preserved verbatim.
- Duplicate event IDs are idempotent only when the complete producer payload matches; conflicting reuse is an error.
- Run backend tests with `PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/observability/tests -v`.
- Run frontend contract tests with `pnpm --dir frontend test`.
