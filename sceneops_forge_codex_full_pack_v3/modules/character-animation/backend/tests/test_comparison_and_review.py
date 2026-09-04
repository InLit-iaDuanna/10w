import unittest
from datetime import datetime, timezone

from sceneops_character_animation.animation_models import AnimationEventMarker
from sceneops_character_animation.common import ApprovalState
from sceneops_character_animation.fixtures import remember_home_bundle
from sceneops_character_animation.errors import InvalidVersionError
from sceneops_character_animation.operation_models import (
    CharacterInspectionRequest,
    VersionComparisonRequest,
    VersionReviewRequest,
)
from sceneops_character_animation.service import CharacterAnimationService


def rebuilt(model, **updates):
    value = model.model_dump(mode="python")
    value.update(updates)
    return type(model).model_validate(value)


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.bundle = remember_home_bundle()
        self.service = CharacterAnimationService()
        self.service.inspect(
            CharacterInspectionRequest(request_id="req_inspect", bundle=self.bundle, mode="mock")
        )

    def test_rig_comparison_reports_stable_id_rename_and_is_reversible(self):
        bones = list(self.bundle.rig.bones)
        bones[3] = rebuilt(bones[3], name="Head.Renamed")
        proposed = rebuilt(
            self.bundle.rig,
            rig_version_id="rig_homekeeper_v2",
            version_number=2,
            previous_version_id=self.bundle.rig.rig_version_id,
            bones=bones,
            provenance=rebuilt(self.bundle.rig.provenance, artifact_id="rig_homekeeper_v2"),
        )
        result = self.service.compare_versions(
            VersionComparisonRequest(request_id="req_rig_diff", entity_type="rig", base=self.bundle.rig, proposed=proposed)
        )
        self.assertTrue(result.diff.reversible)
        self.assertEqual(result.diff.bone_changes[0].bone_id, "bone_head")
        self.assertEqual(result.diff.bone_changes[0].change, "renamed")

    def test_clip_comparison_reports_duration_loop_root_and_marker_changes(self):
        base = self.bundle.clips[0]
        marker = AnimationEventMarker(marker_id=base.event_markers[0].marker_id, name="footstep", time_seconds=0.6)
        proposed = rebuilt(
            base,
            clip_version_id="clip_idle_v2",
            previous_version_id=base.clip_version_id,
            version_number=2,
            duration_seconds=1.2,
            loop=False,
            root_motion="apply",
            event_markers=[marker],
            provenance=rebuilt(base.provenance, artifact_id="clip_idle_v2"),
        )
        result = self.service.compare_versions(
            VersionComparisonRequest(request_id="req_clip_diff", entity_type="clip", base=base, proposed=proposed)
        )
        self.assertAlmostEqual(result.diff.duration_delta_seconds, 0.2)
        self.assertTrue(result.diff.loop_changed)
        self.assertTrue(result.diff.root_motion_changed)
        self.assertEqual(result.diff.event_marker_changes[0].change, "retimed")

    def test_review_records_approval_and_rollback_version(self):
        base = self.bundle.clips[0]
        proposed = rebuilt(
            base,
            clip_version_id="clip_idle_v2",
            previous_version_id=base.clip_version_id,
            version_number=2,
            approval=rebuilt(base.approval, state="waiting_approval", reviewed_by=None, reviewed_at=None),
            provenance=rebuilt(
                base.provenance,
                artifact_id="clip_idle_v2",
                approval_state="waiting_approval",
            ),
        )
        self.service.inspect(
            CharacterInspectionRequest(
                request_id="req_register_v2",
                bundle=rebuilt(self.bundle, clips=[proposed]),
                mode="mock",
            )
        )
        result = self.service.review_version(
            VersionReviewRequest(
                request_id="req_review",
                entity_type="clip",
                entity_id=proposed.clip_version_id,
                decision="approve",
                reviewer_id="usr_animation_lead",
                reviewed_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
                comment="回归预览通过。",
            )
        )
        self.assertEqual(result.approval.state, ApprovalState.APPROVED)
        self.assertEqual(result.rollback_version_id, base.clip_version_id)

    def test_terminal_review_cannot_be_overwritten(self):
        with self.assertRaises(InvalidVersionError):
            self.service.review_version(
                VersionReviewRequest(
                    request_id="req_review_again",
                    entity_type="clip",
                    entity_id=self.bundle.clips[0].clip_version_id,
                    decision="reject",
                    reviewer_id="usr_animation_lead",
                    reviewed_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
                    comment="不应覆盖已经批准的决定。",
                )
            )


if __name__ == "__main__":
    unittest.main()
