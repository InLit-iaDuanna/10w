# module-runtime module rules

- Own manifest schema, discovery, dependency validation, static catalogs, scaffold tooling, and import-boundary checks only.
- Registration is build-time and explicit; do not add an unrestricted runtime plugin loader.
- Pydantic `ModuleManifest` is the source for the generated JSON Schema.
- Public frontend imports go through `frontend/src/index.ts`; public backend imports go through `module_runtime/__init__.py`.
- Generated files are listed in this module README and must pass `scripts/module-generate --check`.
- Run `scripts/module-test module-runtime` and `scripts/module-validate` before handoff.
