# UI Studio ownership

Only this folder is owned by UI Studio. Its public backend surface is `backend/src/ui_studio/__init__.py`; its public frontend surface is `frontend/src/index.ts`.

- Unity communication uses only `UnityUiAdapter` in `contracts.py`; never import an engine-unity internal path.
- All generated or AI-assisted UI mapping is a `ChangeSet` and remains `proposed` until explicitly approved and published.
- Fixtures are deterministic `mock` data and must never be labelled live.
- Run `PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v` before handoff.
