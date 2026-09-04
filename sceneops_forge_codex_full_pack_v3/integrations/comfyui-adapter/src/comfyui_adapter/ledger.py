"""Atomic enqueue idempotency ledgers for ComfyUI command delivery."""

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Dict, Literal, Optional, Protocol, Tuple

from .models import ComfyEnqueueCommand, EnqueueResult


LedgerState = Literal["claimed", "uncertain", "succeeded"]


@dataclass(frozen=True)
class EnqueueClaim:
    created: bool
    state: LedgerState
    result: Optional[EnqueueResult]


class EnqueueLedgerConflict(ValueError):
    pass


class EnqueueLedger(Protocol):
    @property
    def durable(self) -> bool:
        ...

    def claim(self, command: ComfyEnqueueCommand) -> EnqueueClaim:
        """Atomically claim a request ID or return its existing state."""
        ...

    def mark_uncertain(self, request_id: str) -> None:
        ...

    def mark_succeeded(self, request_id: str, result: EnqueueResult) -> None:
        ...


def _command_json(command: ComfyEnqueueCommand) -> str:
    return json.dumps(
        command.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


class InMemoryEnqueueLedger:
    """Thread-safe, process-local ledger intended for tests and local mocks."""

    durable = False

    def __init__(self) -> None:
        self._entries: Dict[str, Tuple[str, LedgerState, Optional[EnqueueResult]]] = {}
        self._lock = RLock()

    def claim(self, command: ComfyEnqueueCommand) -> EnqueueClaim:
        payload = _command_json(command)
        with self._lock:
            existing = self._entries.get(command.request_id)
            if existing is None:
                self._entries[command.request_id] = (payload, "claimed", None)
                return EnqueueClaim(created=True, state="claimed", result=None)
            prior_payload, state, result = existing
            if prior_payload != payload:
                raise EnqueueLedgerConflict("request ID was reused for different inputs")
            return EnqueueClaim(created=False, state=state, result=result)

    def mark_uncertain(self, request_id: str) -> None:
        with self._lock:
            payload, _state, result = self._entries[request_id]
            self._entries[request_id] = (payload, "uncertain", result)

    def mark_succeeded(self, request_id: str, result: EnqueueResult) -> None:
        with self._lock:
            payload, _state, _result = self._entries[request_id]
            self._entries[request_id] = (payload, "succeeded", result)


class SQLiteEnqueueLedger:
    """Durable, cross-process ledger backed by SQLite transactions."""

    durable = True

    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS comfy_enqueue_ledger (
                    request_id TEXT PRIMARY KEY,
                    command_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('claimed', 'uncertain', 'succeeded')),
                    result_json TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._path), timeout=30.0)

    def claim(self, command: ComfyEnqueueCommand) -> EnqueueClaim:
        payload = _command_json(command)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO comfy_enqueue_ledger
                    (request_id, command_json, state, result_json)
                VALUES (?, ?, 'claimed', NULL)
                """,
                (command.request_id, payload),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                """
                SELECT command_json, state, result_json
                FROM comfy_enqueue_ledger WHERE request_id = ?
                """,
                (command.request_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("enqueue ledger claim was not persisted")
        prior_payload, state, result_json = row
        if prior_payload != payload:
            raise EnqueueLedgerConflict("request ID was reused for different inputs")
        result = EnqueueResult.model_validate_json(result_json) if result_json else None
        return EnqueueClaim(created=created, state=state, result=result)

    def mark_uncertain(self, request_id: str) -> None:
        self._update(request_id, "uncertain", None)

    def mark_succeeded(self, request_id: str, result: EnqueueResult) -> None:
        self._update(request_id, "succeeded", result.model_dump_json())

    def _update(
        self, request_id: str, state: LedgerState, result_json: Optional[str]
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE comfy_enqueue_ledger
                SET state = ?, result_json = COALESCE(?, result_json)
                WHERE request_id = ?
                """,
                (state, result_json, request_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("unknown enqueue request ID: " + request_id)
