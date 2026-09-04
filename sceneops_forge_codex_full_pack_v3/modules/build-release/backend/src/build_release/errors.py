"""Structured module errors suitable for API error mapping."""

from __future__ import annotations

from typing import Any, Dict, Optional


class BuildReleaseError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable


class NotFoundError(BuildReleaseError):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            "NOT_FOUND",
            f"{entity} was not found.",
            details={"entity": entity, "id": entity_id},
        )


class ConflictError(BuildReleaseError):
    def __init__(self, message: str, *, details: Dict[str, Any]) -> None:
        super().__init__("CONFLICT", message, details=details)


class PolicyError(BuildReleaseError):
    def __init__(self, code: str, message: str, *, details: Dict[str, Any]) -> None:
        super().__init__(code, message, details=details)


class AdapterExecutionError(BuildReleaseError):
    def __init__(self, message: str, *, retryable: bool, details: Dict[str, Any]) -> None:
        super().__init__(
            "DEPLOYMENT_ADAPTER_FAILED",
            message,
            details=details,
            retryable=retryable,
        )
