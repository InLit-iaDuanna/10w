# 06 — Concept Lab and Style Bible

## Recommended agent / model

Use `module_builder` with Terra/high or `render_ops_builder` for image-generation integration.

## Objective

Create a concept-production and review module that converts project style and feature needs into approved, traceable asset briefs.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/concept-lab/**
- concept-specific adapters only if assigned
- concept editors/tests/docs

Do not own the final 3D asset publishing pipeline.

## Tasks

1. Build Moodboard and Style Bible editors linked to Project Bible.
2. Define ConceptSpec with subject, gameplay function, proportions, dimensions, materials, required views, platform budget, style constraints, forbidden elements, and references.
3. Support imported references and generated variants with source/license/provenance.
4. Generate multi-view or turn-around requests when supported.
5. Compare variants, comment, reject, approve, and record decisions.
6. Add style-consistency checks that return evidence and confidence, not absolute artistic truth.
7. Compile an approved concept into an AssetSpec draft for asset-factory.
8. Provide cached/mock generation fixtures and a clear live integration boundary.
9. Build the key concept flow for the hero feature.
10. Ensure concepts can be opened from chat and task links.

## Acceptance criteria

- A concept can move from request to approved version and AssetSpec draft.
- References and AI outputs carry provenance and permission status.
- Rejected options remain traceable.
- Style checks are explainable and reviewable.
- The module works without image generation by importing a concept.

## Required tests

- concept create/edit/version
- imported reference provenance
- live/mock/cached generation states
- compare/approve/reject
- style-check evidence
- AssetSpec compilation
- missing model/integration behavior
- license-status warning

## Do not

- Do not treat image generation as final asset production.
- Do not claim subjective style scores are facts.
- Do not lose prompts/seeds/workflow versions.
- Do not copy asset-factory responsibilities.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
