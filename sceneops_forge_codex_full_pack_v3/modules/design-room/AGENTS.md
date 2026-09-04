# Design Room module rules

## Ownership

- This module owns Project Bible, structured GDD, Feature Spec, design decisions, document versions/diffs, and planning-ready events.
- It may consume only the public `project-intake/frontend/src/index.ts` API.
- It does not create production tasks, edit project files, or call asset/Unity/Blender internals.

## Invariants

- GDD and Feature Specs remain structured data, never a single markdown blob.
- Assistant-created content is a draft with explicit unconfirmed assumptions.
- AI edits to an existing document create a typed `DesignChangeSet`; applying it requires approval and an unchanged base version.
- A Feature Spec cannot emit its planning-ready event until intake and actionable-spec validations pass.
- Version snapshots are immutable and structural diffs are deterministic.

## Verification

Run `npm test` from `frontend/`. Required coverage includes Feature Spec version/diff, decision accept/reject, conversation-to-draft, ChangeSet approval, access states, and module disablement.
