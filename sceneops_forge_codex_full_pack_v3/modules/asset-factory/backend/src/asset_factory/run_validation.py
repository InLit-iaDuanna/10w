from __future__ import annotations

from typing import List

from asset_library import AssetLibraryService, AssetNotFoundError

from .schemas import PipelineRequest, PipelineRun


def catalog_input_errors(
    catalog: AssetLibraryService, request: PipelineRequest
) -> List[str]:
    try:
        record = catalog.get(request.spec.asset_id)
    except AssetNotFoundError:
        return ["asset is not registered in the trusted catalog"]
    reasons = []
    if record.spec != request.spec:
        reasons.append("AssetSpec does not match the trusted catalog")
    if record.source != request.source:
        reasons.append("SourceAsset does not match the trusted catalog")
    catalog_objects = sorted(record.source_objects, key=lambda item: item.sceneops_id)
    request_objects = sorted(
        request.source_object_identities, key=lambda item: item.sceneops_id
    )
    if catalog_objects != request_objects:
        reasons.append("source object identities do not match the trusted catalog")
    return reasons


def retry_matches_run(previous: PipelineRun, request: PipelineRequest) -> bool:
    return (
        request.spec.project_id,
        request.spec.asset_id,
        request.asset_version_id,
        request.change_set.change_set_id,
    ) == (
        previous.project_id,
        previous.asset_id,
        previous.asset_version_id,
        previous.change_set_id,
    )


def rollback_matches_run(run: PipelineRun, request: PipelineRequest) -> bool:
    return (
        request.pipeline_run_id,
        request.spec.project_id,
        request.spec.asset_id,
        request.asset_version_id,
        request.change_set.change_set_id,
    ) == (
        run.pipeline_run_id,
        run.project_id,
        run.asset_id,
        run.asset_version_id,
        run.change_set_id,
    )
