from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_release.enums import (
    ApprovalAction,
    ApprovalDecision,
    BuildProfile,
    CandidateStatus,
    DeploymentStatus,
    DeploymentTarget,
    ExecutionMode,
)
from build_release.models_common import Approval
from build_release.requests import (
    CreateCandidateRequest,
    DeployRequest,
    PrepareDeploymentRequest,
)

from support import (
    BASE_TIME,
    create_patch_note,
    create_ready_candidate,
    make_build_pair,
    make_service,
    record_pair,
)


MODULE_ROOT = Path(__file__).resolve().parents[1]


class ExampleGameReleaseFlowTests(unittest.TestCase):
    def test_both_games_use_one_release_implementation_with_isolated_histories(self) -> None:
        service, catalog, adapter, _ = make_service()
        observed = []
        for game_folder in ("remember-home", "warehouse-escape"):
            fixture = json.loads(
                (MODULE_ROOT / "fixtures" / game_folder / "release-scenario.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(fixture["fixture_mode"], "mock")
            self.assertEqual(fixture["cached_judge_expectation"]["status"], "blocked")
            self.assertEqual(
                set(fixture["build_profiles"]),
                {profile.value for profile in BuildProfile},
            )
            pair = make_build_pair(
                f"e2e.{fixture['scenario_slug']}",
                project_id=fixture["project_id"],
                game_id=fixture["game_id"],
                commit=fixture["source_commit"],
                output_seed=f"{fixture['scenario_slug']}-player",
            )
            record_pair(service, catalog, pair)
            self.assertEqual(pair.manifests[0].input_fingerprint, pair.manifests[1].input_fingerprint)
            self.assertEqual(pair.manifests[0].output_fingerprint, pair.manifests[1].output_fingerprint)
            candidate = create_ready_candidate(
                service, pair, fixture["mock_qa_candidate_id"]
            )
            note = create_patch_note(
                service,
                pair,
                candidate,
                f"patch-note.{fixture['scenario_slug']}.qa",
            )
            prepared = PrepareDeploymentRequest(
                deployment_id=fixture["mock_judge_deployment_id"],
                candidate_id=candidate.candidate_id,
                target=DeploymentTarget.JUDGE,
                patch_note_id=note.patch_note_id,
                patch_note_revision=note.revision,
                idempotency_key=f"key-{fixture['mock_judge_deployment_id']}",
                expected_mode=ExecutionMode.MOCK,
            )
            plan = service.prepare_deployment(prepared)
            approvals = [
                Approval(
                    approval_id=f"approval.{fixture['scenario_slug']}.judge.{index}",
                    action=ApprovalAction.DEPLOY,
                    target_id=prepared.deployment_id,
                    scope_fingerprint=plan.operation_scope_fingerprint,
                    role=role,
                    actor_id=f"user.{role}",
                    decision=ApprovalDecision.APPROVED,
                    rationale="Approve deterministic example-game deployment.",
                    decided_at=BASE_TIME,
                )
                for index, role in enumerate(plan.required_approval_roles)
            ]
            deployment = service.deploy(
                DeployRequest(**prepared.model_dump(), approvals=approvals)
            )
            self.assertEqual(deployment.status, DeploymentStatus.SUCCEEDED)
            self.assertEqual(deployment.mode, ExecutionMode.MOCK)
            observed.append((candidate, deployment))

            release_pair = make_build_pair(
                f"e2e.{fixture['scenario_slug']}.rc",
                project_id=fixture["project_id"],
                game_id=fixture["game_id"],
                commit=fixture["source_commit"],
                profile=BuildProfile.RELEASE_CANDIDATE,
                output_seed=f"{fixture['scenario_slug']}-rc-player",
            )
            record_pair(service, catalog, release_pair)
            blocked_rc = service.create_candidate(
                CreateCandidateRequest(
                    candidate_id=f"candidate.{fixture['scenario_slug']}.rc.blocked",
                    manifest_ids=[item.manifest_id for item in release_pair.manifests],
                    gates=release_pair.gates,
                    approved_change_set_ids=[
                        item.change_set_id for item in release_pair.change_sets
                    ],
                )
            )
            self.assertEqual(blocked_rc.status, CandidateStatus.BLOCKED)
            self.assertIn("GATE:EXECUTION_MODE_NOT_ALLOWED", blocked_rc.blockers)

        first_candidate, first_deployment = observed[0]
        second_candidate, second_deployment = observed[1]
        self.assertNotEqual(first_candidate.project_id, second_candidate.project_id)
        self.assertNotEqual(first_candidate.game_id, second_candidate.game_id)
        self.assertNotEqual(first_deployment.candidate_id, second_deployment.candidate_id)
        self.assertEqual(len(adapter.activations), 2)


if __name__ == "__main__":
    unittest.main()
