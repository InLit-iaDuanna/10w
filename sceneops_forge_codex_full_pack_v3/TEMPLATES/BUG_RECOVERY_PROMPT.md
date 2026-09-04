# SceneOps Forge — Bug Reproduction and Recovery

A failure exists in `<flow/module>`.

## Evidence

- expected behavior:
- actual behavior:
- exact reproduction:
- failing command/test:
- logs/artifacts:
- first known bad commit:
- execution mode:

## Instructions

1. Reproduce before editing.
2. Spawn a read-only code mapper if the path crosses more than one module.
3. Identify the owning module and invariant that failed.
4. Make the smallest defensible fix in owned files.
5. Add a regression test that fails before and passes after.
6. Verify no public contract or module boundary was bypassed.
7. Run relevant module and flow tests.
8. Update troubleshooting/status if user-facing.

Do not hide the failure with retries, catch-all error handling, fake data, disabled assertions, or broader timeouts without evidence.
