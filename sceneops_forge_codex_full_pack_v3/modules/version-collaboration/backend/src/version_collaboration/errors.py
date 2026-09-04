from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    GIT_OFFLINE = "GIT_OFFLINE"
    GIT_DIRTY = "GIT_DIRTY"
    GIT_CONFLICT = "GIT_CONFLICT"
    GIT_COMMAND_FAILED = "GIT_COMMAND_FAILED"
    GIT_TIMEOUT = "GIT_TIMEOUT"
    GIT_CANCELLED = "GIT_CANCELLED"
    PATH_OUTSIDE_PROJECT = "PATH_OUTSIDE_PROJECT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    STALE_BASE = "STALE_BASE"
    LOCK_CONFLICT = "LOCK_CONFLICT"
    LOCK_OWNERSHIP = "LOCK_OWNERSHIP"
    LOCK_RECONCILIATION_REQUIRED = "LOCK_RECONCILIATION_REQUIRED"
    DELETED_TARGET = "DELETED_TARGET"
    INCOMPATIBLE_SCHEMA = "INCOMPATIBLE_SCHEMA"
    INVALID_COMMENT_ANCHOR = "INVALID_COMMENT_ANCHOR"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    NOT_FOUND = "NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"


class VersionCollaborationError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        suggested_actions: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.suggested_actions = suggested_actions

    def as_dict(self, request_id: str) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "request_id": request_id,
            "retryable": self.retryable,
            "suggested_actions": list(self.suggested_actions),
        }
