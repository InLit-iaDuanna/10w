---
name: sceneops-adapter-integration
description: Add a safe external-tool adapter for Blender, Unity, ComfyUI, Git, storage, build, or playtest execution.
---

# SceneOps Adapter Integration

1. Read root security and adapter rules.
2. Define capability and typed command contracts before vendor code.
3. Implement health check and capability report.
4. Restrict paths to configured project roots.
5. Use an explicit command allowlist and schema validation.
6. Implement dry-run, timeout, cancellation, progress, structured logs, error mapping, provenance, and idempotency.
7. Add deterministic mock and cached replay support.
8. Add success, offline, timeout, invalid-command, path-boundary, cancellation, duplicate-request, and rollback/compensation tests.
9. Document setup, pinned version/commit, license, ports, permissions, and troubleshooting.

Never expose unrestricted Python, C#, shell, or arbitrary file access through the application.
