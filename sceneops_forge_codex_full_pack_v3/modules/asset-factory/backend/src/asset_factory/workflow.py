from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sceneops_blender import (
    BlenderCommand,
    BlenderOperation,
    MutationAuthorization,
)

from .schemas import ChangeSetState, PipelineRequest, ProcessingStepKind


@dataclass(frozen=True)
class StepPlan:
    kind: ProcessingStepKind
    commands: List[BlenderCommand]
    skip_reason: Optional[str] = None


def build_workflow_plan(request: PipelineRequest, *, preview: bool) -> List[StepPlan]:
    source = request.source.project_relative_path
    object_ids = [item.sceneops_id for item in request.source_object_identities]
    authorization = _authorization(request, preview)
    output = request.output_directory
    internal_run_directory = ".sceneops/asset-factory/%s" % request.pipeline_run_id
    working_source = internal_run_directory + "/working.blend"
    processing_source = source if preview else working_source
    command_index = 0

    def command(
        operation: BlenderOperation,
        *,
        outputs: Optional[List[str]] = None,
        parameters: Optional[dict] = None,
        targets: Optional[List[str]] = None,
        input_path: Optional[str] = None,
    ) -> BlenderCommand:
        nonlocal command_index
        command_index += 1
        return BlenderCommand(
            request_id="%s:%02d:%s" % (request.pipeline_run_id, command_index, operation.value),
            project_id=request.spec.project_id,
            operation=operation,
            source_path=input_path or source,
            output_paths=outputs or [],
            object_ids=targets or [],
            parameters=parameters or {},
            authorization=authorization,
            dry_run=preview,
        )

    geometry_parameters = {
        "triangle_budget": request.spec.triangle_budget,
        "require_uv": request.spec.requires_uv,
        "allow_nonmanifold": False,
    }
    plans = [
        StepPlan(
            ProcessingStepKind.PREFLIGHT,
            [
                command(BlenderOperation.SCAN_SCENE),
                command(
                    BlenderOperation.CHECK_GEOMETRY,
                    parameters=geometry_parameters,
                    targets=object_ids,
                ),
            ],
        ),
        StepPlan(
            ProcessingStepKind.SNAPSHOT,
            [
                command(
                    BlenderOperation.SAVE_SNAPSHOT,
                    outputs=[
                        internal_run_directory + "/rollback.blend",
                        working_source,
                    ],
                )
            ],
        ),
        StepPlan(
            ProcessingStepKind.CLEAN,
            [
                command(
                    BlenderOperation.ASSIGN_STABLE_IDS,
                    parameters={
                        "identity_assignments": {
                            item.display_name: item.sceneops_id
                            for item in request.source_object_identities
                        }
                    },
                    targets=object_ids,
                    input_path=processing_source,
                ),
                command(
                    BlenderOperation.SET_NORMALS,
                    parameters={"mode": "recalculate_outside"},
                    targets=object_ids,
                    input_path=processing_source,
                ),
            ],
        ),
        StepPlan(
            ProcessingStepKind.UV_MATERIAL_CHECK,
            [
                command(
                    BlenderOperation.INSPECT_OBJECT,
                    parameters={"include_materials": True},
                    targets=object_ids,
                    input_path=processing_source,
                )
            ],
        ),
        StepPlan(
            ProcessingStepKind.LOD,
            [
                command(
                    BlenderOperation.GENERATE_LOD,
                    parameters={"ratios": [0.5, 0.25]},
                    targets=object_ids,
                    input_path=processing_source,
                )
            ]
            if request.spec.requires_lods
            else [],
            None if request.spec.requires_lods else "AssetSpec does not require LOD generation.",
        ),
        StepPlan(
            ProcessingStepKind.COLLIDER,
            [
                command(
                    BlenderOperation.GENERATE_COLLIDER,
                    parameters={"method": "convex_hull"},
                    targets=object_ids,
                    input_path=processing_source,
                )
            ]
            if request.spec.requires_collider
            else [],
            None if request.spec.requires_collider else "AssetSpec does not require a collider.",
        ),
        StepPlan(
            ProcessingStepKind.TURNTABLE_AOV,
            [
                command(
                    BlenderOperation.RENDER_AOV,
                    outputs=["%s/review/%s-turntable.exr" % (output, request.pipeline_run_id)],
                    parameters={
                        "passes": ["beauty", "depth", "normal", "object_id", "material_id"],
                        "width": 512,
                        "height": 512,
                        "samples": 32,
                    },
                    targets=object_ids,
                    input_path=processing_source,
                )
            ],
        ),
        StepPlan(
            ProcessingStepKind.VALIDATE,
            [
                command(
                    BlenderOperation.CHECK_GEOMETRY,
                    parameters=geometry_parameters,
                    targets=object_ids,
                    input_path=processing_source,
                )
            ],
        ),
        StepPlan(
            ProcessingStepKind.EXPORT,
            [
                command(
                    BlenderOperation.EXPORT_ASSET,
                    outputs=[
                        internal_run_directory + "/exports/asset.glb",
                        internal_run_directory + "/exports/asset.fbx",
                    ],
                    parameters={
                        "formats": ["glb", "fbx"],
                        "include_extras": True,
                        "selection_only": True,
                    },
                    targets=object_ids,
                    input_path=processing_source,
                )
            ],
        ),
        StepPlan(ProcessingStepKind.PUBLISH, []),
    ]
    return plans


def _authorization(
    request: PipelineRequest, preview: bool
) -> Optional[MutationAuthorization]:
    if preview:
        return None
    change_set = request.change_set
    if change_set.state != ChangeSetState.APPROVED or not change_set.approval_id:
        return None
    return MutationAuthorization(
        change_set_id=change_set.change_set_id,
        approval_id=change_set.approval_id,
    )
