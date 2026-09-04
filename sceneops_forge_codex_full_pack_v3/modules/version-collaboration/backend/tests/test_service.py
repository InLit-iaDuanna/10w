from __future__ import annotations

import unittest

from version_collaboration.base import ExecutionMode
from version_collaboration.diff_models import ConflictCode
from version_collaboration.errors import ErrorCode, VersionCollaborationError
from version_collaboration.ports import UnavailableChangeSetGateway
from version_collaboration.review_models import (
    AssignmentAction,
    CommentAnchor,
    CommentAnchorKind,
    CreateReviewCommand,
    DecisionOutcome,
)
from version_collaboration.sqlite_repository import SqliteReviewRepository

from support import (
    BASE,
    TARGET,
    FakeApprovalVerifier,
    FakeGitAdapter,
    behavior_pair,
    context,
    git_diff,
    make_service,
    semantic_pair,
    version,
    visual_pair,
)


class VersionCollaborationServiceTests(unittest.TestCase):
    def _create_review(self, *, git: FakeGitAdapter | None = None):
        service, repository, fake_git, approvals, events = make_service(git=git)
        semantic_before, semantic_after = semantic_pair()
        visual_before, visual_after = visual_pair()
        behavior_before, behavior_after = behavior_pair()
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="钥匙开门分支评审",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
                visual_before=visual_before,
                visual_after=visual_after,
                behavior_before=behavior_before,
                behavior_after=behavior_after,
                evidence_ids=("evidence_diff_1",),
            ),
            context(),
        )
        return service, repository, fake_git, approvals, events, review

    def test_read_permission_alone_cannot_create_review(self) -> None:
        service, _, _, _, _ = make_service()
        denied = context("user_viewer").model_copy(
            update={"permissions": frozenset({"review:read"})}
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.create_review(
                CreateReviewCommand(
                    project_id="project_home",
                    repository_id="repository_home",
                    title="不应创建",
                    base_commit=BASE,
                    target_commit=TARGET,
                ),
                denied,
            )
        self.assertEqual(raised.exception.code, ErrorCode.PERMISSION_DENIED)

    def test_review_creation_seals_four_layers_and_emits_activity(self) -> None:
        service, repository, _, _, events, review = self._create_review()

        self.assertEqual(review.diff.base_version.commit_id, BASE)
        self.assertEqual(review.diff.target_version.commit_id, TARGET)
        self.assertEqual(review.diff.semantic.changes[0].path, "/locked")
        self.assertEqual(review.diff.visual.changed_samples, 2)
        self.assertEqual(len(review.diff.behavior.changes), 3)
        self.assertEqual(review.mode, ExecutionMode.MOCK)
        self.assertEqual(len(repository.list_activity(review.review_id)), 1)
        self.assertEqual(events.events[0].event_type, "review.session.created")
        self.assertIsNotNone(service.get_review(review.review_id))

    def test_review_revision_publish_preserves_the_pinned_predecessor(self) -> None:
        service, _, _, _, events, first = self._create_review()
        second = service.create_review(
            CreateReviewCommand(
                review_id=first.review_id,
                expected_previous_revision_id=first.review_revision_id,
                project_id="project_home",
                repository_id="repository_home",
                title="钥匙开门分支评审 · 第二版",
                base_commit=BASE,
                target_commit=TARGET,
            ),
            context(),
        )

        self.assertEqual(second.review_id, first.review_id)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.previous_revision_id, first.review_revision_id)
        self.assertEqual(
            service.get_review_revision(first.review_id, first.review_revision_id),
            first,
        )
        self.assertEqual(service.get_review(first.review_id), second)
        self.assertEqual(events.events[-1].event_type, "review.revision.published")

        with self.assertRaises(VersionCollaborationError) as raised:
            service.create_review(
                CreateReviewCommand(
                    review_id=first.review_id,
                    expected_previous_revision_id=first.review_revision_id,
                    project_id="project_home",
                    repository_id="repository_home",
                    title="并发旧版发布",
                    base_commit=BASE,
                    target_commit=TARGET,
                ),
                context(),
            )
        self.assertEqual(raised.exception.code, ErrorCode.STALE_BASE)

    def test_dirty_and_conflicted_worktree_are_structured_states(self) -> None:
        _, _, _, _, _, review = self._create_review(
            git=FakeGitAdapter(dirty=True, conflicted=True)
        )

        codes = {conflict.code for conflict in review.diff.conflicts}
        self.assertIn(ConflictCode.DIRTY_WORKTREE, codes)
        self.assertIn(ConflictCode.MERGE_CONFLICT, codes)
        self.assertTrue(review.diff.has_blocking_conflicts)

    def test_all_supported_comment_anchors_keep_version_and_object_identity(self) -> None:
        service, repository, _, _, _, review = self._create_review()
        kinds = tuple(CommentAnchorKind)

        for index, kind in enumerate(kinds, start=1):
            fields = {}
            if kind == CommentAnchorKind.CODE_RANGE:
                fields = {"file_path": "src/gameplay.ts", "start_line": 10, "end_line": 12}
            comment = service.add_comment(
                review.review_id,
                f"锚点评论 {kind.value}",
                CommentAnchor(
                    kind=kind,
                    review_revision_id=review.review_revision_id,
                    diff_bundle_id=review.diff.diff_bundle_id,
                    version=review.target_version,
                    target_id=f"target_{index}",
                    **fields,
                ),
                context("user_reviewer"),
            )
            self.assertEqual(comment.anchor.version.commit_id, TARGET)
            self.assertEqual(comment.anchor.target_id, f"target_{index}")

        self.assertEqual(len(repository.list_comments(review.review_id)), len(kinds))

    def test_comment_rejects_anchor_from_another_diff(self) -> None:
        service, _, _, _, _, review = self._create_review()
        anchor = CommentAnchor(
            kind="asset",
            review_revision_id=review.review_revision_id,
            diff_bundle_id="diff_other",
            version=review.target_version,
            target_id="asset_key",
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.add_comment(review.review_id, "错误锚点", anchor, context())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_COMMENT_ANCHOR)

    def test_backend_permission_check_cannot_be_bypassed_by_frontend(self) -> None:
        service, _, _, _, _, review = self._create_review()
        denied = context("user_viewer").model_copy(
            update={"permissions": frozenset({"review:read"})}
        )
        anchor = CommentAnchor(
            kind="asset",
            review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id,
            version=review.target_version,
            target_id="asset_key",
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.add_comment(review.review_id, "不应写入", anchor, denied)

        self.assertEqual(raised.exception.code, ErrorCode.PERMISSION_DENIED)

    def test_assignment_and_decision_are_append_only_activity(self) -> None:
        service, repository, _, _, _, review = self._create_review()

        service.record_assignment(
            review.review_id, "user_reviewer", AssignmentAction.ASSIGNED, context()
        )
        decision = service.record_decision(
            review.review_id,
            DecisionOutcome.REQUEST_CHANGES,
            "门锁语义仍需确认。",
            ("evidence_semantic_1",),
            context("user_reviewer"),
        )

        self.assertEqual(repository.list_assignments(review.review_id)[0].reviewer_id, "user_reviewer")
        self.assertEqual(repository.list_decisions(review.review_id), (decision,))
        self.assertEqual(service.summarize(review.review_id).status.value, "changes_requested")

    def test_approval_history_is_verified_and_stale_base_is_rejected(self) -> None:
        service, repository, _, verifier, _, review = self._create_review()

        first = service.observe_approval(
            review_id=review.review_id,
            approval_id="approval_first",
            subject_kind="review",
            subject_id=review.review_id,
            subject_version=review.revision,
            current_base=review.target_version,
            context=context("user_reviewer"),
        )
        second = service.observe_approval(
            review_id=review.review_id,
            approval_id="approval_second",
            subject_kind="review",
            subject_id=review.review_id,
            subject_version=review.revision,
            current_base=review.target_version,
            context=context("user_reviewer"),
        )
        self.assertEqual(repository.list_approvals(review.review_id), (first, second))
        self.assertEqual(len(verifier.bindings), 2)

        with self.assertRaises(VersionCollaborationError) as raised:
            service.observe_approval(
                review_id=review.review_id,
                approval_id="approval_stale",
                subject_kind="review",
                subject_id=review.review_id,
                subject_version=1,
                current_base=version(BASE),
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.STALE_BASE)

    def test_approval_rechecks_actual_git_head_and_exact_review_subject(self) -> None:
        service, _, git, _, _, review = self._create_review()
        git.head = "3" * 40

        with self.assertRaises(VersionCollaborationError) as raised:
            service.observe_approval(
                review_id=review.review_id,
                approval_id="approval_moved_head",
                subject_kind="review",
                subject_id=review.review_id,
                subject_version=review.revision,
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.STALE_BASE)

        git.head = TARGET
        with self.assertRaises(VersionCollaborationError) as raised:
            service.observe_approval(
                review_id=review.review_id,
                approval_id="approval_wrong_subject",
                subject_kind="review",
                subject_id="review_other",
                subject_version=review.revision,
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_STATE)

    def test_blocking_review_conflict_prevents_approval(self) -> None:
        service, _, _, _, _, review = self._create_review(
            git=FakeGitAdapter(dirty=True, conflicted=True)
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.observe_approval(
                review_id=review.review_id,
                approval_id="approval_conflicted",
                subject_kind="review",
                subject_id=review.review_id,
                subject_version=review.revision,
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_STATE)
        self.assertIn("merge_conflict", raised.exception.details["conflict_codes"])

    def test_binary_asset_lock_uses_lfs_adapter_and_enforces_owner(self) -> None:
        service, repository, _, _, _, review = self._create_review()

        lock = service.acquire_asset_lock(
            review_id=review.review_id,
            project_id="project_home",
            repository_id="repository_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            context=context("user_artist"),
        )
        self.assertEqual(lock.mode, ExecutionMode.MOCK)
        self.assertEqual(repository.get_active_lock("project_home", "asset_key"), lock)

        with self.assertRaises(VersionCollaborationError) as raised:
            service.release_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                resource_id="asset_key",
                context=context("user_other"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.LOCK_OWNERSHIP)

        released = service.release_asset_lock(
            review_id=review.review_id,
            project_id="project_home",
            resource_id="asset_key",
            context=context("user_artist"),
        )
        self.assertEqual(released.action.value, "released")
        self.assertIsNone(repository.get_active_lock("project_home", "asset_key"))

    def test_existing_lock_must_match_path_and_remote_lfs_state(self) -> None:
        service, _, git, _, _, review = self._create_review()
        held = service.acquire_asset_lock(
            review_id=review.review_id,
            project_id="project_home",
            repository_id="repository_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            context=context("user_artist"),
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.acquire_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                repository_id="repository_home",
                resource_id="asset_key",
                path="Assets/Home/Other.glb",
                context=context("user_artist"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.LOCK_CONFLICT)

        git.locked.pop(held.external_lock_id)
        with self.assertRaises(VersionCollaborationError) as raised:
            service.acquire_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                repository_id="repository_home",
                resource_id="asset_key",
                path="Assets/Home/Key.glb",
                context=context("user_artist"),
            )
        self.assertEqual(
            raised.exception.code, ErrorCode.LOCK_RECONCILIATION_REQUIRED
        )

    def test_release_revalidates_remote_lock_before_unlocking_by_id(self) -> None:
        service, _, git, _, _, review = self._create_review()
        held = service.acquire_asset_lock(
            review_id=review.review_id,
            project_id="project_home",
            repository_id="repository_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            context=context("user_artist"),
        )
        git.locked[held.external_lock_id] = git.locked[
            held.external_lock_id
        ].model_copy(update={"path": "Assets/Home/Other.glb"})

        with self.assertRaises(VersionCollaborationError) as raised:
            service.release_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                resource_id="asset_key",
                context=context("user_artist"),
            )

        self.assertEqual(
            raised.exception.code, ErrorCode.LOCK_RECONCILIATION_REQUIRED
        )
        self.assertIn(held.external_lock_id, git.locked)

    def test_binary_file_without_lock_is_a_blocking_review_conflict(self) -> None:
        git = FakeGitAdapter()
        git.compare_versions = lambda repository_id, project_root, base, target: git_diff(
            base, target, binary=True
        )

        _, _, _, _, _, review = self._create_review(git=git)

        self.assertIn(
            ConflictCode.LOCKED_BINARY_ASSET,
            {conflict.code for conflict in review.diff.conflicts},
        )

    def test_binary_approval_revalidates_the_remote_lfs_lock(self) -> None:
        service, _, git, _, _, bootstrap = self._create_review()
        held = service.acquire_asset_lock(
            review_id=bootstrap.review_id,
            project_id="project_home",
            repository_id="repository_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            context=context(),
        )
        git.compare_versions = lambda repository_id, project_root, base, target: git_diff(
            base, target, binary=True
        )
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="二进制锁复核",
                base_commit=BASE,
                target_commit=TARGET,
            ),
            context(),
        )
        self.assertFalse(review.diff.has_blocking_conflicts)

        git.locked.pop(held.external_lock_id)
        with self.assertRaises(VersionCollaborationError) as raised:
            service.observe_approval(
                review_id=review.review_id,
                approval_id="approval_binary_review",
                subject_kind="review",
                subject_id=review.review_id,
                subject_version=review.revision,
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(
            raised.exception.code, ErrorCode.LOCK_RECONCILIATION_REQUIRED
        )

    def test_failed_local_lock_write_compensates_remote_lfs_lock(self) -> None:
        class FailingAcquireRepository(SqliteReviewRepository):
            def acquire_lock(self, record):
                raise RuntimeError("fixture database failure")

        repository = FailingAcquireRepository()
        service, _, git, _, _ = make_service(repository=repository)
        semantic_before, semantic_after = semantic_pair()
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="锁补偿评审",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
            ),
            context(),
        )

        with self.assertRaises(RuntimeError):
            service.acquire_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                repository_id="repository_home",
                resource_id="asset_key",
                path="Assets/Home/Key.glb",
                context=context("user_artist"),
            )
        self.assertEqual(git.locked, {})

    def test_failed_local_unlock_reacquires_and_reconciles_remote_lock(self) -> None:
        class FailingReleaseRepository(SqliteReviewRepository):
            def release_lock(self, record):
                raise RuntimeError("fixture database failure")

        repository = FailingReleaseRepository()
        service, _, git, _, _ = make_service(repository=repository)
        semantic_before, semantic_after = semantic_pair()
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="解锁补偿评审",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
            ),
            context(),
        )
        held = service.acquire_asset_lock(
            review_id=review.review_id,
            project_id="project_home",
            repository_id="repository_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            context=context("user_artist"),
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.release_asset_lock(
                review_id=review.review_id,
                project_id="project_home",
                resource_id="asset_key",
                context=context("user_artist"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_STATE)
        reconciled = repository.get_active_lock("project_home", "asset_key")
        self.assertIsNotNone(reconciled)
        self.assertNotEqual(reconciled.external_lock_id, held.external_lock_id)
        self.assertIn(reconciled.external_lock_id, git.locked)

    def test_rollback_requires_changeset_and_exact_approval_then_is_idempotent(self) -> None:
        service, repository, git, verifier, _, review = self._create_review()
        proposal = service.propose_rollback(
            review_id=review.review_id,
            target_commit=BASE,
            current_base=review.target_version,
            rationale="恢复已验证的门锁状态。",
            context=context("user_reviewer"),
        )

        self.assertEqual(proposal.change_set_id, "changeset_rollback_1")
        self.assertEqual(proposal.mode, ExecutionMode.MOCK)
        self.assertIn("review:approve", proposal.approval_requirements)

        execution = service.execute_rollback(
            proposal_id=proposal.proposal_id,
            approval_id="approval_rollback",
            current_base=review.target_version,
            context=context("user_reviewer"),
        )
        repeated = service.execute_rollback(
            proposal_id=proposal.proposal_id,
            approval_id="approval_rollback",
            current_base=review.target_version,
            context=context("user_reviewer"),
        )

        self.assertEqual(execution, repeated)
        self.assertEqual(git.rollback_calls, 1)
        self.assertEqual(execution.result.previous_head, TARGET)
        self.assertNotEqual(execution.result.resulting_head, TARGET)
        self.assertEqual(len(repository.list_changeset_history(proposal.change_set_id)), 2)
        self.assertEqual(verifier.bindings[-1].subject_kind, "rollback")

        with self.assertRaises(VersionCollaborationError) as raised:
            service.execute_rollback(
                proposal_id=proposal.proposal_id,
                approval_id="approval_different",
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.DUPLICATE_RECORD)

    def test_rollback_proposal_cannot_cross_a_review_revision(self) -> None:
        service, _, git, _, _, first = self._create_review()
        proposal = service.propose_rollback(
            review_id=first.review_id,
            target_commit=BASE,
            current_base=first.target_version,
            rationale="旧 revision 的回滚计划。",
            context=context("user_reviewer"),
        )
        service.create_review(
            CreateReviewCommand(
                review_id=first.review_id,
                expected_previous_revision_id=first.review_revision_id,
                project_id="project_home",
                repository_id="repository_home",
                title="已前进的评审 revision",
                base_commit=BASE,
                target_commit=TARGET,
            ),
            context(),
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.execute_rollback(
                proposal_id=proposal.proposal_id,
                approval_id="approval_old_revision",
                current_base=first.target_version,
                context=context("user_reviewer"),
            )

        self.assertEqual(raised.exception.code, ErrorCode.STALE_BASE)
        self.assertEqual(git.rollback_calls, 0)

    def test_noop_rollback_is_rejected_before_creating_changeset(self) -> None:
        service, _, git, _, _, review = self._create_review()
        original_dry_run = git.dry_run_rollback
        git.dry_run_rollback = lambda root, command: original_dry_run(
            root, command
        ).model_copy(update={"changes": ()})

        with self.assertRaises(VersionCollaborationError) as raised:
            service.propose_rollback(
                review_id=review.review_id,
                target_commit=BASE,
                current_base=review.target_version,
                rationale="不应创建空回滚。",
                context=context("user_reviewer"),
            )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_STATE)

    def test_rollback_approval_without_evidence_is_blocked(self) -> None:
        verifier = FakeApprovalVerifier(evidence_ids=())
        service, _, _, _, _ = make_service(approvals=verifier)
        semantic_before, semantic_after = semantic_pair()
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="回滚证据检查",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
            ),
            context=context(),
        )
        proposal = service.propose_rollback(
            review_id=review.review_id,
            target_commit=BASE,
            current_base=review.target_version,
            rationale="测试无证据审批。",
            context=context(),
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.execute_rollback(
                proposal_id=proposal.proposal_id,
                approval_id="approval_no_evidence",
                current_base=review.target_version,
                context=context("user_reviewer"),
            )
        self.assertEqual(raised.exception.code, ErrorCode.EVIDENCE_REQUIRED)

    def test_missing_core_changeset_service_is_explicitly_blocked(self) -> None:
        service, _, git, _, _ = make_service(
            change_sets=UnavailableChangeSetGateway()
        )
        semantic_before, semantic_after = semantic_pair()
        review = service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="缺少核心合同",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
            ),
            context(),
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            service.propose_rollback(
                review_id=review.review_id,
                target_commit=BASE,
                current_base=review.target_version,
                rationale="验证 blocked 状态。",
                context=context(),
            )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_STATE)
        self.assertEqual(raised.exception.details["mode"], "blocked")
        self.assertEqual(git.rollback_calls, 0)

    def test_approved_change_links_evidence_to_release(self) -> None:
        service, repository, _, _, _, review = self._create_review()
        approval = service.observe_approval(
            review_id=review.review_id,
            approval_id="approval_review",
            subject_kind="review",
            subject_id=review.review_id,
            subject_version=1,
            current_base=review.target_version,
            context=context("user_reviewer"),
        )

        link = service.link_release(
            review_id=review.review_id,
            approval_id=approval.approval_id,
            approved_subject_id=review.review_id,
            approved_subject_version=1,
            release_id="release_candidate_1",
            evidence_ids=("evidence_regression_1",),
            context=context("user_release_owner"),
        )
        repeated = service.link_release(
            review_id=review.review_id,
            approval_id=approval.approval_id,
            approved_subject_id=review.review_id,
            approved_subject_version=1,
            release_id="release_candidate_1",
            evidence_ids=("evidence_regression_1",),
            context=context("user_release_owner"),
        )

        self.assertEqual(link.release_id, "release_candidate_1")
        self.assertEqual(repeated, link)
        self.assertEqual(
            set(link.evidence_ids), {"evidence_review_1", "evidence_regression_1"}
        )
        self.assertEqual(repository.list_release_links(review.review_id), (link,))


if __name__ == "__main__":
    unittest.main()
