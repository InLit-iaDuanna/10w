"""Deterministic, reversible rig and clip version comparisons."""

from typing import List

from .animation_models import AnimationClipSpec, AnimationEventMarker
from .character_models import BoneSpec, RigVersion
from .errors import InvalidVersionError
from .operation_models import (
    BoneChange,
    ClipVersionDiff,
    EventMarkerChange,
    RigVersionDiff,
)


def compare_rig_versions(base: RigVersion, proposed: RigVersion) -> RigVersionDiff:
    _require_rig_sequence(base, proposed)
    base_bones = {bone.bone_id: bone for bone in base.bones}
    proposed_bones = {bone.bone_id: bone for bone in proposed.bones}
    changes: List[BoneChange] = []
    for bone_id in sorted(base_bones.keys() - proposed_bones.keys()):
        changes.append(BoneChange(bone_id=bone_id, change="removed", previous_value=base_bones[bone_id].name))
    for bone_id in sorted(proposed_bones.keys() - base_bones.keys()):
        changes.append(BoneChange(bone_id=bone_id, change="added", proposed_value=proposed_bones[bone_id].name))
    for bone_id in sorted(base_bones.keys() & proposed_bones.keys()):
        changes.extend(_compare_bone(base_bones[bone_id], proposed_bones[bone_id]))
    return RigVersionDiff(
        base_rig_version_id=base.rig_version_id,
        proposed_rig_version_id=proposed.rig_version_id,
        bone_changes=changes,
        coordinate_system_changed=base.coordinate_system != proposed.coordinate_system,
        reversible=True,
    )


def compare_clip_versions(base: AnimationClipSpec, proposed: AnimationClipSpec) -> ClipVersionDiff:
    _require_clip_sequence(base, proposed)
    marker_changes = _compare_markers(base.event_markers, proposed.event_markers)
    return ClipVersionDiff(
        base_clip_version_id=base.clip_version_id,
        proposed_clip_version_id=proposed.clip_version_id,
        duration_delta_seconds=proposed.duration_seconds - base.duration_seconds,
        loop_changed=base.loop != proposed.loop,
        root_motion_changed=base.root_motion != proposed.root_motion,
        event_marker_changes=marker_changes,
        reversible=True,
    )


def _compare_bone(base: BoneSpec, proposed: BoneSpec) -> List[BoneChange]:
    changes = []
    if base.name != proposed.name:
        changes.append(
            BoneChange(
                bone_id=base.bone_id,
                change="renamed",
                previous_value=base.name,
                proposed_value=proposed.name,
            )
        )
    if base.parent_bone_id != proposed.parent_bone_id:
        changes.append(
            BoneChange(
                bone_id=base.bone_id,
                change="reparented",
                previous_value=base.parent_bone_id,
                proposed_value=proposed.parent_bone_id,
            )
        )
    return changes


def _compare_markers(
    base_markers: List[AnimationEventMarker], proposed_markers: List[AnimationEventMarker]
) -> List[EventMarkerChange]:
    base = {marker.marker_id: marker for marker in base_markers}
    proposed = {marker.marker_id: marker for marker in proposed_markers}
    changes: List[EventMarkerChange] = []
    for marker_id in sorted(base.keys() - proposed.keys()):
        changes.append(EventMarkerChange(marker_id=marker_id, change="removed", previous_value=base[marker_id].name))
    for marker_id in sorted(proposed.keys() - base.keys()):
        changes.append(EventMarkerChange(marker_id=marker_id, change="added", proposed_value=proposed[marker_id].name))
    for marker_id in sorted(base.keys() & proposed.keys()):
        changes.extend(_compare_marker(base[marker_id], proposed[marker_id]))
    return changes


def _compare_marker(base: AnimationEventMarker, proposed: AnimationEventMarker) -> List[EventMarkerChange]:
    changes = []
    if base.name != proposed.name:
        changes.append(
            EventMarkerChange(
                marker_id=base.marker_id,
                change="renamed",
                previous_value=base.name,
                proposed_value=proposed.name,
            )
        )
    if base.time_seconds != proposed.time_seconds:
        changes.append(
            EventMarkerChange(
                marker_id=base.marker_id,
                change="retimed",
                previous_value=str(base.time_seconds),
                proposed_value=str(proposed.time_seconds),
            )
        )
    return changes


def _require_rig_sequence(base: RigVersion, proposed: RigVersion) -> None:
    if base.character_id != proposed.character_id:
        raise InvalidVersionError("Rig versions must belong to the same character.")
    if proposed.previous_version_id != base.rig_version_id:
        raise InvalidVersionError("Proposed rig must reference the base rig as previous_version_id.")
    if proposed.version_number <= base.version_number:
        raise InvalidVersionError("Proposed rig version_number must advance.")


def _require_clip_sequence(base: AnimationClipSpec, proposed: AnimationClipSpec) -> None:
    if base.character_id != proposed.character_id or base.name != proposed.name:
        raise InvalidVersionError("Clip versions must represent the same named character clip.")
    if proposed.previous_version_id != base.clip_version_id:
        raise InvalidVersionError("Proposed clip must reference the base clip as previous_version_id.")
    if proposed.version_number <= base.version_number:
        raise InvalidVersionError("Proposed clip version_number must advance.")
