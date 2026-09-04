from __future__ import annotations

import unittest

from version_collaboration.errors import ErrorCode, VersionCollaborationError
from version_collaboration.review_models import (
    ApprovalObservation,
    ApprovalOutcome,
    AssetLockRecord,
    LockAction,
)
from version_collaboration.sqlite_repository import SqliteReviewRepository

from support import NOW, context, version


class SqliteReviewRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqliteReviewRepository()

    def tearDown(self) -> None:
        self.repository.close()

    def test_approval_history_is_append_only(self) -> None:
        first = self._approval("approval_first", ApprovalOutcome.APPROVED)
        second = self._approval("approval_second", ApprovalOutcome.REJECTED)

        self.repository.append_approval(first)
        self.repository.append_approval(second)

        self.assertEqual(self.repository.list_approvals("review_1"), (first, second))
        with self.assertRaises(VersionCollaborationError) as raised:
            self.repository.append_approval(first.model_copy(update={"outcome": ApprovalOutcome.REJECTED}))
        self.assertEqual(raised.exception.code, ErrorCode.DUPLICATE_RECORD)
        self.assertEqual(self.repository.list_approvals("review_1")[0].outcome, ApprovalOutcome.APPROVED)

    def test_asset_lock_has_one_active_owner_and_keeps_release_history(self) -> None:
        acquired = self._lock("lockevent_acquired", "user_owner", LockAction.ACQUIRED)
        competing = self._lock("lockevent_competing", "user_other", LockAction.ACQUIRED)

        self.repository.acquire_lock(acquired)
        with self.assertRaises(VersionCollaborationError) as raised:
            self.repository.acquire_lock(competing)
        self.assertEqual(raised.exception.code, ErrorCode.LOCK_CONFLICT)

        released = acquired.model_copy(
            update={"lock_record_id": "lockevent_released", "action": LockAction.RELEASED}
        )
        self.repository.release_lock(released)
        self.assertIsNone(self.repository.get_active_lock("project_home", "asset_key"))

    def test_non_owner_cannot_release_asset_lock(self) -> None:
        acquired = self._lock("lockevent_acquired", "user_owner", LockAction.ACQUIRED)
        self.repository.acquire_lock(acquired)
        release = acquired.model_copy(
            update={
                "lock_record_id": "lockevent_release",
                "owner_id": "user_other",
                "action": LockAction.RELEASED,
            }
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            self.repository.release_lock(release)

        self.assertEqual(raised.exception.code, ErrorCode.LOCK_OWNERSHIP)

    def _approval(self, approval_id: str, outcome: ApprovalOutcome) -> ApprovalObservation:
        return ApprovalObservation(
            approval_id=approval_id,
            review_id="review_1",
            review_revision_id="reviewrev_1",
            diff_bundle_id="diff_1",
            subject_kind="review",
            subject_id="review_1",
            subject_version=1,
            approver_id="user_reviewer",
            outcome=outcome,
            rationale="Immutable history test.",
            base_version=version(),
            evidence_ids=("evidence_1",),
            created_at=NOW,
            mode="mock",
        )

    def _lock(self, record_id: str, owner: str, action: LockAction) -> AssetLockRecord:
        return AssetLockRecord(
            lock_record_id=record_id,
            lock_id="lock_key",
            external_lock_id="external-1",
            project_id="project_home",
            resource_id="asset_key",
            path="Assets/Home/Key.glb",
            branch="feature/key-door",
            owner_id=owner,
            action=action,
            base_version=version(),
            created_at=NOW,
            mode="mock",
        )


if __name__ == "__main__":
    unittest.main()
