---
name: sceneops-blender-technical-artist
description: Edit registered native Blender assets and return their GLB versions to the current Web Demo.
---

Read project.assets.list and environment.scene.read to identify the selected source version and requested shared instances. Use blender.asset.begin to create one editable candidate from that exact source. A procedural recipe is converted once; a Blender version reopens its saved .blend. Preserve existing free geometry and materials.

Read the begin result's candidate_id, node_ids and object dimensions. blender.asset.edit addresses node_id, never display name. Edit dimensions_m uses Blender X/Y/Z (Z up); exported overall dimensions use glTF X/Y/Z (Y up). base_color is linear RGBA, each value 0–1. The frame stays static; only the leaf belongs under the hinge. Avoid changing identity or hierarchy to achieve a cosmetic change.

Use blender.asset.publish after edits. It saves the native source and exports the runtime GLB, registers a version and updates only requested object_ids (omitting them means all current shared references). Read the current scene version immediately before publication. If references conflict, keep the saved source, reread scene state and publish the same candidate to finish applying it; never restart modeling to retry registration. A completed candidate is immutable; begin a new candidate for subsequent edits.

Manual candidates belong to the user and cannot be edited by the Agent. Unknown results require readback; do not recreate or extend authorization to replay writes. Paths, sockets, programs and permissions are server-owned. Available typed commands define actual production abilities; this skill does not enable arbitrary Python.

Materialize, check, build, then explicitly open the new Demo. For an existing registered game, call code.demo_runtime.preview. If ready with changed files, call code.demo_runtime.upgrade with the returned preview_id before materialization. This versioned three-way migration preserves unrelated custom code; if conflicts are reported, inspect and resolve the actual source through a separately scoped code edit. Do not overwrite a conflicting file. A GLB export alone is not game integration. Verify appearance, hinge, collision and existing key/distance/angle independently. Claim visual understanding only when an image was actually provided to the model.
