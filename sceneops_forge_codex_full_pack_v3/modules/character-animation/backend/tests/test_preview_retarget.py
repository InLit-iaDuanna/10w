import unittest

from pydantic import ValidationError

from sceneops_character_animation.adapter import DeterministicMockCharacterToolAdapter
from sceneops_character_animation.common import ExecutionMode
from sceneops_character_animation.fixtures import (
    fixed_preview_camera,
    remember_home_bundle,
    remember_home_retarget_profile,
    target_humanoid_rig,
)
from sceneops_character_animation.operation_models import PreviewCaptureRequest, RetargetPreviewRequest
from sceneops_character_animation.errors import InvalidVersionError
from sceneops_character_animation.service import CharacterAnimationService


def rebuilt(model, **updates):
    value = model.model_dump(mode="python")
    value.update(updates)
    return type(model).model_validate(value)


class PreviewAndRetargetTests(unittest.TestCase):
    def setUp(self):
        self.bundle = remember_home_bundle()
        self.adapter = DeterministicMockCharacterToolAdapter()
        self.service = CharacterAnimationService(adapter=self.adapter)

    def test_fixed_camera_preview_has_mock_mode_and_full_provenance(self):
        request = PreviewCaptureRequest(
            request_id="capture_idle",
            character=self.bundle.character,
            rig=self.bundle.rig,
            clip=self.bundle.clips[0],
            camera=fixed_preview_camera(),
        )
        preview = self.service.capture_preview(request)
        self.assertEqual(preview.execution_mode, ExecutionMode.MOCK)
        self.assertEqual(preview.camera.camera_id, "camera_character_regression_v1")
        self.assertEqual(preview.media_type, "video/mp4")
        self.assertEqual(preview.frame_count, 31)
        self.assertEqual(preview.provenance.execution_mode, ExecutionMode.MOCK)
        self.assertEqual(
            preview.provenance.related_sceneops_ids[:3],
            [self.bundle.character.character_id, self.bundle.rig.rig_version_id, self.bundle.clips[0].clip_version_id],
        )
        self.assertIn("feature_key_door_branch", preview.provenance.related_sceneops_ids)
        self.assertIn("task_player_traversal", preview.provenance.related_sceneops_ids)

    def test_preview_regression_requires_same_fixed_camera(self):
        request = PreviewCaptureRequest(
            request_id="capture_base",
            character=self.bundle.character,
            rig=self.bundle.rig,
            clip=self.bundle.clips[0],
            camera=fixed_preview_camera(),
        )
        baseline = self.service.capture_preview(request)
        candidate = self.service.capture_preview(rebuilt(request, request_id="capture_candidate", baseline_preview=baseline))
        result = self.service.compare_previews(baseline, candidate)
        self.assertEqual(result.outcome, "passed")
        moved_camera = rebuilt(candidate.camera, position_meters=(1, 1, -3))
        blocked = self.service.compare_previews(baseline, rebuilt(candidate, camera=moved_camera))
        self.assertEqual(blocked.outcome, "blocked")
        self.assertIsNone(blocked.frame_difference_score)

    def test_retarget_profile_round_trips_and_mock_preview_is_explicit(self):
        profile = remember_home_retarget_profile()
        restored = type(profile).model_validate_json(profile.model_dump_json())
        self.assertEqual(restored, profile)
        result = self.service.preview_retarget(
            RetargetPreviewRequest(
                request_id="retarget_walk",
                character=self.bundle.character,
                source_rig=self.bundle.rig,
                target_rig=target_humanoid_rig(),
                source_clip=self.bundle.clips[1],
                profile=profile,
                camera=fixed_preview_camera(),
            )
        )
        self.assertTrue(result.profile_valid)
        self.assertEqual(result.mode, ExecutionMode.MOCK)
        self.assertEqual(result.preview.rig_version_id, "rig_unity_humanoid_v1")

    def test_invalid_retarget_mapping_blocks_capture(self):
        profile = remember_home_retarget_profile()
        mappings = list(profile.mappings)
        mappings[-1] = rebuilt(mappings[-1], target_bone_id="target_bone_missing")
        invalid = rebuilt(profile, mappings=mappings)
        result = self.service.preview_retarget(
            RetargetPreviewRequest(
                request_id="retarget_invalid",
                character=self.bundle.character,
                source_rig=self.bundle.rig,
                target_rig=target_humanoid_rig(),
                source_clip=self.bundle.clips[1],
                profile=invalid,
                camera=fixed_preview_camera(),
            )
        )
        self.assertFalse(result.profile_valid)
        self.assertEqual(result.mode, ExecutionMode.BLOCKED)
        self.assertIsNone(result.preview)

    def test_retarget_contract_rejects_a_root_mapping_outside_mapping_list(self):
        profile = remember_home_retarget_profile()
        unknown_root = rebuilt(profile.root_bone_mapping, target_bone_id="target_bone_missing")
        with self.assertRaises(ValidationError):
            rebuilt(profile, root_bone_mapping=unknown_root)

    def test_preview_rejects_clip_with_missing_motion_evidence(self):
        invalid_clip = rebuilt(self.bundle.clips[0], root_samples=[], foot_samples=[])
        with self.assertRaises(InvalidVersionError):
            self.service.capture_preview(
                PreviewCaptureRequest(
                    request_id="capture_without_evidence",
                    character=self.bundle.character,
                    rig=self.bundle.rig,
                    clip=invalid_clip,
                    camera=fixed_preview_camera(),
                )
            )


if __name__ == "__main__":
    unittest.main()
