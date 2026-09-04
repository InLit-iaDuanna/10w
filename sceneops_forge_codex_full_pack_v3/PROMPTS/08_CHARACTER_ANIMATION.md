# 08 — Character and Animation Pipeline

## Recommended agent / model

Use `character_animation_builder` with Sol/high.

## Objective

Implement a complete but inspectable character/animation module that manages character specifications, rigs, skins, clips, retargeting, previews, Unity mapping, and quality evidence.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/character-animation/**
- assigned character/animation Blender and Unity adapter extensions through public protocols
- module docs/tests/fixtures

Do not edit generic asset or engine internals without explicit ownership.

## Tasks

1. Define CharacterSpec, RigVersion, SkinVersion, AnimationClipSpec, RetargetProfile, AnimatorStateSpec, and PreviewArtifact.
2. Build Character, Rig Inspector, Skin QA, Animation Timeline, Retarget Preview, and Animator Graph editors.
3. Support imported characters and optional generated sources.
4. Add checks for skeleton hierarchy, missing bones, scale/axis, skin-weight anomalies, root motion, loop seams, foot sliding heuristics, clip length, and event markers.
5. Preserve identity and provenance across source, rig, clips, and Unity character Prefab.
6. Implement approval and version comparison for rigs and clips.
7. Provide at least one simple character/animation path in a demo project.
8. Use fixed preview camera and animation regression capture.
9. Degrade cleanly when automatic rigging/retarget integrations are absent.
10. Link animation tasks and artifacts to Feature Specs.

## Acceptance criteria

- A character asset can be inspected, versioned, previewed, mapped to Unity, and tested.
- Quality checks expose evidence and limitations.
- The module can use imported rigs/clips without requiring AI generation.
- Animation changes are diffable and reversible.
- No unsupported claim of perfect auto-rigging.

## Required tests

- skeleton/scale validation
- missing bone and invalid clip
- loop/root-motion checks
- retarget profile serialization
- preview capture
- version comparison
- integration offline state
- Unity mapping contract
- provenance

## Do not

- Do not make character generation mandatory for the main hero flow.
- Do not mark heuristic animation checks as human-quality approval.
- Do not duplicate asset-library storage.
- Do not run unrestricted scripts.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
