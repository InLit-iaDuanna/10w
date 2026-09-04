from __future__ import annotations

from datetime import datetime, timezone

from .contracts import (
    BlenderCommand,
    BlenderOperation,
    CapabilityReport,
    ChangePreview,
    READ_ONLY_OPERATIONS,
)


ADAPTER_VERSION = "0.1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def capabilities() -> CapabilityReport:
    return CapabilityReport(
        adapter_version=ADAPTER_VERSION,
        operations=list(BlenderOperation),
        export_formats=["glb", "fbx"],
        render_passes=["beauty", "depth", "normal", "object_id", "material_id"],
        collider_methods=["bounding_box", "convex_hull"],
    )


def preview(command: BlenderCommand) -> ChangePreview:
    return ChangePreview(
        request_id=command.request_id,
        operation=command.operation,
        source_path=command.source_path,
        output_paths=command.output_paths,
        target_object_ids=command.object_ids,
        parameter_keys=sorted(command.parameters),
        requires_approval=command.operation not in READ_ONLY_OPERATIONS,
    )
