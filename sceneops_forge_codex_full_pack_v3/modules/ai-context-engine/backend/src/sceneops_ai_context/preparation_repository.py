"""SQLite ownership for idempotent production-preparation records."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .preparation_models import ProductionPreparationRequest, ProductionPreparationResult, utc_now


class PreparationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class PreparationRepository:
    def __init__(self, database: str | Path):
        self.database = str(database)
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS production_preparations (
                    project_id TEXT NOT NULL,
                    request_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reservation_id TEXT NOT NULL,
                    request_body TEXT NOT NULL,
                    result_body TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, request_key)
                )
            """)

    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def claim(self, request: ProductionPreparationRequest, reservation_id: str):
        now = utc_now().isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO production_preparations VALUES(?,?,?,?,?,?,?,?)",
                (request.project_id, request.request_key, "preparing", reservation_id,
                 request.model_dump_json(), None, now, now),
            )
            if cursor.rowcount == 1:
                return "claimed", None
            row = connection.execute(
                "SELECT state,request_body,result_body FROM production_preparations WHERE project_id=? AND request_key=?",
                (request.project_id, request.request_key),
            ).fetchone()
        saved_request = ProductionPreparationRequest.model_validate_json(row["request_body"])
        budget_fields = {"model_call_allowed", "remaining_model_calls", "remaining_time_seconds"}
        if saved_request.model_dump(exclude=budget_fields) != request.model_dump(exclude=budget_fields):
            raise PreparationError("PREPARATION_REQUEST_KEY_CONFLICT",
                "同一 request_key 已用于不同的制作请求，请为新要求使用新的 request_key。", 409)
        if row["state"] == "completed" and row["result_body"]:
            return "completed", ProductionPreparationResult.model_validate_json(row["result_body"])
        return "preparing", None

    def complete(self, result: ProductionPreparationResult, reservation_id: str) -> None:
        now = utc_now().isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE production_preparations
                   SET state='completed',result_body=?,updated_at=?
                   WHERE project_id=? AND request_key=? AND reservation_id=? AND state='preparing'""",
                (result.model_dump_json(), now, result.project_id, result.request_key, reservation_id),
            )
        if cursor.rowcount != 1:
            raise PreparationError("PREPARATION_RESERVATION_LOST", "制作准备记录已由另一个请求完成。", 409)

    def get(self, project_id: str, request_key: str) -> ProductionPreparationResult:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state,result_body FROM production_preparations WHERE project_id=? AND request_key=?",
                (project_id, request_key),
            ).fetchone()
        if row is None:
            raise PreparationError("PREPARATION_NOT_FOUND", "没有找到本次制作准备记录。", 404)
        if row["state"] != "completed" or not row["result_body"]:
            raise PreparationError("PREPARATION_IN_PROGRESS", "本次制作准备正在进行。", 409)
        return ProductionPreparationResult.model_validate_json(row["result_body"])
