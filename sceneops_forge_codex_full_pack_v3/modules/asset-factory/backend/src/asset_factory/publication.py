from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from asset_library import (
    ArtifactOutput,
    ArtifactProvenance,
    AssetLibraryService,
    AssetObjectIdentity,
    AssetVersion,
    ExecutionMode,
    GeometryMetrics,
    PublicationRequest,
    PublicationStatus,
    QualityGate,
    Vector3Meters,
)
from sceneops_blender import ProjectPathPolicy, artifact_sha256

from .schemas import PipelineRequest
from .finalization import FinalizedCandidateStore


def build_and_publish_version(
    request: PipelineRequest,
    catalog: AssetLibraryService,
    export_data: Dict[str, object],
    metrics_data: Dict[str, object],
    gates: List[QualityGate],
    execution_mode: ExecutionMode,
    tool_version: str,
    now: datetime,
    project_root: Path,
    candidate_store: FinalizedCandidateStore,
) -> Tuple[AssetVersion, AssetVersion]:
    created_paths: List[Path] = []
    finalized_candidate: Optional[AssetVersion] = None
    try:
        engine_outputs = _promote_engine_outputs(
            request, export_data, project_root, created_paths
        )
        object_identities = _exported_identities(request, export_data)
        manifest_output = _write_export_manifest(
            request,
            object_identities,
            engine_outputs,
            execution_mode,
            now,
            project_root,
            created_paths,
        )
        outputs = [*engine_outputs, manifest_output]
        candidate = _candidate_version(
            request,
            outputs,
            object_identities,
            metrics_data,
            gates,
            execution_mode,
            tool_version,
            now,
        )
        candidate_store.finalize(request.change_set.change_set_id, candidate)
        finalized_candidate = candidate
        published = catalog.publish(
            PublicationRequest(
                asset_id=request.spec.asset_id,
                asset_version_id=candidate.asset_version_id,
                change_set_id=request.change_set.change_set_id,
                approval_id=request.change_set.approval_id or "",
                approved_by=request.change_set.approved_by or "",
            )
        )
        return candidate, published
    except Exception as publication_error:
        discard_error: Optional[Exception] = None
        if finalized_candidate is not None:
            try:
                candidate_store.discard(
                    request.change_set.change_set_id, finalized_candidate
                )
            except Exception as error:
                discard_error = error
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        if discard_error is not None:
            raise RuntimeError(
                "finalized candidate compensation failed"
            ) from publication_error
        raise


def _candidate_version(
    request: PipelineRequest,
    outputs: List[ArtifactOutput],
    object_identities: List[AssetObjectIdentity],
    metrics_data: Dict[str, object],
    gates: List[QualityGate],
    execution_mode: ExecutionMode,
    tool_version: str,
    now: datetime,
) -> AssetVersion:
    provenance = [
        ArtifactProvenance(
            artifact_id=artifact.artifact_id,
            source_project=request.spec.project_id,
            source_version=request.source.source_version,
            source_commit=request.source.source_commit,
            related_sceneops_ids=[
                item.sceneops_id for item in object_identities
            ],
            producing_module="asset-factory",
            tool_name="Blender" if artifact.format in {"glb", "fbx"} else "SceneOps Forge",
            tool_version=tool_version,
            adapter_version="0.1.0",
            recipe_version="asset-to-engine-ready@1",
            creator=request.creator,
            execution_mode=execution_mode,
            timestamp=now,
            sha256=artifact.sha256,
            approval_state="approved",
        )
        for artifact in outputs
    ]
    return AssetVersion(
        asset_version_id=request.asset_version_id,
        asset_id=request.spec.asset_id,
        source_asset_id=request.source.source_asset_id,
        version=request.asset_version_number,
        status=PublicationStatus.APPROVED,
        execution_mode=execution_mode,
        metrics=_geometry_metrics(metrics_data),
        object_identities=object_identities,
        outputs=outputs,
        quality_gates=gates,
        provenance=provenance,
        approval_id=request.change_set.approval_id,
        created_at=now,
    )


def _promote_engine_outputs(
    request: PipelineRequest,
    export_data: Dict[str, object],
    project_root: Path,
    created_paths: List[Path],
) -> List[ArtifactOutput]:
    staged = [_artifact_output(item) for item in export_data.get("artifacts", [])]
    _validate_engine_formats(staged)
    policy = ProjectPathPolicy(project_root)
    outputs: List[ArtifactOutput] = []
    for artifact in sorted(staged, key=lambda item: item.format):
        source = policy.resolve(artifact.project_relative_path, must_exist=True)
        if source.stat().st_size != artifact.byte_size or artifact_sha256(source) != artifact.sha256:
            raise ValueError("staged artifact integrity does not match: " + artifact.artifact_id)
        relative_path = "%s/v%d/asset.%s" % (
            request.output_directory,
            request.asset_version_number,
            artifact.format,
        )
        destination = policy.resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_stream = destination.open("xb")
        except FileExistsError as error:
            raise ValueError("published asset version path already exists") from error
        created_paths.append(destination)
        with source.open("rb") as input_stream, output_stream:
            shutil.copyfileobj(input_stream, output_stream)
        outputs.append(
            artifact.model_copy(
                update={
                    "artifact_id": "art_%s_%s"
                    % (request.asset_version_id, artifact.format),
                    "project_relative_path": relative_path,
                },
                deep=True,
            )
        )
    return outputs


def _artifact_output(raw: object) -> ArtifactOutput:
    if not isinstance(raw, dict):
        raise ValueError("Blender artifact entry must be an object")
    return ArtifactOutput(
        artifact_id=raw["artifact_id"],
        artifact_type="engine_asset",
        format=raw["format"],
        project_relative_path=raw["project_relative_path"],
        media_type=raw["media_type"],
        byte_size=raw["byte_size"],
        sha256=raw["sha256"],
    )


def _validate_engine_formats(outputs: List[ArtifactOutput]) -> None:
    formats = {item.format for item in outputs}
    if len(outputs) != 2 or formats != {"glb", "fbx"}:
        raise ValueError("Blender export must produce exactly one GLB and one FBX")


def _write_export_manifest(
    request: PipelineRequest,
    object_identities: List[AssetObjectIdentity],
    outputs: List[ArtifactOutput],
    execution_mode: ExecutionMode,
    now: datetime,
    project_root: Path,
    created_paths: List[Path],
) -> ArtifactOutput:
    policy = ProjectPathPolicy(project_root)
    relative_path = "%s/v%d/manifest.json" % (
        request.output_directory,
        request.asset_version_number,
    )
    path = policy.resolve(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "asset_id": request.spec.asset_id,
        "source_asset_id": request.source.source_asset_id,
        "asset_version_id": request.asset_version_id,
        "object_identities": [item.model_dump(mode="json") for item in object_identities],
        "artifacts": [item.model_dump(mode="json") for item in outputs],
        "execution_mode": execution_mode.value,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
    }
    try:
        stream = path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError("published asset manifest already exists") from error
    created_paths.append(path)
    with stream:
        stream.write(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
    return ArtifactOutput(
        artifact_id="art_%s_manifest" % request.asset_version_id,
        artifact_type="asset_manifest",
        format="json",
        project_relative_path=relative_path,
        media_type="application/json",
        byte_size=path.stat().st_size,
        sha256=artifact_sha256(path),
    )


def _exported_identities(
    request: PipelineRequest, export_data: Dict[str, object]
) -> List[AssetObjectIdentity]:
    identities = {item.sceneops_id: item for item in request.source_object_identities}
    for raw in export_data.get("object_identities", []):
        if not isinstance(raw, dict):
            raise ValueError("export object identity must be an object")
        sceneops_id = raw["sceneops_id"]
        identities.setdefault(
            sceneops_id,
            AssetObjectIdentity(
                sceneops_id=sceneops_id,
                source_asset_id=request.source.source_asset_id,
                display_name=raw["display_name"],
                source_object_locator=raw["source_object_locator"],
                parent_sceneops_id=raw.get("parent_sceneops_id"),
            ),
        )
    exported_ids = set(export_data.get("sceneops_ids", []))
    if exported_ids != set(identities):
        raise ValueError("export identity manifest does not match AssetVersion identities")
    return [identities[key] for key in sorted(identities)]


def _geometry_metrics(raw: Dict[str, object]) -> GeometryMetrics:
    dimensions = raw.get("dimensions_m") or {}
    if not isinstance(dimensions, dict):
        raise ValueError("geometry dimensions must be an object")
    return GeometryMetrics(
        dimensions_m=Vector3Meters(
            x=dimensions.get("x", 0),
            y=dimensions.get("y", 0),
            z=dimensions.get("z", 0),
        ),
        triangle_count=raw.get("triangle_count", 0),
        vertex_count=raw.get("vertex_count", 0),
        material_count=raw.get("material_count", 0),
        texture_count=raw.get("texture_count", 0),
        has_uv=raw.get("has_uv", False),
        is_rigged=raw.get("is_rigged", False),
        animation_names=raw.get("animation_names", []),
        lod_count=raw.get("lod_count", 0),
        collider_kind=raw.get("collider_kind"),
    )
