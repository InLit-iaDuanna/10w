# ComfyUI Adapter Rules

This integration owns only the typed ComfyUI HTTP boundary. It must not accept
arbitrary workflow JSON, workflow file paths, output paths, or executable code
from a render command. Workflows and bindings are trusted configuration;
commands select them by reference and SHA-256 checksum.

Keep health, capabilities, timeout, cancellation, retry, idempotency, progress,
output retrieval, error mapping, deterministic mock behavior, and provenance
covered by independent tests. Network tests must use an injected transport and
must never label deterministic fixtures as live.
