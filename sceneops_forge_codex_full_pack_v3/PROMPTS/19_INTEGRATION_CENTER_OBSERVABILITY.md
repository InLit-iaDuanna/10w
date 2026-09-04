# 19 — Integration Center, Workers, Logs, and Observability

## Recommended agent / model

Use `module_builder` with Terra/high; use `security_reviewer` for permissions and networking.

## Objective

Create a unified, modular system for integration health, capabilities, workers, jobs, logs, traces, correlation IDs, and recovery without coupling UI modules to tool SDKs.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/integration-center/**
- modules/observability/**
- shared adapter gateway/event transport assigned by principal
- docs/tests/fixtures

Do not implement tool-specific production logic owned by adapters.

## Tasks

1. Build Integration Health and Worker Monitor editors.
2. Model connected, disconnected, degraded, incompatible, busy, unauthorized, and unknown states.
3. Show tool/version/capabilities, last seen, current job, queue, logs, and recommended actions.
4. Implement one API/event gateway for module progress and structured logs.
5. Preserve project/run/job/correlation/causation IDs.
6. Add log levels, searchable structured fields, artifact links, and downloadable diagnostic bundle.
7. Implement timeout, cancel, retry, resume, worker restart guidance, and circuit-breaker behavior where appropriate.
8. Ensure secrets and sensitive paths are redacted.
9. Add Judge Mode health summary and cached fallback explanation.
10. Add health fixtures for Blender, Unity, ComfyUI, Git, artifact store, and workers.

## Acceptance criteria

- Feature modules can query health/capabilities without vendor imports.
- Users see exactly why an action is unavailable and how to recover.
- Logs correlate across modules and tools.
- Retry/resume does not duplicate completed side effects.
- Diagnostic exports do not expose secrets.
- Judge Mode remains understandable if a tool disconnects.

## Required tests

- all health states
- version/capability mismatch
- redaction
- timeout/cancel/retry/resume
- duplicate-event/idempotency
- circuit behavior
- diagnostic bundle
- event reconnect
- Judge Mode fallback

## Do not

- Do not centralize domain logic in observability.
- Do not log secrets, full tokens, or unrestricted local paths.
- Do not tell users an integration is healthy from a static flag.
- Do not retry non-idempotent actions blindly.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
