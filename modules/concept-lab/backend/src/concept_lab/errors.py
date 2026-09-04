from __future__ import annotations

from typing import Any, Dict, List, Optional


class ConceptLabError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
        suggested_actions: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.suggested_actions = suggested_actions or []


class NotFoundError(ConceptLabError):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            "NOT_FOUND",
            f"{entity} was not found.",
            details={"entity": entity, "id": entity_id},
        )


class ConflictError(ConceptLabError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("VERSION_CONFLICT", message, details=details)


class ReviewGateError(ConceptLabError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(code, message, details=details)


class InvalidTransitionError(ConceptLabError):
    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            "INVALID_STATE_TRANSITION",
            f"Cannot transition from {current} to {requested}.",
            details={"current": current, "requested": requested},
        )
