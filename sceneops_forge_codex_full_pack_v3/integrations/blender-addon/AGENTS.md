# Blender Adapter Rules

## Ownership

This integration owns the typed Blender process boundary, bundled add-on/bridge,
path enforcement, stable Blender object properties, export inspection, and
deterministic adapter doubles. It does not own asset publication policy.

## Security invariants

- Only `BlenderOperation` values and their per-operation parameter keys run.
- There is no execute-Python, expression, shell, or user-script operation.
- User-provided project paths resolve inside one configured project root.
- Subprocesses use argument arrays with `shell=False` and a bundled bridge only.
- Mutating commands require a ChangeSet and approval ID; dry-run never launches
  Blender.
- Source `.blend` files are not overwritten. Mutation starts from a snapshot.

## Tests

```text
PYTHONPATH=integrations/blender-addon/src python3 -m unittest discover -s integrations/blender-addon/tests -v
```

A Blender smoke test must execute in either `live` or truthful `blocked` mode; it
must never silently substitute a mock.
