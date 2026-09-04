# 11 — UI Studio, Audio Studio, and VFX/Shader Modules

## Recommended agent / model

Use separate `module_builder` agents with non-overlapping ownership; Terra/medium is sufficient, Sol for shader/VFX complexity.

## Objective

Implement independent UI, audio, and VFX modules with one real vertical path each, integrated into the hero feature without bloating the shell.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Parallel ownership:
- modules/ui-studio/**
- modules/audio-studio/**
- modules/vfx-shader/**

One agent per folder. Shared contract changes must return to principal.

## Tasks

UI Studio:
1. UI Flow, HUD/menu/quest prompt specs, Unity UI asset mapping, resolution/safe-area checks, localization length, and visual regression.
2. Implement a key pickup/locked-door feedback prompt in the hero flow.

Audio Studio:
3. Audio task/spec, asset import/generation reference, waveform/metadata, peak/loudness/basic format checks, event binding, AudioSource/Mixer mapping, provenance.
4. Implement key pickup and door unlock sound bindings.

VFX/Shader:
5. VFX/Shader Recipe, parameter editor, preview, quality tier, overdraw/particle budget, event binding, provenance.
6. Implement a subtle approved key or doorway highlight effect that can be enabled/disabled and tested.

Shared:
7. Each module contributes its own editors/commands/jobs and handles missing Unity/render integrations.
8. All AI-generated media remains a proposal until approved and published.
9. Add module-local fixtures, tests, docs, and second-game-compatible templates.

## Acceptance criteria

- Each module has a real usable capability, not an empty placeholder.
- The hero feature includes UI feedback, audio event binding, and one optional VFX path.
- Each module can be disabled without breaking core project/build behavior; missing media shows a clear degraded state.
- Assets are versioned and traceable.
- Unity mapping occurs through engine-unity public APIs.

## Required tests

UI: flow validation, resolution/safe-area, localization overflow, visual fixture.
Audio: format/metadata/peak/loudness fixture, missing file, event binding.
VFX: parameter schema, quality tier, budget warning, event binding.
All: module manifest, disabled/offline state, provenance, integration contract.

## Do not

- Do not merge the three modules into one giant media folder.
- Do not add media SDKs directly to React components.
- Do not claim generated sound/VFX is licensed without provenance.
- Do not make optional media failure block a core smoke build unless policy explicitly requires it.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
