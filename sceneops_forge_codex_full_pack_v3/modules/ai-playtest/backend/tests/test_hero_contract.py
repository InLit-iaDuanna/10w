from __future__ import annotations

import json
import unittest

from fastapi import FastAPI

from test_support import MODULE_ROOT, run_fixture

from ai_playtest import InMemoryPlaytestRepository, create_router
from ai_playtest.schemas import (
    BackpinStatus,
    ExecutionMode,
    FailureKind,
    RegressionStatus,
    RunStatus,
    SourceCatalog,
)


class HeroContractTest(unittest.TestCase):
    def test_before_review_proposal_after_comparison_contract(self):
        repository = InMemoryPlaytestRepository()
        before, _, before_service, _ = run_fixture(
            "find-my-way-home-before.runtime.json",
            "run.hero-contract.before",
            repository=repository,
        )
        self.assertEqual(before.status, RunStatus.FAILED)
        self.assertTrue(before.comparison_eligible)
        collider_issue = next(
            issue
            for issue in before.issues
            if issue.failure_signal.kind == FailureKind.COLLIDER_ERROR
        )
        self.assertEqual(collider_issue.backpin.status, BackpinStatus.RESOLVED)
        self.assertEqual(
            collider_issue.backpin.target_id,
            "component.home-door-interaction",
        )

        catalog_path = (
            MODULE_ROOT / "contracts" / "examples" / "source-catalog.v1.json"
        )
        catalog = SourceCatalog.model_validate_json(
            catalog_path.read_text(encoding="utf-8")
        )
        source_path, source_fragment = collider_issue.backpin.source_record_uri.split(
            "#", 1
        )
        self.assertEqual(MODULE_ROOT / source_path, catalog_path)
        source_record = catalog.records[source_fragment]
        self.assertEqual(
            source_record.source_record_id,
            collider_issue.backpin.source_record_id,
        )
        self.assertEqual(source_record.build_id, before.build.build_id)

        reviewed = before_service.review_backpin(
            collider_issue.issue_id,
            "user.hero-reviewer",
            "confirm",
        )
        self.assertEqual(reviewed.backpin.reviewed_by, "user.hero-reviewer")
        restoration = before_service.restore_issue(collider_issue.issue_id)
        self.assertEqual(restoration.execution_mode, ExecutionMode.MOCK)
        self.assertTrue(restoration.require_confirmation)
        self.assertEqual(
            restoration.context.selected_sceneops_ids,
            ["sceneops.home-door"],
        )
        proposal = before_service.propose_issue_change(
            collider_issue.issue_id,
            proposal_id="proposal.hero-contract.door-collider",
            base_version=before.build.version,
            target_integration="unity-playtest-runner",
            previous_values={"interaction_layer": "Default"},
            proposed_values={"interaction_layer": "Interactable"},
            rationale="Collider evidence shows the interaction ray is blocked.",
            expected_result="The exact key-door TestCase can activate the door.",
            impact_scope="Home door interaction component only.",
            risk="medium",
            validation_plan=["Review owning module ChangeSet", "Rerun exact TestCase"],
            rollback_plan=["Restore the prior interaction layer"],
            approval_requirements=["logic-studio owner", "human approval"],
        )
        self.assertEqual(proposal.source_issue_id, collider_issue.issue_id)
        self.assertEqual(proposal.owning_module, "logic-studio")
        self.assertEqual(proposal.execution_mode, ExecutionMode.PLANNED)

        after, _, after_service, _ = run_fixture(
            "find-my-way-home-after.runtime.json",
            "run.hero-contract.after",
            repository=repository,
        )
        self.assertEqual(after.status, RunStatus.SUCCEEDED)
        self.assertTrue(after.comparison_eligible)
        comparison = after_service.compare(
            "comparison.hero-contract",
            before.run_id,
            after.run_id,
        )
        self.assertTrue(comparison.exact_configuration)
        self.assertEqual(comparison.status, RegressionStatus.IMPROVED)
        self.assertIn(collider_issue.issue_id, comparison.resolved_issue_ids)

        app = FastAPI()
        app.include_router(create_router(after_service))
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/playtests/runs", paths)
        self.assertIn("/api/v1/playtests/regressions", paths)
        print(
            json.dumps(
                {
                    "before_status": before.status.value,
                    "before_steps": len(before.steps),
                    "before_issues": len(before.issues),
                    "backpin_target": collider_issue.backpin.target_id,
                    "source_record": source_record.source_record_id,
                    "reviewer": reviewed.backpin.reviewed_by,
                    "proposal_mode": proposal.execution_mode.value,
                    "restore_confirmation": restoration.require_confirmation,
                    "after_status": after.status.value,
                    "after_steps": len(after.steps),
                    "comparison_status": comparison.status.value,
                    "exact_configuration": comparison.exact_configuration,
                    "resolved_issue_count": len(comparison.resolved_issue_ids),
                    "openapi_path_count": len(paths),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
