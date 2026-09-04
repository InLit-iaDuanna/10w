"""Structured Unity integration errors."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    COMMAND_NOT_ALLOWED = "UNITY_COMMAND_NOT_ALLOWED"
    INVALID_PAYLOAD = "UNITY_INVALID_PAYLOAD"
    PATH_OUTSIDE_PROJECT = "UNITY_PATH_OUTSIDE_PROJECT"
    PROJECT_INVALID = "UNITY_PROJECT_INVALID"
    PERMISSION_DENIED = "UNITY_PERMISSION_DENIED"
    CHANGESET_REQUIRED = "UNITY_CHANGESET_REQUIRED"
    CHANGESET_MISMATCH = "UNITY_CHANGESET_MISMATCH"
    APPROVAL_REQUIRED = "UNITY_APPROVAL_REQUIRED"
    BASE_VERSION_MISMATCH = "UNITY_BASE_VERSION_MISMATCH"
    VERSION_INCOMPATIBLE = "UNITY_VERSION_INCOMPATIBLE"
    INTEGRATION_OFFLINE = "UNITY_INTEGRATION_OFFLINE"
    TIMEOUT = "UNITY_TIMEOUT"
    CANCELLED = "UNITY_CANCELLED"
    RESULT_MISSING = "UNITY_RESULT_MISSING"
    RESULT_INVALID = "UNITY_RESULT_INVALID"
    CACHE_MISS = "UNITY_CACHE_MISS"
    IDEMPOTENCY_CONFLICT = "UNITY_IDEMPOTENCY_CONFLICT"
    COMPILE_FAILED = "UNITY_COMPILE_FAILED"
    TEST_FAILED = "UNITY_TEST_FAILED"
    BUILD_FAILED = "UNITY_BUILD_FAILED"
    MISSING_MATERIAL = "UNITY_MISSING_MATERIAL"
    MISSING_SCRIPT = "UNITY_MISSING_SCRIPT"
    MISSING_REFERENCE = "UNITY_MISSING_REFERENCE"
    IDENTITY_CONFLICT = "UNITY_IDENTITY_CONFLICT"
    ROLLBACK_UNAVAILABLE = "UNITY_ROLLBACK_UNAVAILABLE"


class UnityIntegrationError(RuntimeError):
    """An adapter error that can cross the module boundary safely."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = details or {}
