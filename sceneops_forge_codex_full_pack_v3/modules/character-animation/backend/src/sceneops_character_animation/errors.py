"""Structured domain and adapter errors."""

from typing import Dict, List, Optional


class CharacterAnimationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[Dict[str, object]] = None,
        retryable: bool = False,
        suggested_actions: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.suggested_actions = suggested_actions or []


class IntegrationOfflineError(CharacterAnimationError):
    def __init__(self, integration_id: str, operation: str) -> None:
        super().__init__(
            "INTEGRATION_OFFLINE",
            "{} integration is not connected.".format(integration_id),
            details={"integration_id": integration_id, "operation": operation},
            retryable=True,
            suggested_actions=["integration.open", "run.retry"],
        )


class ApprovalRequiredError(CharacterAnimationError):
    def __init__(self, changeset_id: str) -> None:
        super().__init__(
            "APPROVAL_REQUIRED",
            "ChangeSet requires explicit approval before execution.",
            details={"changeset_id": changeset_id},
            suggested_actions=["changeset.open", "changeset.approve"],
        )


class InvalidVersionError(CharacterAnimationError):
    def __init__(self, message: str, details: Optional[Dict[str, object]] = None) -> None:
        super().__init__("INVALID_VERSION", message, details=details)


class OperationCancelledError(CharacterAnimationError):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            "OPERATION_CANCELLED",
            "Adapter operation was cancelled before execution.",
            details={"request_id": request_id},
        )


class AdapterTimeoutError(CharacterAnimationError):
    def __init__(self, timeout_seconds: float, maximum_seconds: float) -> None:
        super().__init__(
            "ADAPTER_TIMEOUT_INVALID",
            "Requested timeout exceeds the adapter capability.",
            details={"timeout_seconds": timeout_seconds, "maximum_seconds": maximum_seconds},
        )
