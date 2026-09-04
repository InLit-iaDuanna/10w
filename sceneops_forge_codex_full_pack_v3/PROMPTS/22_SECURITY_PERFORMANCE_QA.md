# 22 — Security, Performance, Accessibility, and QA Hardening

## Recommended agent / model

Spawn `security_reviewer`, `qa_reviewer`, `code_explorer`, and a browser/debug agent in parallel; principal coordinates fixes.

## Objective

Run a release-level hardening pass across the modular system, external adapters, chat actions, docking UI, 3D performance, jobs, tests, and documentation.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Review all code read-only first. Fixes are assigned to owning modules/agents. Do not let reviewers make broad cross-module edits directly.

## Tasks

1. Threat-model assistant actions, module manifests, command bus, file paths, Blender/Unity/ComfyUI/Git adapters, artifact uploads, secrets, logs, popout windows, and approvals.
2. Find arbitrary-code, path traversal, command injection, unsafe deserialization, credential leakage, overly broad permissions, and missing approval risks.
3. Profile initial chat-only load, tool lazy load, drawer/docking interaction, 3D resize, hidden rendering, asset grid, logs, graphs, and event streaming.
4. Verify no expensive editor remounts during resize and no hidden WebGL loops.
5. Verify accessibility: keyboard alternatives, focus, status not color-only, reduced motion, target size, error recovery.
6. Review module boundaries, duplicated contracts, stale generated clients, dependency cycles, and giant stores/files.
7. Exercise external-tool offline, timeout, cancel, retry, resume, duplicate request, and partial completion.
8. Run all release-blocking tests and inspect failures instead of merely rerunning.
9. Review unsupported product claims and live/mock/cached truthfulness.
10. Produce a prioritized report, assign fixes, rerun, and close blockers.

## Acceptance criteria

- No known critical/high security issue remains unaddressed or explicitly accepted with rationale.
- Initial chat-only screen and shell meet performance budgets defined from actual measurements.
- Hidden 3D/game views stop continuous work.
- Keyboard-only Judge Mode is possible for core actions.
- All release blocker tests pass.
- Claims, docs, and UI modes are truthful.
- No module boundary violation remains.

## Required tests

- security unit/integration tests
- path/command allowlist
- permission/approval
- secret redaction
- layout and popout security
- load/interaction performance measurements
- hidden render suspension
- event reconnect/backpressure
- accessibility automated/manual checks
- complete test suite
- documentation drift checks

## Do not

- Do not “fix” performance by removing functionality without product review.
- Do not silence security warnings.
- Do not weaken tests.
- Do not accept mock evidence as live.
- Do not leave findings only in chat; write a review artifact and update STATUS.md.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
