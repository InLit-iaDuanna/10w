# Render Ops events

Render Ops event payload schemas are stored in `contracts/events/`. The core
event envelope supplies event ID/type/version, UTC occurrence time, project,
correlation/causation IDs, actor, and execution mode. These module schemas define
payloads only and do not replace or alter that shared envelope.

| Event | Producer | Intended consumers |
|---|---|---|
| `render.job.started@1` | render queue worker | queue editor, observability |
| `render.job.progressed@1` | capture/Comfy worker | queue editor, observability |
| `render.job.failed@1` | render orchestrator | queue editor, integration center |
| `render.job.cancelled@1` | render orchestrator | queue editor, observability |
| `render.variant.created@1` | variant worker | Render Viewer, provenance editor |
| `render.writeback.proposed@1` | Render Ops service | ChangeSet/approval module |
| `render.validation.completed@1` | validation worker | comparison editor, release gates |

Consumers must be idempotent by core event ID. `render.variant.created@1` carries
the workflow checksum, model reference, seed, output artifact, and truthful mode;
full prompt and negative prompt remain in the immutable RenderManifest to avoid
putting potentially sensitive creative text on a broad event stream.
