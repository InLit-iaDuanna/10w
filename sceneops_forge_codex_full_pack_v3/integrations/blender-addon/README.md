# SceneOps Blender typed adapter and add-on

This package is the only Blender process boundary for the 07 asset pipeline. It
accepts typed, allowlisted commands, validates every project path, launches only
the bundled bridge, maps failures to structured errors, and labels execution as
`live`, `cached`, `mock`, `planned`, or `blocked`.

## Supported operations

Health/capabilities are separate APIs. Commands cover scene scan, stable-ID
assignment, object inspection, transform/normals, bounded material and light
parameters, context capture, allowlisted AOV render, geometry checks,
conservative LOD/collider generation, snapshot/rollback, and GLB/FBX export.
There is deliberately no arbitrary Python or shell command.

`generate_lod` uses Blender's decimate modifier with declared ratios.
`generate_collider` supports only bounding-box and convex-hull strategies. These
are production proposals requiring inspection; the integration makes no claim of
automatic production-quality retopology.

## Live setup

Install or point the service at a supported Blender executable, then construct
`LiveBlenderAdapter(project_root, executable)`. Executable discovery is off by
default, the configured binary must be named Blender and pass `--version`, and
the Python bridge cannot be overridden. Commands run with `--background`,
`--factory-startup`, and `--disable-autoexec` through the fixed
`scripts/typed_bridge.py`; the add-on also disables Freestyle and compositor
nodes after loading an imported scene. All requested source/output paths remain
below the configured root. The bundled direct subprocess transport can run only
source-less live checks such as the smoke scan; it reports
`BLENDER_SANDBOX_REQUIRED` before opening any project `.blend`. Project-file
commands require an injected transport that truthfully advertises filesystem
isolation. Persistent scene mutations also require an existing, server-owned
per-run `operation_state_root` outside project content for locks and retry
journals.

When Blender is unavailable, `health_check()` returns `blocked`. Callers may
explicitly select `DeterministicMockBlenderAdapter`. `CachedBlenderAdapter`
becomes healthy only when trusted storage supplies a successful live-run record
for each workflow-slot/operation key. Run-directory paths are normalized only at
their structural segments; the remaining command, current source checksum, and
verified materialization blobs must match. Each side effect is materialized into
the new run and rechecked for byte size/checksum. The live adapter never auto-
falls back.

## Tests

```text
PYTHONPATH=integrations/blender-addon/src python3 -m unittest discover -s integrations/blender-addon/tests -v
```

The smoke test is not skipped: it asserts `live` when Blender is found and
otherwise asserts a structured `blocked` result.
