from __future__ import annotations

import unittest

from test_support import run_fixture

from ai_playtest.backpin import BackpinResolver, BackpinReviewError
from ai_playtest.changesets import ChangeSetProposalError
from ai_playtest.schemas import BackpinStatus, ExecutionMode, FailureKind
from ai_playtest.schemas import SourceCandidate


class BackpinAndChangeSetTests(unittest.TestCase):
    def setUp(self):
        self.run, self.adapter, self.service, self.repository = run_fixture(
            "find-my-way-home-before.runtime.json", "run.backpin"
        )
        self.issue = next(
            issue
            for issue in self.run.issues
            if issue.failure_signal.kind == FailureKind.COLLIDER_ERROR
        )

    def test_exact_identity_backpin_resolves_with_evidence(self):
        backpin = self.issue.backpin
        self.assertEqual(backpin.status, BackpinStatus.RESOLVED)
        self.assertEqual(backpin.sceneops_id, "sceneops.home-door")
        self.assertEqual(backpin.target_type.value, "component")
        self.assertGreaterEqual(backpin.confidence, 0.7)
        self.assertTrue(backpin.evidence_ids)

    def test_equal_candidates_are_ambiguous_not_falsely_resolved(self):
        source = self.adapter.fixture["source_candidates"][0]
        other = dict(source)
        other["target_id"] = "component.home-door-collider"
        other["locator"] = "Assets/Scenes/Home.unity#DoorCollider"
        candidates = self.adapter.source_candidates(None, "sceneops.home-door")
        from ai_playtest.schemas import SourceCandidate

        candidates.append(SourceCandidate.model_validate(other))
        result = BackpinResolver().resolve(
            "backpin.ambiguous",
            self.issue.failure_signal,
            self.issue.evidence,
            candidates,
        )
        self.assertEqual(result.status, BackpinStatus.AMBIGUOUS)
        self.assertTrue(result.alternatives)

    def test_no_candidate_is_unresolved_and_human_rejection_is_retained(self):
        unresolved = BackpinResolver().resolve(
            "backpin.none", self.issue.failure_signal, self.issue.evidence, []
        )
        self.assertEqual(unresolved.status, BackpinStatus.UNRESOLVED)
        rejected_issue = self.service.review_backpin(
            self.issue.issue_id, "user.qa-reviewer", "reject"
        )
        rejected = rejected_issue.backpin
        self.assertEqual(rejected.status, BackpinStatus.REJECTED)
        self.assertEqual(rejected.reviewed_by, "user.qa-reviewer")
        self.assertIn("人工审核拒绝", rejected.reasons[-1])
        self.assertIn("人工拒绝", rejected_issue.limitation_labels[0])
        persisted = self.repository.get_issue(self.issue.issue_id)
        self.assertEqual(persisted.backpin, rejected)
        self.assertEqual(persisted.evidence, self.issue.evidence)

    def test_candidate_from_another_build_is_never_eligible(self):
        candidate = self.adapter.source_candidates(None, "sceneops.home-door")[0]
        stale = SourceCandidate.model_validate(
            candidate.model_copy(update={"build_id": "build.hero.stale"})
        )
        result = BackpinResolver().resolve(
            "backpin.stale-build",
            self.issue.failure_signal,
            self.issue.evidence,
            [stale],
        )
        self.assertEqual(result.status, BackpinStatus.UNRESOLVED)
        self.assertEqual(result.alternatives, [])

    def test_clicking_issue_restores_scene_object_camera_path_and_time(self):
        command = self.service.restore_issue(self.issue.issue_id)
        self.assertEqual(command.command_id, "workbench.context.restore")
        self.assertEqual(command.run_id, self.issue.run_id)
        self.assertEqual(command.build_id, self.issue.evidence.build_id)
        self.assertEqual(command.execution_mode, self.issue.execution_mode)
        self.assertTrue(command.require_confirmation)
        self.assertEqual(command.context.scene_id, self.issue.evidence.scene_id)
        self.assertEqual(
            command.context.selected_sceneops_ids, ["sceneops.home-door"]
        )
        self.assertEqual(command.context.camera, self.issue.evidence.camera)
        self.assertTrue(command.context.trajectory)
        self.assertGreater(command.context.timeline_time_seconds, 0)
        self.assertEqual(command.context.step_index, self.issue.restoration.step_index)

    def test_changeset_is_only_a_planned_typed_proposal_for_owning_module(self):
        reviewed = self.service.review_backpin(
            self.issue.issue_id, "user.qa-reviewer", "confirm"
        )
        self.assertEqual(reviewed.backpin.reviewed_by, "user.qa-reviewer")
        self.assertIn("人工确认", reviewed.limitation_labels[0])
        proposal = self.service.propose_issue_change(
            self.issue.issue_id,
            proposal_id="proposal.door-collider",
            base_version="git:abc123",
            target_integration="unity",
            previous_values={"interaction_layer": "Default"},
            proposed_values={"interaction_layer": "Interactable"},
            rationale="Collider evidence shows the interaction ray is blocked.",
            expected_result="The same key-door TestCase can activate the door.",
            impact_scope="Home door interaction component only.",
            risk="medium",
            validation_plan=["Dry-run owning module ChangeSet", "Rerun exact TestCase"],
            rollback_plan=["Restore component value from ChangeSet snapshot"],
            approval_requirements=["logic-studio owner", "human approval"],
        )
        self.assertEqual(proposal.command_id, "changeset.propose")
        self.assertEqual(proposal.owning_module, "logic-studio")
        self.assertEqual(proposal.execution_mode, ExecutionMode.PLANNED)
        self.assertEqual(proposal.target_object_ids, ["component.home-door-interaction"])
        persisted_run = self.repository.get_run(self.run.run_id)
        persisted_issue = next(
            item for item in persisted_run.issues if item.issue_id == self.issue.issue_id
        )
        self.assertEqual(persisted_issue.backpin.reviewed_by, "user.qa-reviewer")
        with self.assertRaises(BackpinReviewError):
            self.service.review_backpin(
                self.issue.issue_id, "user.second-reviewer", "reject"
            )

    def test_unreviewed_resolved_backpin_cannot_create_change_proposal(self):
        with self.assertRaises(ChangeSetProposalError):
            self.service.propose_issue_change(
                self.issue.issue_id,
                proposal_id="proposal.unreviewed",
                base_version="git:abc123",
                target_integration="unity",
                previous_values={},
                proposed_values={},
                rationale="not reviewed",
                expected_result="not available",
                impact_scope="unknown",
                risk="high",
                validation_plan=["review backpin"],
                rollback_plan=["no mutation occurred"],
                approval_requirements=["human"],
            )

    def test_ambiguous_backpin_cannot_create_fix_proposal(self):
        ambiguous = self.issue.backpin.model_copy(
            update={"status": BackpinStatus.AMBIGUOUS}
        )
        issue = self.issue.model_copy(update={"backpin": ambiguous})
        self.repository.save_issue(issue)
        with self.assertRaises(ChangeSetProposalError):
            self.service.propose_issue_change(
                issue.issue_id,
                proposal_id="proposal.invalid",
                base_version="git:abc123",
                target_integration="unity",
                previous_values={},
                proposed_values={},
                rationale="not allowed",
                expected_result="not allowed",
                impact_scope="unknown",
                risk="high",
                validation_plan=["none"],
                rollback_plan=["none"],
                approval_requirements=["human"],
            )


if __name__ == "__main__":
    unittest.main()
