from __future__ import annotations

import unittest
from datetime import timedelta

from sceneops_production_planner.errors import PlannerDomainError
from sceneops_production_planner.events import approved_event_payload
from sceneops_production_planner.fixtures import key_door_snapshot
from sceneops_production_planner.graph import build_graph_view
from sceneops_production_planner.models import (
    Assignment,
    AssignmentKind,
    DeliverableLink,
    ExecutionMode,
    FeatureAcceptanceCriterion,
    FeatureSpecReference,
    TaskCommentReference,
    TaskBlocker,
    TaskStatus,
)
from sceneops_production_planner.tests.support import FIXED_TIME, create_context, create_plan, create_request, create_service, evidence_for
from sceneops_production_planner.verification import VerifiedRunTiming


class ServiceTests(unittest.TestCase):
    def test_status_transition_requires_plan_approval_upstream_evidence_and_task_approval(self) -> None:
        service, draft = create_plan()
        with self.assertRaisesRegex(PlannerDomainError, "计划确认"):
            service.transition_task(draft.plan_id, draft.tasks[0].task_id, TaskStatus.READY)

        plan = service.apply_plan_approval(draft.plan_id, "approval:plan:1")
        self.assertEqual(approved_event_payload(plan).event_type, "production.plan.approved")
        design = plan.tasks[0]
        concept = plan.tasks[1]
        with self.assertRaisesRegex(PlannerDomainError, "上游"):
            service.transition_task(plan.plan_id, concept.task_id, TaskStatus.READY)

        plan = service.transition_task(plan.plan_id, design.task_id, TaskStatus.IN_PROGRESS)
        design = plan.tasks[0]
        with self.assertRaisesRegex(PlannerDomainError, "验收证据"):
            service.transition_task(plan.plan_id, design.task_id, TaskStatus.COMPLETED)
        evidence_index = 0
        for link in design.acceptance:
            for evidence_type in link.expected_evidence:
                plan = service.link_evidence(
                    plan.plan_id,
                    design.task_id,
                    evidence_for(design, link.criterion_id, str(evidence_index), evidence_type),
                )
                evidence_index += 1
        with self.assertRaisesRegex(PlannerDomainError, "外部审批"):
            service.transition_task(plan.plan_id, design.task_id, TaskStatus.COMPLETED)
        plan = service.transition_task(
            plan.plan_id,
            design.task_id,
            TaskStatus.COMPLETED,
            approval_ref_id="approval:task:design",
        )
        self.assertEqual(plan.tasks[0].status, TaskStatus.COMPLETED)
        self.assertEqual(plan.tasks[1].status, TaskStatus.READY)
        self.assertEqual(plan.milestones[0].state.value, "ready")
        with self.assertRaises(PlannerDomainError) as caught:
            service.edit_task(
                plan.plan_id,
                design.task_id,
                title="改写已完成任务",
                description="该操作必须使用新修订。",
            )
        self.assertEqual(caught.exception.code, "TASK_REVISION_REQUIRED")
        with self.assertRaises(PlannerDomainError) as caught:
            service.replace_dependencies(plan.plan_id, plan.dependencies)
        self.assertEqual(caught.exception.code, "PLAN_REVISION_REQUIRED")

    def test_invalid_status_transition_is_rejected(self) -> None:
        service, draft = create_plan()
        plan = service.apply_plan_approval(draft.plan_id, "approval:plan:1")
        with self.assertRaises(PlannerDomainError) as caught:
            service.transition_task(plan.plan_id, plan.tasks[0].task_id, TaskStatus.COMPLETED)
        self.assertEqual(caught.exception.code, "INVALID_STATUS_TRANSITION")

    def test_assignment_edit_supports_human_and_agent_and_unconfirms_plan(self) -> None:
        service, draft = create_plan()
        approved = service.apply_plan_approval(draft.plan_id, "approval:plan:1")
        assignment = Assignment(
            assignment_id="assignment:replacement",
            kind=AssignmentKind.HUMAN,
            assignee_id="user:artist",
            display_name="资产艺术家",
            confirmed=True,
        )
        edited = service.assign_task(approved.plan_id, approved.tasks[2].task_id, assignment)
        self.assertEqual(edited.status.value, "draft_unconfirmed")
        self.assertIsNone(edited.approval_ref_id)
        self.assertEqual(edited.tasks[2].assignment.kind, AssignmentKind.HUMAN)
        self.assertFalse(edited.tasks[2].assignment.confirmed)

    def test_task_content_is_editable_and_requires_plan_reconfirmation(self) -> None:
        service, draft = create_plan()
        approved = service.apply_plan_approval(draft.plan_id, "approval:plan:1")
        task = approved.tasks[0]
        edited = service.edit_task(
            approved.plan_id,
            task.task_id,
            title="确认钥匙与家门规则",
            description="补充钥匙消费、失败反馈和可访问性验收。",
        )
        self.assertEqual(edited.tasks[0].title, "确认钥匙与家门规则")
        self.assertFalse(edited.tasks[0].confirmed)
        self.assertEqual(edited.status.value, "draft_unconfirmed")
        self.assertIsNone(edited.approval_ref_id)

    def test_repeated_create_preserves_existing_approved_plan(self) -> None:
        snapshot = key_door_snapshot()
        service = create_service(snapshot)
        request = create_request(snapshot)
        first = service.create_plan(request, create_context())
        approved = service.apply_plan_approval(first.plan.plan_id, "approval:plan:1")
        repeated = service.create_plan(request, create_context(command_id="command:repeat"))
        self.assertFalse(repeated.created)
        self.assertEqual(repeated.event_payloads, [])
        self.assertEqual(repeated.plan.status.value, "approved")
        self.assertEqual(repeated.plan.plan_version, approved.plan_version)
        self.assertTrue(repeated.plan.tasks[0].assignment.confirmed)

    def test_approval_reference_must_be_verified_by_provider(self) -> None:
        service, draft = create_plan()
        with self.assertRaises(PlannerDomainError) as caught:
            service.apply_plan_approval(draft.plan_id, "approval:arbitrary")
        self.assertEqual(caught.exception.code, "APPROVAL_NOT_VERIFIED")

    def test_operational_blocker_is_visible_and_must_be_resolved_before_ready(self) -> None:
        service, draft = create_plan()
        plan = service.apply_plan_approval(draft.plan_id, "approval:plan:1")
        task = plan.tasks[0]
        blocker = TaskBlocker(
            blocker_id="blocker:design:review-missing",
            code="operational_blocker",
            message="设计评审记录缺失。",
            task_ids=[task.task_id],
        )
        plan = service.transition_task(plan.plan_id, task.task_id, TaskStatus.BLOCKED, blocker=blocker)
        graph = build_graph_view(plan)
        self.assertEqual(graph.blockers[0].blocker_id, blocker.blocker_id)
        self.assertEqual(graph.milestone_readiness[0].state.value, "blocked")
        with self.assertRaises(PlannerDomainError) as caught:
            service.transition_task(plan.plan_id, task.task_id, TaskStatus.READY)
        self.assertEqual(caught.exception.code, "BLOCKER_UNRESOLVED")
        plan = service.resolve_task_blocker(
            plan.plan_id,
            task.task_id,
            blocker.blocker_id,
            "artifact:design-review:1",
        )
        plan = service.transition_task(plan.plan_id, task.task_id, TaskStatus.READY)
        self.assertEqual(plan.tasks[0].status, TaskStatus.READY)

    def test_measured_estimate_preserves_prediction_and_updates_graph_basis(self) -> None:
        timing = VerifiedRunTiming(
            run_id="run:design:real-1",
            task_id="task:feature:key-and-door:design",
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME + timedelta(hours=7.5),
            mode=ExecutionMode.LIVE,
        )
        service = create_service(run_timings=[timing])
        service, plan = create_plan(service)
        task = plan.tasks[0]
        changed = service.record_measured_estimate(
            plan.plan_id,
            task.task_id,
            run_id="run:design:real-1",
        )
        estimates = changed.tasks[0].estimates
        self.assertEqual([estimate.kind.value for estimate in estimates], ["predicted", "measured"])
        node = next(node for node in build_graph_view(changed).nodes if node.task_id == task.task_id)
        self.assertEqual(node.estimate_kind.value, "measured")
        self.assertEqual(node.estimate_hours, 7.5)
        with self.assertRaises(PlannerDomainError) as caught:
            service.record_measured_estimate(
                plan.plan_id,
                task.task_id,
                run_id="run:unverified",
            )
        self.assertEqual(caught.exception.code, "RUN_EVIDENCE_UNAVAILABLE")

    def test_acceptance_evidence_must_reference_task_criterion(self) -> None:
        service, plan = create_plan()
        evidence = evidence_for(plan.tasks[0], "acceptance:not-linked")
        with self.assertRaises(PlannerDomainError) as caught:
            service.link_evidence(plan.plan_id, plan.tasks[0].task_id, evidence)
        self.assertEqual(caught.exception.code, "EVIDENCE_LINK_INVALID")

    def test_deliverable_and_comment_references_link_without_owning_external_records(self) -> None:
        service, plan = create_plan()
        task = plan.tasks[0]
        deliverable = DeliverableLink(
            link_id="deliverable:design:1",
            output_id=task.outputs[0].output_id,
            artifact_id="artifact:feature-design:1",
            artifact_type=task.outputs[0].artifact_type,
            mode="mock",
        )
        plan = service.link_deliverable(plan.plan_id, task.task_id, deliverable)
        plan = service.link_comment(
            plan.plan_id,
            task.task_id,
            TaskCommentReference(comment_id="comment:1", comment_thread_id="thread:design"),
        )
        self.assertEqual(plan.tasks[0].outputs[0].artifact_id, "artifact:feature-design:1")
        self.assertEqual(plan.tasks[0].comment_thread_id, "thread:design")

    def test_feature_change_impact_includes_linked_tasks_and_downstream(self) -> None:
        old = key_door_snapshot()
        new_criterion = FeatureAcceptanceCriterion(
            criterion_id="acceptance:consume-key",
            statement="开门后钥匙被消费。",
            workstreams=["logic"],
            required_evidence=["inventory-state-log"],
        )
        new = old.model_copy(
            update={
                "feature_ref": FeatureSpecReference(
                    project_id=old.feature_ref.project_id,
                    feature_id=old.feature_ref.feature_id,
                    revision=2,
                ),
                "acceptance_criteria": old.acceptance_criteria + [new_criterion],
            }
        )
        service = create_service(old, new)
        old_plan = service.create_plan(create_request(old), create_context()).plan
        new_plan = service.create_plan(
            create_request(new),
            create_context(command_id="command:create-key-door-plan:r2"),
        ).plan
        impact = service.analyze_feature_change(old, new, old_plan, new_plan)
        self.assertIn("task:feature:key-and-door:logic", impact.affected_task_ids)
        self.assertIn("task:feature:key-and-door:test", impact.affected_task_ids)
        self.assertNotIn("task:feature:key-and-door:asset", impact.affected_task_ids)
        self.assertEqual(impact.changed_criterion_ids, ["acceptance:consume-key"])

    def test_ai_created_plan_requires_changeset_reference(self) -> None:
        snapshot = key_door_snapshot()
        service = create_service(snapshot)
        request = create_request(snapshot)
        with self.assertRaises(PlannerDomainError) as caught:
            service.create_plan(request, create_context(ai_initiated=True, change_set_id=None))
        self.assertEqual(caught.exception.code, "CHANGESET_REQUIRED")

    def test_unimplemented_cached_creation_is_rejected(self) -> None:
        snapshot = key_door_snapshot()
        service = create_service(snapshot)
        request = create_request(snapshot)
        with self.assertRaises(PlannerDomainError) as caught:
            service.create_plan(request, create_context(execution_mode=ExecutionMode.CACHED))
        self.assertEqual(caught.exception.code, "TRUSTED_LIVE_CONTEXT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
