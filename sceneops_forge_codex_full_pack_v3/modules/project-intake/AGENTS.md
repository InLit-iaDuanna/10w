# Project Intake module rules

## Ownership

- This module owns new-project intake, existing-project scan normalization, field confirmation, intake readiness, and the `project.intake` editor contribution.
- External project scanners are consumed only through `ProjectScanAdapter`; vendor SDK values must be normalized before entering this module.
- This module records production intent. It never reads or writes a Unity, Blender, or project file directly.

## Invariants

- `targetPlatforms` and `projectRoots` must be explicitly confirmed before an intake is ready.
- Values derived by conversation or scan remain `inferred` until a user confirmation command runs.
- Execution mode is always carried through adapter results and visible editor states.
- Other modules may import only `frontend/src/index.ts`.

## Verification

Run `npm test` from `frontend/`. The suite covers manifest parity, new and existing project flows, missing critical fields, field confirmation, access/offline states, and module disablement.
