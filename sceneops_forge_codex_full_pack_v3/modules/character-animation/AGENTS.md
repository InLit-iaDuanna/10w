# Character and Animation Module Rules

## Ownership

This directory owns character specifications, rig and skin versions, animation clips,
retarget profiles, animator-state specifications, preview evidence, quality checks,
version review, and the typed Unity character-mapping proposal.

Do not store source assets here or import internals from Asset Library, Design Room,
Production Planner, Blender, or Unity modules. Reference their public entities by
stable ID and use the adapter protocols in `adapters/` for external operations.

## Invariants

- Source asset, character, rig, skin, clip, preview, Unity Prefab, and scene object IDs stay distinct.
- Meters, coordinate space, up axis, and forward axis are explicit.
- Heuristic checks never imply human-quality approval.
- External writes require a dry-run `ChangeSet` and explicit approval.
- Imported rigs and clips remain usable when generation or retargeting is offline.
- Preview comparisons use the same fixed camera.
- Every result carries `live`, `cached`, `mock`, `planned`, or `blocked` mode.

## Generated files

- `contracts/manifests/character-animation.schema.json`
- `contracts/events/*.schema.json`
- `backend/openapi.json`
- `frontend/src/generated/api.ts`
- `contracts/examples/remember-home-character.json`
- `contracts/examples/preview-artifact.json`
- `contracts/examples/unity-mapping-proposal.json`

Regenerate them with the commands documented in `README.md`; do not hand-edit them.

## Acceptance commands

```bash
cd modules/character-animation/backend
PYTHONPATH=src python3 -m unittest discover -s tests -v

cd ../frontend
npm run check
```
