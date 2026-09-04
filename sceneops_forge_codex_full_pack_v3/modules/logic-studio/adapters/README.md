# Unity code-generation adapter boundary

Logic Studio owns the typed orchestration contract implemented in
`backend/src/logic_studio/unity_adapter.py`. The concrete Unity integration must
implement health/capability reporting, dry-run, allowlisted apply, compile plus
Edit/Play Mode tests, cancellation, progress, timeout/retry policy, and rollback.

The included adapter is deterministic `mock` only. It records in-memory receipts
and never reads, writes, compiles, or executes C#. A live implementation belongs
behind the `engine-unity` safety boundary and is currently `blocked` because that
module is absent from this baseline.
