"""Inspectable validation algorithms for imported character data."""

from math import sqrt
from typing import Dict, Iterable, List, Set

from .animation_models import AnimationClipSpec, AnimatorStateSpec, RetargetProfile
from .character_models import CharacterSpec, RigVersion, SkinVersion
from .common import CheckStatus, ExecutionMode, Severity, Vector3
from .operation_models import CharacterBundle, QualityCheck, QualityReport


def validate_bundle(bundle: CharacterBundle, mode: ExecutionMode) -> QualityReport:
    checks = []
    checks.extend(validate_skeleton(bundle.character, bundle.rig))
    checks.append(validate_scale_and_axis(bundle.character, bundle.rig))
    checks.append(validate_skin_weights(bundle.skin, bundle.rig))
    for clip in bundle.clips:
        checks.extend(validate_clip(clip))
    checks.extend(validate_animator_states(bundle.animator_states, bundle.clips))
    outcome = _outcome(checks)
    return QualityReport(
        report_id="report_{}_{}".format(bundle.character.character_id, bundle.rig.rig_version_id),
        character_id=bundle.character.character_id,
        mode=mode,
        checks=checks,
        automated_outcome=outcome,
        human_quality_approval=False,
    )


def validate_skeleton(character: CharacterSpec, rig: RigVersion) -> List[QualityCheck]:
    bones_by_id = {bone.bone_id: bone for bone in rig.bones}
    duplicate_ids = _duplicates(bone.bone_id for bone in rig.bones)
    duplicate_names = _duplicates(bone.name for bone in rig.bones)
    missing_parents = sorted(
        bone.parent_bone_id
        for bone in rig.bones
        if bone.parent_bone_id and bone.parent_bone_id not in bones_by_id
    )
    roots = [bone.bone_id for bone in rig.bones if bone.parent_bone_id is None]
    cycles = sorted(_cycle_members(bones_by_id))
    evidence = {
        "root_bone_ids": roots,
        "duplicate_bone_ids": duplicate_ids,
        "duplicate_bone_names": duplicate_names,
        "missing_parent_ids": missing_parents,
        "cycle_bone_ids": cycles,
    }
    invalid = duplicate_ids or duplicate_names or missing_parents or cycles or len(roots) != 1
    hierarchy = _quality(
        "character.skeleton_hierarchy",
        not invalid,
        "骨骼层级有效。",
        "骨骼层级包含重复项、缺失父级、循环或非单一根骨。",
        evidence,
    )
    present_names = {bone.name for bone in rig.bones}
    missing_names = sorted(set(character.expected_bone_names) - present_names)
    missing = _quality(
        "character.missing_bones",
        not missing_names,
        "所需骨骼均存在。",
        "缺少角色规格要求的骨骼。",
        {"missing_bone_names": missing_names},
    )
    return [hierarchy, missing]


def validate_scale_and_axis(character: CharacterSpec, rig: RigVersion) -> QualityCheck:
    expected = character.coordinate_system
    actual = rig.coordinate_system
    scale_valid = actual.meters_per_unit > 0 and abs(actual.meters_per_unit - expected.meters_per_unit) <= 1e-6
    axes_valid = (
        actual.handedness == expected.handedness
        and actual.up_axis == expected.up_axis
        and actual.forward_axis == expected.forward_axis
    )
    evidence = {
        "expected": expected.model_dump(mode="json"),
        "actual": actual.model_dump(mode="json"),
    }
    return _quality(
        "character.scale_axis",
        scale_valid and axes_valid,
        "比例、单位与坐标轴匹配。",
        "比例、单位或坐标轴与角色规格不匹配。",
        evidence,
    )


def validate_skin_weights(skin: SkinVersion, rig: RigVersion) -> QualityCheck:
    bone_ids = {bone.bone_id for bone in rig.bones}
    invalid_vertices = []
    for vertex in skin.vertices:
        total = sum(influence.weight for influence in vertex.influences)
        unknown = [item.bone_id for item in vertex.influences if item.bone_id not in bone_ids]
        invalid = (
            not vertex.influences
            or len(vertex.influences) > skin.max_supported_influences
            or any(item.weight < 0 or item.weight > 1 for item in vertex.influences)
            or abs(total - 1.0) > 0.01
            or bool(unknown)
        )
        if invalid:
            invalid_vertices.append({"vertex_index": vertex.vertex_index, "sum": total, "unknown_bones": unknown})
    return _quality(
        "character.skin_weights",
        not invalid_vertices,
        "蒙皮权重满足归一化、影响数和骨骼引用约束。",
        "检测到未归一、越界、空权重、过多影响或未知骨骼。",
        {"invalid_vertices": invalid_vertices, "checked_vertices": len(skin.vertices)},
    )


def validate_clip(clip: AnimationClipSpec) -> List[QualityCheck]:
    return [
        _clip_length_check(clip),
        _event_marker_check(clip),
        _root_motion_check(clip),
        _loop_seam_check(clip),
        _foot_sliding_check(clip),
    ]


def validate_animator_states(
    states: List[AnimatorStateSpec], clips: List[AnimationClipSpec]
) -> List[QualityCheck]:
    if not states:
        return [_warning("animation.animator_graph", "尚未提供 Animator 状态图。", {"state_count": 0})]
    state_ids = {state.animator_state_id for state in states}
    clip_ids = {clip.clip_version_id for clip in clips}
    invalid_clip_states = [state.animator_state_id for state in states if state.clip_version_id not in clip_ids]
    invalid_targets = [
        transition.target_state_id
        for state in states
        for transition in state.transitions
        if transition.target_state_id not in state_ids
    ]
    duplicate_state_ids = _duplicates(state.animator_state_id for state in states)
    valid = not invalid_clip_states and not invalid_targets and not duplicate_state_ids
    return [
        _quality(
            "animation.animator_graph",
            valid,
            "Animator 状态与转换引用有效。",
            "Animator 状态引用了未知片段或目标状态。",
            {
                "invalid_clip_states": invalid_clip_states,
                "invalid_transition_targets": invalid_targets,
                "duplicate_state_ids": duplicate_state_ids,
            },
        )
    ]


def validate_retarget_profile(
    profile: RetargetProfile, source_rig: RigVersion, target_rig: RigVersion
) -> List[QualityCheck]:
    source_ids = {bone.bone_id for bone in source_rig.bones}
    target_ids = {bone.bone_id for bone in target_rig.bones}
    missing_source = [item.source_bone_id for item in profile.mappings if item.source_bone_id not in source_ids]
    missing_target = [item.target_bone_id for item in profile.mappings if item.target_bone_id not in target_ids]
    duplicate_targets = _duplicates(item.target_bone_id for item in profile.mappings)
    ids_match = (
        profile.source_rig_version_id == source_rig.rig_version_id
        and profile.target_rig_version_id == target_rig.rig_version_id
    )
    valid = ids_match and not missing_source and not missing_target and not duplicate_targets
    evidence = {
        "rig_ids_match": ids_match,
        "missing_source_bones": missing_source,
        "missing_target_bones": missing_target,
        "duplicate_target_bones": duplicate_targets,
    }
    return [
        _quality(
            "animation.retarget_profile",
            valid,
            "重定向映射引用有效且目标唯一。",
            "重定向映射包含错误的 Rig、缺失骨骼或重复目标。",
            evidence,
        )
    ]


def _clip_length_check(clip: AnimationClipSpec) -> QualityCheck:
    valid = clip.duration_seconds > 0 and clip.sample_rate_hz > 0
    return _quality(
        "animation.clip_length",
        valid,
        "片段时长与采样率有效。",
        "片段时长或采样率必须大于零。",
        _clip_evidence(clip, {"sample_rate_hz": clip.sample_rate_hz}),
    )


def _event_marker_check(clip: AnimationClipSpec) -> QualityCheck:
    times = [marker.time_seconds for marker in clip.event_markers]
    outside = [time for time in times if time < 0 or time > clip.duration_seconds]
    ordered = times == sorted(times)
    valid = not outside and ordered and not _duplicates(marker.marker_id for marker in clip.event_markers)
    return _quality(
        "animation.event_markers",
        valid,
        "事件标记顺序与时间范围有效。",
        "事件标记超出片段范围、顺序错误或 ID 重复。",
        _clip_evidence(clip, {"outside_times": outside, "chronological": ordered}),
    )


def _root_motion_check(clip: AnimationClipSpec) -> QualityCheck:
    if len(clip.root_samples) < 2:
        return QualityCheck(
            code="animation.root_motion",
            status=CheckStatus.BLOCKED,
            severity=Severity.WARNING,
            message="Root Motion 样本不足，无法验证声明模式。",
            evidence=_clip_evidence(clip, {"sample_count": len(clip.root_samples)}),
            limitation="至少需要两个按时间排序且位于片段范围内的根位移样本。",
        )
    times = [sample.time_seconds for sample in clip.root_samples]
    time_valid = times == sorted(times) and all(0 <= time <= clip.duration_seconds for time in times)
    displacement = _distance(
        clip.root_samples[0].translation_meters,
        clip.root_samples[-1].translation_meters,
    )
    valid = time_valid and (clip.root_motion != "in_place" or displacement <= 0.02)
    return _quality(
        "animation.root_motion",
        valid,
        "Root Motion 与声明模式一致。",
        "原地片段出现超过 0.02 米的根位移。",
        _clip_evidence(
            clip,
            {"displacement_meters": displacement, "mode": clip.root_motion, "sample_times_valid": time_valid},
        ),
    )


def _loop_seam_check(clip: AnimationClipSpec) -> QualityCheck:
    translation = _distance(clip.start_pose.root_translation_meters, clip.end_pose.root_translation_meters)
    rotation = _distance(clip.start_pose.root_rotation_degrees, clip.end_pose.root_rotation_degrees)
    valid = not clip.loop or (translation <= 0.02 and rotation <= 3.0)
    return _quality(
        "animation.loop_seam",
        valid,
        "循环首尾根姿态在阈值内。" if clip.loop else "非循环片段无需首尾缝检查。",
        "循环首尾根姿态差异超过 0.02 米或 3 度。",
        _clip_evidence(clip, {"translation_delta_meters": translation, "rotation_delta_degrees": rotation}),
    )


def _foot_sliding_check(clip: AnimationClipSpec) -> QualityCheck:
    planted_samples = [sample for sample in clip.foot_samples if sample.planted]
    movement = {}
    comparable_pairs = 0
    for foot in ("left", "right"):
        movement[foot], pairs = _max_contact_span_movement(clip, foot)
        comparable_pairs += pairs
    if len(planted_samples) < 2 or comparable_pairs == 0:
        return QualityCheck(
            code="animation.foot_sliding",
            status=CheckStatus.BLOCKED,
            severity=Severity.WARNING,
            message="脚掌接触样本不足，无法提示滑步风险。",
            evidence=_clip_evidence(
                clip,
                {"planted_sample_count": len(planted_samples), "comparable_pairs": comparable_pairs},
            ),
            heuristic=True,
            limitation="至少需要两个 planted 样本；结果仍不能替代动画师目检。",
        )
    times = [sample.time_seconds for sample in clip.foot_samples]
    time_valid = times == sorted(times) and all(0 <= time <= clip.duration_seconds for time in times)
    warning = max(movement.values(), default=0.0) > 0.025
    status = CheckStatus.WARNING if warning else CheckStatus.PASS
    severity = Severity.WARNING if warning else Severity.INFO
    if not time_valid:
        status, severity = CheckStatus.FAIL, Severity.ERROR
    return QualityCheck(
        code="animation.foot_sliding",
        status=status,
        severity=severity,
        message=_foot_message(time_valid, warning),
        evidence=_clip_evidence(
            clip,
            {"max_planted_displacement_meters": movement, "threshold_meters": 0.025, "sample_times_valid": time_valid},
        ),
        heuristic=True,
        limitation="仅依据已标记接触样本的位移提示风险，不能替代动画师目检。",
    )


def _foot_message(time_valid: bool, warning: bool) -> str:
    if not time_valid:
        return "脚掌接触样本顺序错误或超出片段范围。"
    if warning:
        return "脚掌接触期间可能发生滑步。"
    return "脚掌接触样本未超过滑步提示阈值。"


def _max_contact_span_movement(clip: AnimationClipSpec, foot: str):
    maximum = 0.0
    baseline = None
    comparable_pairs = 0
    for sample in (item for item in clip.foot_samples if item.foot == foot):
        if not sample.planted:
            baseline = None
        elif baseline is None:
            baseline = sample.position_meters
        else:
            maximum = max(maximum, _distance(baseline, sample.position_meters))
            comparable_pairs += 1
    return maximum, comparable_pairs


def _quality(
    code: str, valid: bool, passed: str, failed: str, evidence: Dict[str, object]
) -> QualityCheck:
    return QualityCheck(
        code=code,
        status=CheckStatus.PASS if valid else CheckStatus.FAIL,
        severity=Severity.INFO if valid else Severity.ERROR,
        message=passed if valid else failed,
        evidence=evidence,
    )


def _warning(code: str, message: str, evidence: Dict[str, object]) -> QualityCheck:
    return QualityCheck(
        code=code,
        status=CheckStatus.WARNING,
        severity=Severity.WARNING,
        message=message,
        evidence=evidence,
    )


def _clip_evidence(clip: AnimationClipSpec, values: Dict[str, object]) -> Dict[str, object]:
    return {"clip_version_id": clip.clip_version_id, "duration_seconds": clip.duration_seconds, **values}


def _duplicates(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for value in values:
        duplicates.add(value) if value in seen else seen.add(value)
    return sorted(duplicates)


def _cycle_members(bones_by_id: Dict[str, object]) -> Set[str]:
    cycles: Set[str] = set()
    for bone_id in bones_by_id:
        path: Set[str] = set()
        current = bone_id
        while current in bones_by_id:
            if current in path:
                cycles.add(current)
                break
            path.add(current)
            current = getattr(bones_by_id[current], "parent_bone_id")
            if current is None:
                break
    return cycles


def _distance(left: Vector3, right: Vector3) -> float:
    return sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _outcome(checks: List[QualityCheck]) -> str:
    if any(item.status == CheckStatus.FAIL for item in checks):
        return "failed"
    if any(item.status == CheckStatus.BLOCKED for item in checks):
        return "blocked"
    if any(item.status == CheckStatus.WARNING for item in checks):
        return "warnings"
    return "passed"
