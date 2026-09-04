"""Deterministic Remember Home character fixture used by backend and contract tests."""

from datetime import datetime, timezone
from typing import List

from .animation_models import (
    AnimationClipSpec,
    AnimationEventMarker,
    AnimatorStateSpec,
    AnimatorTransitionSpec,
    FixedPreviewCamera,
    FootPlantSample,
    LoopPose,
    RetargetBoneMapping,
    RetargetProfile,
    RootMotionSample,
)
from .character_models import (
    BoneSpec,
    CharacterSpec,
    RigVersion,
    SkinInfluence,
    SkinVersion,
    VertexWeights,
)
from .common import ApprovalRecord, ApprovalState, CoordinateSystem, ExecutionMode, FeatureLink, Provenance
from .operation_models import CharacterBundle


FIXTURE_TIME = datetime(2026, 9, 4, tzinfo=timezone.utc)
CHECKSUM = "a" * 64
COORDINATES = CoordinateSystem(
    space="character_local",
    handedness="right",
    up_axis="Y",
    forward_axis="Z",
    meters_per_unit=1.0,
)
APPROVED = ApprovalRecord(
    state=ApprovalState.APPROVED,
    reviewed_by="usr_animation_lead",
    reviewed_at=FIXTURE_TIME,
    comment="用于确定性模块 fixture。",
)


def remember_home_bundle() -> CharacterBundle:
    character = CharacterSpec(
        character_id="char_homekeeper",
        display_name="归家者",
        source_asset_id="asset_homekeeper_source",
        source_kind="imported",
        feature_links=[FeatureLink(feature_spec_id="feature_key_door_branch", task_ids=["task_player_traversal"])],
        expected_bone_names=["Root", "Pelvis", "Spine", "Head", "Foot.L", "Foot.R"],
        coordinate_system=COORDINATES,
        provenance=_provenance("char_homekeeper", "character-spec", ["asset_homekeeper_source"]),
    )
    rig = remember_home_rig()
    skin = _skin(rig)
    clips = [_clip("idle", "clip_idle_v1", True, "in_place"), _clip("walk", "clip_walk_v1", True, "extract")]
    states = _animator_states(clips)
    return CharacterBundle(
        character=character,
        rig=rig,
        skin=skin,
        clips=clips,
        retarget_profiles=[remember_home_retarget_profile()],
        animator_states=states,
    )


def remember_home_rig() -> RigVersion:
    bones = [
        BoneSpec(bone_id="bone_root", name="Root", rest_translation_meters=(0, 0, 0)),
        BoneSpec(bone_id="bone_pelvis", name="Pelvis", parent_bone_id="bone_root", rest_translation_meters=(0, 0.9, 0)),
        BoneSpec(bone_id="bone_spine", name="Spine", parent_bone_id="bone_pelvis", rest_translation_meters=(0, 0.3, 0)),
        BoneSpec(bone_id="bone_head", name="Head", parent_bone_id="bone_spine", rest_translation_meters=(0, 0.55, 0)),
        BoneSpec(bone_id="bone_foot_l", name="Foot.L", parent_bone_id="bone_pelvis", rest_translation_meters=(-0.12, -0.9, 0)),
        BoneSpec(bone_id="bone_foot_r", name="Foot.R", parent_bone_id="bone_pelvis", rest_translation_meters=(0.12, -0.9, 0)),
    ]
    return RigVersion(
        rig_version_id="rig_homekeeper_v1",
        character_id="char_homekeeper",
        version_number=1,
        source_rig_id="source_rig_homekeeper",
        bones=bones,
        coordinate_system=COORDINATES,
        approval=APPROVED,
        provenance=_provenance("rig_homekeeper_v1", "rig-version", ["char_homekeeper"]),
    )


def target_humanoid_rig() -> RigVersion:
    source = remember_home_rig()
    target_bones = [
        bone.model_copy(
            update={
                "bone_id": bone.bone_id.replace("bone_", "target_bone_"),
                "parent_bone_id": (
                    bone.parent_bone_id.replace("bone_", "target_bone_") if bone.parent_bone_id else None
                ),
            }
        )
        for bone in source.bones
    ]
    return source.model_copy(
        update={
            "rig_version_id": "rig_unity_humanoid_v1",
            "source_rig_id": "source_rig_unity_humanoid",
            "bones": target_bones,
            "provenance": _provenance("rig_unity_humanoid_v1", "rig-version", ["char_homekeeper"]),
        }
    )


def remember_home_retarget_profile() -> RetargetProfile:
    mappings = [
        RetargetBoneMapping(
            source_bone_id=bone.bone_id,
            target_bone_id=bone.bone_id.replace("bone_", "target_bone_"),
        )
        for bone in remember_home_rig().bones
    ]
    return RetargetProfile(
        retarget_profile_id="retarget_homekeeper_unity_v1",
        source_rig_version_id="rig_homekeeper_v1",
        target_rig_version_id="rig_unity_humanoid_v1",
        coordinate_system=COORDINATES,
        mappings=mappings,
        root_bone_mapping=mappings[0],
        provenance=_provenance(
            "retarget_homekeeper_unity_v1",
            "retarget-profile",
            ["rig_homekeeper_v1", "rig_unity_humanoid_v1"],
        ),
    )


def fixed_preview_camera() -> FixedPreviewCamera:
    return FixedPreviewCamera(
        camera_id="camera_character_regression_v1",
        position_meters=(0.0, 1.1, -3.2),
        target_meters=(0.0, 1.0, 0.0),
        vertical_fov_degrees=35,
        resolution_width=960,
        resolution_height=960,
    )


def _skin(rig: RigVersion) -> SkinVersion:
    vertices = [
        VertexWeights(vertex_index=0, influences=[SkinInfluence(bone_id="bone_pelvis", weight=1.0)]),
        VertexWeights(
            vertex_index=1,
            influences=[
                SkinInfluence(bone_id="bone_pelvis", weight=0.55),
                SkinInfluence(bone_id="bone_spine", weight=0.45),
            ],
        ),
        VertexWeights(vertex_index=2, influences=[SkinInfluence(bone_id="bone_head", weight=1.0)]),
    ]
    return SkinVersion(
        skin_version_id="skin_homekeeper_v1",
        character_id="char_homekeeper",
        rig_version_id=rig.rig_version_id,
        version_number=1,
        vertices=vertices,
        approval=APPROVED,
        provenance=_provenance("skin_homekeeper_v1", "skin-version", [rig.rig_version_id]),
    )


def _clip(name: str, clip_id: str, loop: bool, root_motion: str) -> AnimationClipSpec:
    displacement = 1.0 if root_motion == "extract" else 0.0
    pose = LoopPose(root_translation_meters=(0, 0, 0), root_rotation_degrees=(0, 0, 0))
    return AnimationClipSpec(
        clip_version_id=clip_id,
        character_id="char_homekeeper",
        rig_version_id="rig_homekeeper_v1",
        version_number=1,
        name=name,
        duration_seconds=1.0,
        sample_rate_hz=30,
        loop=loop,
        root_motion=root_motion,
        start_pose=pose,
        end_pose=pose,
        root_samples=[
            RootMotionSample(time_seconds=0, translation_meters=(0, 0, 0)),
            RootMotionSample(time_seconds=1, translation_meters=(0, 0, displacement)),
        ],
        foot_samples=_foot_samples(),
        event_markers=[AnimationEventMarker(marker_id="marker_{}_step".format(name), name="footstep", time_seconds=0.5)],
        approval=APPROVED,
        provenance=_provenance(clip_id, "animation-clip", ["char_homekeeper", "rig_homekeeper_v1"]),
    )


def _foot_samples() -> List[FootPlantSample]:
    return [
        FootPlantSample(time_seconds=0.0, foot="left", planted=True, position_meters=(-0.12, 0, 0)),
        FootPlantSample(time_seconds=0.25, foot="left", planted=True, position_meters=(-0.115, 0, 0)),
        FootPlantSample(time_seconds=0.5, foot="right", planted=True, position_meters=(0.12, 0, 0)),
        FootPlantSample(time_seconds=0.75, foot="right", planted=True, position_meters=(0.115, 0, 0)),
    ]


def _animator_states(clips: List[AnimationClipSpec]) -> List[AnimatorStateSpec]:
    idle, walk = clips
    return [
        AnimatorStateSpec(
            animator_state_id="anim_state_idle",
            character_id="char_homekeeper",
            name="Idle",
            clip_version_id=idle.clip_version_id,
            speed=1,
            transitions=[
                AnimatorTransitionSpec(
                    target_state_id="anim_state_walk",
                    condition_parameter="speed",
                    comparison="greater",
                    threshold=0.1,
                    duration_seconds=0.15,
                )
            ],
            provenance=_provenance("anim_state_idle", "animator-state", [idle.clip_version_id]),
        ),
        AnimatorStateSpec(
            animator_state_id="anim_state_walk",
            character_id="char_homekeeper",
            name="Walk",
            clip_version_id=walk.clip_version_id,
            speed=1,
            transitions=[
                AnimatorTransitionSpec(
                    target_state_id="anim_state_idle",
                    condition_parameter="speed",
                    comparison="less",
                    threshold=0.1,
                    duration_seconds=0.15,
                )
            ],
            provenance=_provenance("anim_state_walk", "animator-state", [walk.clip_version_id]),
        ),
    ]


def _provenance(artifact_id: str, artifact_type: str, related_ids: List[str]) -> Provenance:
    return Provenance(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        source_project_id="prj_remember_home",
        source_version="fixture-1",
        source_commit="1d4f0f3",
        related_sceneops_ids=related_ids,
        tool="imported-fixture",
        adapter_version="1.0.0",
        recipe_version="remember-home-character-v1",
        creator="fixture_worker",
        execution_mode=ExecutionMode.MOCK,
        created_at=FIXTURE_TIME,
        checksum_sha256=CHECKSUM,
        approval_state=ApprovalState.APPROVED,
    )
