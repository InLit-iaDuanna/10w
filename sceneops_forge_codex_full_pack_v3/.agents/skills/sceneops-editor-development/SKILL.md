---
name: sceneops-editor-development
description: Build a dockable SceneOps editor and register it without coupling the feature to ForgeShell or Dockview internals.
---

# SceneOps Editor Development

1. Read `design.md`, `FRONTEND_INTEGRATION.md`, target module docs, and the editor registry contract.
2. Define editor ID, title, category, lazy loader, placement, minimum size, integration and permission requirements, context binding, and serializable local state.
3. Build loading, empty, success, failure, offline, permission, and retry states.
4. Use the generated API client and TanStack Query for server data.
5. Use shared `WorkbenchContext`; support follow-global and pinned context where relevant.
6. Use typed commands rather than directly mutating shell state.
7. Add editor registry, local-state restore, context, and failure-state tests.
8. Add a compact example to module docs and frontend integration docs when the extension pattern changes.

Never import Dockview directly into a feature editor unless the shell contract explicitly requires it. Never call external tool SDKs from React.
