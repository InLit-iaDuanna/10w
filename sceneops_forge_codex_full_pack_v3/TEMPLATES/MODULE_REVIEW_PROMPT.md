# SceneOps Forge — Read-Only Module Review

Review module `<module-id>` as an owner. Do not edit code.

Read root guidance, module manifest/README/AGENTS, public contracts, implementation, tests, and docs.

Find concrete issues in:

1. module ownership and undeclared dependencies;
2. public API stability;
3. editor/command/event/job registration;
4. success and failure behavior;
5. permission and integration-offline behavior;
6. Live/Mock/Cached truthfulness;
7. state transitions and idempotency;
8. security and path/command boundaries;
9. test coverage and flaky behavior;
10. documentation drift;
11. unnecessary abstractions or duplicated logic;
12. performance and resource cleanup.

Return findings first, ordered by severity, with file/symbol references and reproduction steps. Then list test gaps and a concise remediation order. Do not include style-only comments unless they hide a real defect.
