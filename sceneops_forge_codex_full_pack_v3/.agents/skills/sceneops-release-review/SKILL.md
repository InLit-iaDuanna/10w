---
name: sceneops-release-review
description: Run the final owner-level review for architecture, security, tests, documentation, demo readiness, truthfulness, and reuse.
---

# SceneOps Release Review

Spawn parallel read-only reviews for:

- architecture and module boundaries;
- security and external-tool permissions;
- frontend shell and accessibility;
- tests and failure recovery;
- documentation and unsupported claims;
- hero-flow and second-game reuse.

Wait for all reviews. Consolidate findings by severity. Fix release blockers, rerun all required tests, and update `STATUS.md`.

A release may not pass while:

- the chat-only home is broken;
- module boundaries are bypassed;
- live/mock/cached is misleading;
- unrestricted external code execution exists;
- the hero flow or other-game flow fails;
- documentation is stale;
- Judge Mode cannot reset.
