# SceneOps Forge — Cross-Module Integration Review

Review the integration between:

- producer module(s): `<modules>`
- consumer module(s): `<modules>`
- contracts/events: `<list>`
- adapters/tools: `<list>`
- target flow: `<flow>`

Do not edit code initially.

Trace one real request from UI/assistant command through API, jobs, adapter, artifacts/events, downstream consumers, and user-visible result. Verify:

- stable IDs and correlation IDs;
- contract ownership and versioning;
- retry/idempotency/cancellation;
- approval pauses;
- provenance;
- failure and recovery;
- Live/Mock/Cached labels;
- no internal cross-module imports;
- documentation accuracy;
- tests that exercise the real path.

Return concrete findings. After principal assigns ownership, implement only the approved bounded fixes and rerun the flow.
