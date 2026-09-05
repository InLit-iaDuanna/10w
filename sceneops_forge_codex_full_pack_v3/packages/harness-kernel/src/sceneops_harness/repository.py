"""SQLite run records and append-only events in one transaction, namespaced tables."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from .contracts import utc_now
from .registry import HarnessError
from .run_contracts import HarnessEvent, PipelineRun


class RunRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            raise HarnessError("DURABLE_DATABASE_REQUIRED", "Harness requires a file-backed database")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS harness_runs (
                    project_id TEXT NOT NULL, id TEXT NOT NULL, request_id TEXT NOT NULL,
                    body TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, id), UNIQUE(project_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS harness_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    step_id TEXT, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS harness_events_run
                    ON harness_events(project_id, run_id, sequence);
                CREATE TABLE IF NOT EXISTS harness_resource_locks (
                    resource_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, invocation_id TEXT NOT NULL, owner_pid INTEGER NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.database_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _read(self, conn, project_id: str, run_id: str) -> PipelineRun:
        row = conn.execute("SELECT body FROM harness_runs WHERE project_id=? AND id=?",
                           (project_id, run_id)).fetchone()
        if row is None:
            raise HarnessError("RUN_NOT_FOUND", "Run does not exist in this project")
        return PipelineRun.model_validate_json(row["body"])

    def get(self, project_id: str, run_id: str) -> PipelineRun:
        with self.connection() as conn:
            return self._read(conn, project_id, run_id)

    def list(self, project_id: str, limit: int = 50) -> list[PipelineRun]:
        with self.connection() as conn:
            rows = conn.execute("SELECT body FROM harness_runs WHERE project_id=? ORDER BY updated_at DESC LIMIT ?",
                                (project_id, max(1, min(limit, 200)))).fetchall()
            return [PipelineRun.model_validate_json(row["body"]) for row in rows]

    def create(self, run: PipelineRun) -> PipelineRun:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute("SELECT body FROM harness_runs WHERE project_id=? AND request_id=?",
                                 (run.project_id, run.request_id)).fetchone()
            if prior:
                existing = PipelineRun.model_validate_json(prior["body"])
                if existing.definition != run.definition or existing.submitted_by != run.submitted_by:
                    raise HarnessError("REQUEST_CONFLICT", "Request ID already belongs to a different submission")
                return existing
            conn.execute("INSERT INTO harness_runs VALUES (?,?,?,?,?)", (run.project_id, run.id,
                         run.request_id, run.model_dump_json(), run.updated_at.isoformat()))
            self._event(conn, run, "harness.run.submitted", None, {"state": run.state})
        return run

    def _event(self, conn, run, event_type, step_id, payload):
        conn.execute("INSERT INTO harness_events(project_id,run_id,event_type,occurred_at,step_id,payload) VALUES(?,?,?,?,?,?)",
                     (run.project_id, run.id, event_type, utc_now().isoformat(), step_id, json.dumps(payload)))

    def update(self, project_id: str, run_id: str, mutate: Callable[[PipelineRun], None],
               event_type: str, step_id: str | None = None, payload: dict | None = None) -> PipelineRun:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = self._read(conn, project_id, run_id)
            mutate(run)
            run.revision += 1
            run.updated_at = utc_now()
            conn.execute("UPDATE harness_runs SET body=?,updated_at=? WHERE project_id=? AND id=?",
                         (run.model_dump_json(), run.updated_at.isoformat(), project_id, run_id))
            self._event(conn, run, event_type, step_id, payload or {"state": run.state})
        return run

    def save_owned(self, run: PipelineRun, event_type: str, step_id: str | None = None) -> PipelineRun:
        def replace(current: PipelineRun):
            if current.owner_pid != os.getpid():
                raise HarnessError("RUN_OWNERSHIP_LOST", "The run no longer belongs to this worker")
            cancel_requested = current.cancel_requested
            for field in PipelineRun.model_fields:
                if field not in ("revision", "cancel_requested"):
                    setattr(current, field, getattr(run, field))
            current.cancel_requested = cancel_requested or run.cancel_requested
        return self.update(run.project_id, run.id, replace, event_type, step_id)

    def events(self, project_id: str, run_id: str, after: int = 0, limit: int = 200) -> list[HarnessEvent]:
        with self.connection() as conn:
            self._read(conn, project_id, run_id)
            rows = conn.execute("SELECT * FROM harness_events WHERE project_id=? AND run_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                                (project_id, run_id, after, max(1, min(limit, 1000)))).fetchall()
            return [HarnessEvent(**{**dict(row), "payload": json.loads(row["payload"])}) for row in rows]

    @contextmanager
    def resources(self, invocation, resource_ids: list[str]):
        """Connector locks serialize external local instances across API workers/projects."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for resource_id in sorted(set(resource_ids)):
                prior = conn.execute("SELECT owner_pid FROM harness_resource_locks WHERE resource_id=?", (resource_id,)).fetchone()
                if prior:
                    try:
                        os.kill(prior["owner_pid"], 0)
                    except ProcessLookupError:
                        conn.execute("DELETE FROM harness_resource_locks WHERE resource_id=?", (resource_id,))
                    except PermissionError:
                        raise HarnessError("CONNECTOR_BUSY", f"Connector {resource_id} is owned by another worker")
                    else:
                        raise HarnessError("CONNECTOR_BUSY", f"Connector {resource_id} is already executing")
                conn.execute("INSERT INTO harness_resource_locks VALUES(?,?,?,?,?)", (resource_id,
                    invocation.project_id, invocation.run_id, invocation.id, os.getpid()))
        try:
            yield
        finally:
            with self.connection() as conn:
                conn.execute("DELETE FROM harness_resource_locks WHERE project_id=? AND run_id=? AND invocation_id=? AND owner_pid=?",
                             (invocation.project_id, invocation.run_id, invocation.id, os.getpid()))

    def recover_interrupted(self, project_id: str) -> list[str]:
        """Only a dead local owner is recoverable; PID reuse may require manual inspection."""
        recovered = []
        for run in self.list(project_id, limit=200):
            if run.owner_pid is None:
                continue
            try:
                os.kill(run.owner_pid, 0)
                continue
            except PermissionError:
                continue
            except ProcessLookupError:
                pass
            def interrupt(current: PipelineRun):
                if current.owner_pid != run.owner_pid:
                    raise HarnessError("RUN_CHANGED", "Run owner changed during recovery")
                current.state = "blocked"
                current.reason = "Worker interrupted; inspect external effects before explicitly retrying"
                current.owner_pid = None
                for step in current.step_runs:
                    if step.rollback_state == "running":
                        step.rollback_state = "uncertain"
                        step.rollback_approved_by = None
                        if step.rollback_attempts:
                            step.rollback_attempts[-1].state = "uncertain"
                            step.rollback_attempts[-1].reason = "Worker interrupted during compensation; inspect external effects"
                            step.rollback_attempts[-1].ended_at = utc_now()
                    if step.state in ("running", "evaluating", "assigned"):
                        step.state, step.reason = "blocked", current.reason
                        if step.attempts:
                            if step.attempts[-1].invocation.metered:
                                current.budget_accounting_complete = False
                            step.attempts[-1].state = "blocked"
                            step.attempts[-1].error_code = "WORKER_INTERRUPTED"
                            step.attempts[-1].error = current.reason
                            step.attempts[-1].ended_at = utc_now()
            self.update(project_id, run.id, interrupt, "harness.run.interrupted")
            recovered.append(run.id)
        return recovered
