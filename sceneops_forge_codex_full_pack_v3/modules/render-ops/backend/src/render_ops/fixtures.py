"""Deterministic module fixture used by tests and offline UI examples."""

from datetime import datetime, timezone
from typing import List

from .schemas import (
    AovArtifact,
    AovDependencySnapshot,
    AovPass,
    ApprovalState,
    ArtifactApprovalState,
    ArtifactRef,
    CachePlan,
    DifferenceMetrics,
    ExecutionMode,
    ProtectedRegion,
    ProtectedRegionResult,
    RecipeKind,
    RenderBrief,
    RenderComparison,
    RenderJob,
    RenderJobState,
    RenderManifest,
    RenderRecipe,
    RenderVariant,
    SceneCameraRef,
    ValidationResult,
    WorkflowProvenance,
    WritebackOperation,
    WritebackProperty,
    WritebackProposal,
    WritebackTarget,
)


FIXTURE_TIME = datetime(2026, 9, 4, 1, 2, 3, tzinfo=timezone.utc)
WORKFLOW_CHECKSUM = "a" * 64
MODEL_CHECKSUM = "b" * 64
ARTIFACT_CHECKSUM = "c" * 64


def mock_scene() -> SceneCameraRef:
    return SceneCameraRef(
        project_id="prj_remember_home",
        scene_id="scn_home_hall",
        scene_version="scene-v17",
        camera_id="cam_front_door",
        camera_version="camera-v4",
        scene_object_ids=["sceneops_light_porch", "sceneops_door_home"],
        coordinate_space="world",
        axis_convention="right-handed, Y-up, -Z-forward",
        distance_unit="meter",
    )


def mock_artifact(
    artifact_id: str,
    artifact_type: str,
    approval_state: ArtifactApprovalState = ArtifactApprovalState.NOT_REQUIRED,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        uri="fixture://render-ops/" + artifact_id,
        checksum_sha256=ARTIFACT_CHECKSUM,
        source_project_id="prj_remember_home",
        source_version="scene-v17",
        source_commit="commit-fixture-not-live",
        related_sceneops_ids=["sceneops_light_porch", "sceneops_door_home"],
        producing_module="render-ops",
        tool_name="deterministic-fixture-renderer",
        tool_version="1.0.0",
        creator="fixture_worker",
        approval_state=approval_state,
        execution_mode=ExecutionMode.MOCK,
        created_at=FIXTURE_TIME,
    )


def mock_recipe() -> RenderRecipe:
    return RenderRecipe(
        recipe_id="render.lighting-visibility",
        version="1.0.0",
        kind=RecipeKind.LIGHTING_VISIBILITY,
        required_passes=[
            AovPass.BEAUTY,
            AovPass.DEPTH,
            AovPass.NORMAL,
            AovPass.ALBEDO,
            AovPass.OBJECT_ID,
        ],
        optional_passes=[AovPass.MATERIAL_ID],
        workflow_reference="lookdev.lighting-visibility.v1",
        workflow_checksum_sha256=WORKFLOW_CHECKSUM,
        parameters={"target_visibility": "clear", "resolution": [4, 4]},
    )


def mock_dependency_snapshot(**changes) -> AovDependencySnapshot:
    payload = {
        "recipe_id": "render.lighting-visibility",
        "recipe_version": "1.0.0",
        "geometry_version": "geometry-v8",
        "camera_version": "camera-v4",
        "material_version": "material-v3",
        "lighting_version": "lighting-v5",
        "visibility_version": "visibility-v2",
        "renderer_version": "fixture-renderer-1.0.0",
        "samples": 64,
        "width": 4,
        "height": 4,
    }
    payload.update(changes)
    return AovDependencySnapshot.model_validate(payload)


def mock_aovs() -> List[AovArtifact]:
    scene = mock_scene()
    return [
        AovArtifact(
            pass_type=pass_type,
            scene=scene,
            width=4,
            height=4,
            artifact=mock_artifact("aov_" + pass_type.value, "render.aov." + pass_type.value),
        )
        for pass_type in mock_recipe().required_passes
    ]


def mock_manifest() -> RenderManifest:
    scene = mock_scene()
    brief = RenderBrief(
        brief_id="rbrief_porch_visibility",
        scene=scene,
        intent="让门廊钥匙区域更清晰，同时保护门体轮廓。",
        target_object_ids=["sceneops_light_porch"],
        protected_regions=[
            ProtectedRegion(
                region_id="region_home_door",
                object_ids=["sceneops_door_home"],
                mask_artifact_id="aov_object_id",
                max_changed_ratio=0.0,
            )
        ],
        requested_by="usr_fixture_reviewer",
        created_at=FIXTURE_TIME,
    )
    recipe = mock_recipe()
    job = RenderJob(
        job_id="rjob_fixture_001",
        brief_id=brief.brief_id,
        recipe_id=recipe.recipe_id,
        recipe_version=recipe.version,
        scene=scene,
        dependency_snapshot=mock_dependency_snapshot(),
        cache_plan=CachePlan(
            capture_passes=recipe.required_passes,
            reasons={item: "deterministic fixture capture" for item in recipe.required_passes},
        ),
        state=RenderJobState.SUCCEEDED,
        execution_mode=ExecutionMode.MOCK,
        progress=1.0,
        created_at=FIXTURE_TIME,
        updated_at=FIXTURE_TIME,
    )
    provenance = WorkflowProvenance(
        provider="deterministic-fixture",
        workflow_reference=recipe.workflow_reference,
        workflow_checksum_sha256=recipe.workflow_checksum_sha256,
        model_reference="fixture/lookdev-model-v1",
        model_checksum_sha256=MODEL_CHECKSUM,
        seed=74012,
        prompt="warm porch light revealing the target, preserve door silhouette",
        negative_prompt="geometry change, camera move, door silhouette change",
        parameters={"steps": 1, "guidance": 1.0},
        adapter_version="0.1.0",
    )
    pending_variant = RenderVariant(
        variant_id="rvariant_fixture_001",
        job_id=job.job_id,
        scene=scene,
        output=mock_artifact(
            "render_variant_fixture_001",
            "render.variant",
            ArtifactApprovalState.PENDING,
        ),
        constraint_passes=[AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID],
        provenance=provenance,
        approval_state=ApprovalState.PENDING,
    )
    from .service import RenderOpsService

    variant = RenderOpsService().approve_variant(
        pending_variant,
        approved_by="usr_fixture_reviewer",
        approved_at=FIXTURE_TIME,
    )
    comparison = RenderComparison(
        comparison_id="rcompare_fixture_001",
        before_artifact_id="aov_beauty",
        after_artifact_id="validation_beauty_fixture_001",
        scene=scene,
        metrics=DifferenceMetrics(
            mean_absolute_difference=0.02,
            changed_pixel_ratio=0.25,
            maximum_channel_difference=0.12,
            artistic_quality_measured=False,
        ),
        protected_regions=[
            ProtectedRegionResult(
                region_id="region_home_door",
                changed_pixel_ratio=0.0,
                threshold=0.0,
                passed=True,
            )
        ],
        changed_object_ids=["sceneops_light_porch"],
        execution_mode=ExecutionMode.MOCK,
    )
    pending_proposal = WritebackProposal(
        proposal_id="rwriteback_fixture_001",
        variant_id=variant.variant_id,
        brief_id=brief.brief_id,
        scene=scene,
        base_scene_version=scene.scene_version,
        operations=[
            WritebackOperation(
                target=WritebackTarget.BLENDER,
                target_object_id="sceneops_light_porch",
                property=WritebackProperty.LIGHT_INTENSITY,
                previous_value=600.0,
                proposed_value=850.0,
            )
        ],
        rationale="Approved variant reveals the target with a bounded light edit.",
        expected_result="The key target is more visible from the fixed camera.",
        impact_scope=["sceneops_light_porch"],
        allowed_object_ids=brief.target_object_ids,
        risk="low",
        validation_plan="Re-render the fixed camera and validate protected regions.",
        rollback_plan="Restore light intensity to 600.0.",
        approval_requirements=["render:approve", "render:writeback"],
        approval_state=ApprovalState.PENDING,
    )
    from .writeback import approve_writeback

    proposal = approve_writeback(
        pending_proposal,
        changeset_id="changeset_fixture_001",
        approved_by="usr_fixture_reviewer",
        approved_at=FIXTURE_TIME,
    )
    validation = ValidationResult(
        validation_id="rvalidation_fixture_001",
        proposal_id=proposal.proposal_id,
        comparison_id=comparison.comparison_id,
        deterministic_recipe_id="render.fixed-camera-regression",
        changed_object_ids=["sceneops_light_porch"],
        allowed_object_ids=["sceneops_light_porch"],
        geometry_unchanged=True,
        camera_unchanged=True,
        protected_regions_passed=True,
        scope_passed=True,
        passed=True,
        failures=[],
        execution_mode=ExecutionMode.MOCK,
        completed_at=FIXTURE_TIME,
    )
    return RenderManifest(
        schema_version=1,
        manifest_id="rmanifest_fixture_001",
        brief=brief,
        recipe=recipe,
        job=job,
        aovs=mock_aovs(),
        variants=[variant],
        comparisons=[comparison],
        writeback_proposals=[proposal],
        validations=[validation],
        created_at=FIXTURE_TIME,
    )
