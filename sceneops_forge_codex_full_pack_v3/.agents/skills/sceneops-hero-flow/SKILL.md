---
name: sceneops-hero-flow
description: Integrate and validate the SceneOps brief-to-release or issue-to-verified-fix vertical flow across modules.
---

# SceneOps Hero Flow

1. Read the current `STATUS.md`, `EXECUTION_PLAN.md`, and hero-flow fixture.
2. List every module, command, event, artifact, approval, and test involved.
3. Verify public contracts before editing.
4. Run the flow once in deterministic mock mode.
5. Replace each mock boundary with live or cached adapters one at a time.
6. Preserve correlation IDs and artifact provenance end to end.
7. Confirm each pause, failure, retry, cancel, resume, and rollback state.
8. Add Playwright/API/integration tests for the whole flow.
9. Ensure the conversation can open every relevant evidence tool.
10. Report exact live, cached, and mock steps.

Do not hide failed nodes or fake progress. Do not hardcode improvement numbers.
