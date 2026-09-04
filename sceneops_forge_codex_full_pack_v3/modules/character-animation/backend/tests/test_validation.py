import unittest

from sceneops_character_animation.animation_models import AnimationEventMarker, FootPlantSample, LoopPose, RootMotionSample
from sceneops_character_animation.character_models import RigVersion, SkinInfluence, SkinVersion, VertexWeights
from sceneops_character_animation.common import CheckStatus, CoordinateSystem, ExecutionMode
from sceneops_character_animation.fixtures import remember_home_bundle
from sceneops_character_animation.operation_models import CharacterBundle
from sceneops_character_animation.validation import validate_bundle


def rebuilt(model, **updates):
    value = model.model_dump(mode="python")
    value.update(updates)
    return type(model).model_validate(value)


class CharacterValidationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = remember_home_bundle()

    def test_valid_fixture_passes_without_human_approval_claim(self):
        report = validate_bundle(self.bundle, ExecutionMode.MOCK)
        self.assertEqual(report.automated_outcome, "passed")
        self.assertFalse(report.human_quality_approval)
        self.assertTrue(all(check.status == CheckStatus.PASS for check in report.checks))

    def test_optional_generated_source_is_inspectable_without_auto_rigging(self):
        character = rebuilt(
            self.bundle.character,
            source_kind="generated",
            provenance=rebuilt(self.bundle.character.provenance, tool="upstream-generated-artifact"),
        )
        report = validate_bundle(rebuilt(self.bundle, character=character), ExecutionMode.MOCK)
        self.assertEqual(report.automated_outcome, "passed")

    def test_every_version_provenance_identifies_its_own_stable_id(self):
        artifacts = [
            (self.bundle.character.character_id, self.bundle.character.provenance.artifact_id),
            (self.bundle.rig.rig_version_id, self.bundle.rig.provenance.artifact_id),
            (self.bundle.skin.skin_version_id, self.bundle.skin.provenance.artifact_id),
            *[(clip.clip_version_id, clip.provenance.artifact_id) for clip in self.bundle.clips],
        ]
        self.assertTrue(all(entity_id == artifact_id for entity_id, artifact_id in artifacts))

    def test_skeleton_missing_bone_and_scale_axis_fail(self):
        bones = [bone for bone in self.bundle.rig.bones if bone.name != "Head"]
        coordinates = CoordinateSystem(
            space="rig_local",
            handedness="left",
            up_axis="Z",
            forward_axis="Y",
            meters_per_unit=0.01,
        )
        rig = rebuilt(self.bundle.rig, bones=bones, coordinate_system=coordinates)
        bundle = rebuilt(self.bundle, rig=rig, skin=rebuilt(self.bundle.skin, rig_version_id=rig.rig_version_id))
        report = validate_bundle(bundle, ExecutionMode.MOCK)
        checks = {item.code: item for item in report.checks}
        self.assertEqual(checks["character.missing_bones"].status, CheckStatus.FAIL)
        self.assertEqual(checks["character.scale_axis"].status, CheckStatus.FAIL)
        self.assertIn("Head", checks["character.missing_bones"].evidence["missing_bone_names"])

    def test_invalid_clip_length_and_marker_are_exposed(self):
        clip = rebuilt(
            self.bundle.clips[0],
            duration_seconds=0,
            sample_rate_hz=0,
            event_markers=[AnimationEventMarker(marker_id="marker_bad", name="bad", time_seconds=2)],
        )
        bundle = rebuilt(self.bundle, clips=[clip])
        report = validate_bundle(bundle, ExecutionMode.MOCK)
        statuses = {item.code: item.status for item in report.checks}
        self.assertEqual(statuses["animation.clip_length"], CheckStatus.FAIL)
        self.assertEqual(statuses["animation.event_markers"], CheckStatus.FAIL)

    def test_loop_and_in_place_root_motion_checks_fail(self):
        moved_pose = LoopPose(root_translation_meters=(0.1, 0, 0), root_rotation_degrees=(0, 6, 0))
        clip = rebuilt(
            self.bundle.clips[0],
            end_pose=moved_pose,
            root_samples=[
                RootMotionSample(time_seconds=0, translation_meters=(0, 0, 0)),
                RootMotionSample(time_seconds=1, translation_meters=(0.05, 0, 0)),
            ],
        )
        report = validate_bundle(rebuilt(self.bundle, clips=[clip]), ExecutionMode.MOCK)
        statuses = {item.code: item.status for item in report.checks}
        self.assertEqual(statuses["animation.loop_seam"], CheckStatus.FAIL)
        self.assertEqual(statuses["animation.root_motion"], CheckStatus.FAIL)

    def test_skin_anomaly_and_foot_sliding_warning_include_evidence(self):
        skin = rebuilt(
            self.bundle.skin,
            vertices=[
                VertexWeights(
                    vertex_index=0,
                    influences=[
                        SkinInfluence(bone_id="bone_unknown", weight=0.8),
                        SkinInfluence(bone_id="bone_pelvis", weight=0.8),
                    ],
                )
            ],
        )
        clip = rebuilt(
            self.bundle.clips[0],
            foot_samples=[
                FootPlantSample(time_seconds=0, foot="left", planted=True, position_meters=(0, 0, 0)),
                FootPlantSample(time_seconds=0.2, foot="left", planted=True, position_meters=(0.04, 0, 0)),
            ],
        )
        report = validate_bundle(rebuilt(self.bundle, skin=skin, clips=[clip]), ExecutionMode.MOCK)
        checks = {item.code: item for item in report.checks}
        self.assertEqual(checks["character.skin_weights"].status, CheckStatus.FAIL)
        self.assertEqual(checks["animation.foot_sliding"].status, CheckStatus.WARNING)
        self.assertTrue(checks["animation.foot_sliding"].heuristic)
        self.assertIn("动画师", checks["animation.foot_sliding"].limitation)

    def test_missing_motion_evidence_is_blocked_not_reported_as_passed(self):
        clips = [rebuilt(clip, root_samples=[], foot_samples=[]) for clip in self.bundle.clips]
        report = validate_bundle(rebuilt(self.bundle, clips=clips), ExecutionMode.MOCK)
        checks = {item.code: item for item in report.checks}
        self.assertEqual(checks["animation.root_motion"].status, CheckStatus.BLOCKED)
        self.assertEqual(checks["animation.foot_sliding"].status, CheckStatus.BLOCKED)
        self.assertEqual(report.automated_outcome, "blocked")


if __name__ == "__main__":
    unittest.main()
