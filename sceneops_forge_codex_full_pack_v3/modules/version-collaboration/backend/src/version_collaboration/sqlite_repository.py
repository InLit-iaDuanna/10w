from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator, TypeVar

from pydantic import BaseModel

from .errors import ErrorCode, VersionCollaborationError
from .review_models import (
    ActivityRecord,
    ApprovalObservation,
    AssetLockRecord,
    AssignmentRecord,
    ChangeSetHistoryEntry,
    DecisionRecord,
    ReleaseEvidenceLink,
    ReviewComment,
    ReviewSession,
    RollbackExecution,
    RollbackProposal,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


class SqliteReviewRepository:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(database), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def append_review(
        self,
        review: ReviewSession,
        expected_previous_revision_id: str | None = None,
    ) -> None:
        with self._transaction() as cursor:
            latest = cursor.execute(
                "SELECT review_revision_id, revision FROM review_revisions "
                "WHERE review_id = ? ORDER BY revision DESC LIMIT 1",
                (review.review_id,),
            ).fetchone()
            actual_previous = (
                str(latest["review_revision_id"]) if latest is not None else None
            )
            actual_revision = int(latest["revision"]) if latest is not None else 0
            if (
                actual_previous != expected_previous_revision_id
                or review.revision != actual_revision + 1
                or review.previous_revision_id != expected_previous_revision_id
            ):
                raise VersionCollaborationError(
                    ErrorCode.STALE_BASE,
                    "The review session advanced before this immutable revision was published.",
                    details={
                        "review_id": review.review_id,
                        "expected_previous_revision_id": expected_previous_revision_id,
                        "actual_previous_revision_id": actual_previous,
                    },
                )
            try:
                cursor.execute(
                    "INSERT INTO review_revisions"
                    "(review_revision_id, review_id, revision, payload) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        review.review_revision_id,
                        review.review_id,
                        review.revision,
                        review.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise VersionCollaborationError(
                    ErrorCode.DUPLICATE_RECORD,
                    "An immutable review revision with this identity already exists.",
                    details={"review_revision_id": review.review_revision_id},
                ) from error

    def get_review(self, review_id: str) -> ReviewSession:
        row = self._fetch_one(
            "SELECT payload FROM review_revisions WHERE review_id = ? ORDER BY revision DESC LIMIT 1",
            (review_id,),
        )
        return self._required_model(row, ReviewSession, "review", review_id)

    def get_review_revision(self, review_revision_id: str) -> ReviewSession:
        row = self._fetch_one(
            "SELECT payload FROM review_revisions WHERE review_revision_id = ?",
            (review_revision_id,),
        )
        return self._required_model(row, ReviewSession, "review revision", review_revision_id)

    @contextmanager
    def guard_review_revision(
        self, review_id: str, review_revision_id: str
    ) -> Iterator[None]:
        with self._transaction() as cursor:
            latest = cursor.execute(
                "SELECT review_revision_id FROM review_revisions "
                "WHERE review_id = ? ORDER BY revision DESC LIMIT 1",
                (review_id,),
            ).fetchone()
            actual = (
                str(latest["review_revision_id"]) if latest is not None else None
            )
            if actual != review_revision_id:
                raise VersionCollaborationError(
                    ErrorCode.STALE_BASE,
                    "The review session advanced before the mutation boundary.",
                    details={
                        "review_id": review_id,
                        "expected_review_revision_id": review_revision_id,
                        "actual_review_revision_id": actual,
                    },
                )
            yield

    def append_comment(self, comment: ReviewComment) -> None:
        self._append_audit("comments", "comment_id", comment.comment_id, comment.review_id, comment)

    def list_comments(self, review_id: str) -> tuple[ReviewComment, ...]:
        return self._list_audit("comments", review_id, ReviewComment)

    def append_assignment(self, assignment: AssignmentRecord) -> None:
        self._append_audit(
            "assignments", "assignment_id", assignment.assignment_id, assignment.review_id, assignment
        )

    def list_assignments(self, review_id: str) -> tuple[AssignmentRecord, ...]:
        return self._list_audit("assignments", review_id, AssignmentRecord)

    def append_decision(self, decision: DecisionRecord) -> None:
        self._append_audit("decisions", "decision_id", decision.decision_id, decision.review_id, decision)

    def list_decisions(self, review_id: str) -> tuple[DecisionRecord, ...]:
        return self._list_audit("decisions", review_id, DecisionRecord)

    def append_approval(self, approval: ApprovalObservation) -> None:
        self._append_audit(
            "approvals", "approval_id", approval.approval_id, approval.review_id, approval
        )

    def list_approvals(self, review_id: str) -> tuple[ApprovalObservation, ...]:
        return self._list_audit("approvals", review_id, ApprovalObservation)

    def get_approval(self, approval_id: str) -> ApprovalObservation:
        row = self._fetch_one("SELECT payload FROM approvals WHERE approval_id = ?", (approval_id,))
        return self._required_model(row, ApprovalObservation, "approval", approval_id)

    def acquire_lock(self, record: AssetLockRecord) -> None:
        with self._transaction() as cursor:
            active = cursor.execute(
                "SELECT payload FROM active_locks WHERE project_id = ? AND resource_id = ?",
                (record.project_id, record.resource_id),
            ).fetchone()
            if active is not None:
                held = AssetLockRecord.model_validate_json(active["payload"])
                raise VersionCollaborationError(
                    ErrorCode.LOCK_CONFLICT,
                    "The binary asset is already locked.",
                    details={"resource_id": record.resource_id, "owner_id": held.owner_id},
                )
            self._insert_lock_record(cursor, record)
            cursor.execute(
                "INSERT INTO active_locks(project_id, resource_id, lock_id, payload) VALUES (?, ?, ?, ?)",
                (record.project_id, record.resource_id, record.lock_id, record.model_dump_json()),
            )

    def release_lock(self, record: AssetLockRecord) -> None:
        with self._transaction() as cursor:
            active = cursor.execute(
                "SELECT payload FROM active_locks WHERE project_id = ? AND resource_id = ?",
                (record.project_id, record.resource_id),
            ).fetchone()
            if active is None:
                raise VersionCollaborationError(
                    ErrorCode.NOT_FOUND,
                    "No active lock exists for this binary asset.",
                    details={"resource_id": record.resource_id},
                )
            held = AssetLockRecord.model_validate_json(active["payload"])
            if held.lock_id != record.lock_id or held.owner_id != record.owner_id:
                raise VersionCollaborationError(
                    ErrorCode.LOCK_OWNERSHIP,
                    "Only the lock owner can release this lock.",
                    details={"resource_id": record.resource_id, "owner_id": held.owner_id},
                )
            self._insert_lock_record(cursor, record)
            cursor.execute(
                "DELETE FROM active_locks WHERE project_id = ? AND resource_id = ?",
                (record.project_id, record.resource_id),
            )

    def replace_active_lock(self, record: AssetLockRecord) -> None:
        with self._transaction() as cursor:
            active = cursor.execute(
                "SELECT payload FROM active_locks WHERE project_id = ? AND resource_id = ?",
                (record.project_id, record.resource_id),
            ).fetchone()
            if active is None:
                raise VersionCollaborationError(
                    ErrorCode.NOT_FOUND,
                    "No active lock exists to reconcile.",
                    details={"resource_id": record.resource_id},
                )
            held = AssetLockRecord.model_validate_json(active["payload"])
            if (
                held.lock_id != record.lock_id
                or held.owner_id != record.owner_id
                or held.path != record.path
            ):
                raise VersionCollaborationError(
                    ErrorCode.LOCK_OWNERSHIP,
                    "The active lock changed before reconciliation.",
                    details={"resource_id": record.resource_id},
                )
            self._insert_lock_record(cursor, record)
            cursor.execute(
                "UPDATE active_locks SET lock_id = ?, payload = ? WHERE project_id = ? AND resource_id = ?",
                (
                    record.lock_id,
                    record.model_dump_json(),
                    record.project_id,
                    record.resource_id,
                ),
            )

    def get_active_lock(self, project_id: str, resource_id: str) -> AssetLockRecord | None:
        row = self._fetch_one(
            "SELECT payload FROM active_locks WHERE project_id = ? AND resource_id = ?",
            (project_id, resource_id),
        )
        return AssetLockRecord.model_validate_json(row["payload"]) if row else None

    def list_active_locks(self, project_id: str) -> tuple[AssetLockRecord, ...]:
        rows = self._fetch_all(
            "SELECT payload FROM active_locks WHERE project_id = ? ORDER BY resource_id", (project_id,)
        )
        return tuple(AssetLockRecord.model_validate_json(row["payload"]) for row in rows)

    def list_lock_records(self, project_id: str) -> tuple[AssetLockRecord, ...]:
        rows = self._fetch_all(
            "SELECT payload FROM lock_records WHERE project_id = ? ORDER BY rowid",
            (project_id,),
        )
        return tuple(
            AssetLockRecord.model_validate_json(row["payload"]) for row in rows
        )

    def append_changeset_history(self, entry: ChangeSetHistoryEntry) -> None:
        self._insert(
            "changeset_history",
            ("history_id", "change_set_id", "revision", "payload"),
            (entry.history_id, entry.change_set_id, entry.revision, entry.model_dump_json()),
        )

    def list_changeset_history(self, change_set_id: str) -> tuple[ChangeSetHistoryEntry, ...]:
        rows = self._fetch_all(
            "SELECT payload FROM changeset_history WHERE change_set_id = ? ORDER BY revision",
            (change_set_id,),
        )
        return tuple(ChangeSetHistoryEntry.model_validate_json(row["payload"]) for row in rows)

    def append_activity(self, activity: ActivityRecord) -> None:
        self._append_audit(
            "activities", "activity_id", activity.activity_id, activity.review_id, activity
        )

    def list_activity(self, review_id: str) -> tuple[ActivityRecord, ...]:
        return self._list_audit("activities", review_id, ActivityRecord)

    def append_rollback_proposal(self, proposal: RollbackProposal) -> None:
        self._insert(
            "rollback_proposals",
            ("proposal_id", "review_id", "payload"),
            (proposal.proposal_id, proposal.review_id, proposal.model_dump_json()),
        )

    def get_rollback_proposal(self, proposal_id: str) -> RollbackProposal:
        row = self._fetch_one(
            "SELECT payload FROM rollback_proposals WHERE proposal_id = ?", (proposal_id,)
        )
        return self._required_model(row, RollbackProposal, "rollback proposal", proposal_id)

    def append_rollback_execution(self, execution: RollbackExecution) -> None:
        self._insert(
            "rollback_executions",
            ("execution_id", "proposal_id", "review_id", "payload"),
            (
                execution.execution_id,
                execution.proposal_id,
                execution.review_id,
                execution.model_dump_json(),
            ),
        )

    def get_rollback_execution(self, proposal_id: str) -> RollbackExecution | None:
        row = self._fetch_one(
            "SELECT payload FROM rollback_executions WHERE proposal_id = ?", (proposal_id,)
        )
        return RollbackExecution.model_validate_json(row["payload"]) if row else None

    def append_release_link(self, link: ReleaseEvidenceLink) -> None:
        self._insert(
            "release_links",
            ("link_id", "review_id", "approved_subject_id", "release_id", "payload"),
            (
                link.link_id,
                link.review_id,
                link.approved_subject_id,
                link.release_id,
                link.model_dump_json(),
            ),
        )

    def list_release_links(self, review_id: str) -> tuple[ReleaseEvidenceLink, ...]:
        rows = self._fetch_all(
            "SELECT payload FROM release_links WHERE review_id = ? ORDER BY rowid", (review_id,)
        )
        return tuple(ReleaseEvidenceLink.model_validate_json(row["payload"]) for row in rows)

    def _create_schema(self) -> None:
        statements = (
            "CREATE TABLE IF NOT EXISTS review_revisions (review_revision_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(review_id, revision))",
            "CREATE TABLE IF NOT EXISTS comments (comment_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS assignments (assignment_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS decisions (decision_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS approvals (approval_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS lock_records (lock_record_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, resource_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS active_locks (project_id TEXT NOT NULL, resource_id TEXT NOT NULL, lock_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(project_id, resource_id))",
            "CREATE TABLE IF NOT EXISTS changeset_history (history_id TEXT PRIMARY KEY, change_set_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(change_set_id, revision))",
            "CREATE TABLE IF NOT EXISTS activities (activity_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rollback_proposals (proposal_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rollback_executions (execution_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE, review_id TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS release_links (link_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, approved_subject_id TEXT NOT NULL, release_id TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(approved_subject_id, release_id))",
        )
        with self._transaction() as cursor:
            for statement in statements:
                cursor.execute(statement)

    def _append_audit(
        self, table: str, id_column: str, record_id: str, review_id: str, model: BaseModel
    ) -> None:
        self._insert(table, (id_column, "review_id", "payload"), (record_id, review_id, model.model_dump_json()))

    def _list_audit(self, table: str, review_id: str, model: type[ModelT]) -> tuple[ModelT, ...]:
        rows = self._fetch_all(
            f"SELECT payload FROM {table} WHERE review_id = ? ORDER BY rowid", (review_id,)
        )
        return tuple(model.model_validate_json(row["payload"]) for row in rows)

    def _insert(self, table: str, columns: tuple[str, ...], values: tuple[object, ...]) -> None:
        placeholders = ", ".join("?" for _ in values)
        with self._transaction() as cursor:
            try:
                cursor.execute(
                    f"INSERT INTO {table}({', '.join(columns)}) VALUES ({placeholders})", values
                )
            except sqlite3.IntegrityError as error:
                raise VersionCollaborationError(
                    ErrorCode.DUPLICATE_RECORD,
                    "An immutable audit record with this identity already exists.",
                    details={"table": table},
                ) from error

    def _insert_lock_record(self, cursor: sqlite3.Cursor, record: AssetLockRecord) -> None:
        try:
            cursor.execute(
                "INSERT INTO lock_records(lock_record_id, project_id, resource_id, payload) VALUES (?, ?, ?, ?)",
                (
                    record.lock_record_id,
                    record.project_id,
                    record.resource_id,
                    record.model_dump_json(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise VersionCollaborationError(
                ErrorCode.DUPLICATE_RECORD,
                "This immutable lock event already exists.",
                details={"lock_record_id": record.lock_record_id},
            ) from error

    def _required_model(
        self, row: sqlite3.Row | None, model: type[ModelT], kind: str, identity: str
    ) -> ModelT:
        if row is None:
            raise VersionCollaborationError(
                ErrorCode.NOT_FOUND,
                f"The requested {kind} does not exist.",
                details={"id": identity},
            )
        return model.model_validate_json(row["payload"])

    def _fetch_one(self, query: str, parameters: tuple[object, ...]) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(query, parameters).fetchone()

    def _fetch_all(self, query: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._connection.execute(query, parameters).fetchall())

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._connection.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                yield cursor
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cursor.close()
