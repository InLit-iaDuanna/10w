# SceneOps Editable Content

Keep editable authority in its existing public source:

- Shared procedural visuals live in project asset recipes and versions. Updating a shared recipe affects only scene instances explicitly rebound to the new asset version; state the affected instance identities.
- Placement, transform, supported behavior identity, and behavior parameters live in versioned project scene instances. A single-instance transform must not move another instance.
- Game-specific mechanics and their real parameters live in focused, ordinary project source modules. Import those parameters in runtime behavior and UI instead of copying values into a second hard-coded location.

The files `.sceneops/demo-content.json` and `src/game/sceneops-demo-content.ts`, retained build candidates, and `dist` are derived outputs. Never edit them with source tools. Materialization may replace only the two derived content files and must preserve model-authored behavior modules.

Use stable asset, instance, and behavior identities returned by the tools. Read the current version before every content mutation and submit that exact version. On conflicts, reread and decide from the new state; do not guess IDs or broaden scope. Do not invent `.blend`, `.fbx`, preview, or runtime artifact paths.

For a follow-up goal, continue the same registered workspace and task history. Modify the actual source for that request, preserve unrelated content, rebuild into a new candidate, and keep the previous playable candidate if the update fails.
