# Unity smoke project template

This is source-only test data for the `engine-unity` module. `run_unity_smoke.py` copies it to a temporary directory, embeds the canonical `integrations/unity-package` package, and lets Unity generate caches and build artifacts outside Git.

The fixture generates three playable standalone scenes:

- Remember Home A: the initial key/door branch;
- Remember Home B: the approved visibility adjustment;
- Warehouse Escape: a switch/door/exit reuse case.

Nothing in this directory is evidence of a live build until the smoke runner reports `mode: live` and records Unity's process result.
