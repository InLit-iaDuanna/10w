"""Structured adapter errors."""

from typing import Any, Dict, List, Optional


class ComfyAdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        details: Optional[Dict[str, Any]] = None,
        suggested_actions: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.suggested_actions = suggested_actions or []

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
            "suggested_actions": self.suggested_actions,
        }


class TransportFailure(RuntimeError):
    """Low-level network error used only between transport and adapter."""


def offline_error(message: str) -> ComfyAdapterError:
    return ComfyAdapterError(
        "INTEGRATION_OFFLINE",
        message,
        retryable=True,
        suggested_actions=["integration.open", "render.job.retry"],
    )


def timeout_error(prompt_id: str) -> ComfyAdapterError:
    return ComfyAdapterError(
        "INTEGRATION_TIMEOUT",
        "ComfyUI did not finish before the configured deadline.",
        retryable=True,
        details={"prompt_id": prompt_id},
        suggested_actions=["render.job.retry"],
    )


def cancelled_error(prompt_id: str) -> ComfyAdapterError:
    return ComfyAdapterError(
        "RUN_CANCELLED",
        "The ComfyUI prompt was cancelled.",
        retryable=True,
        details={"prompt_id": prompt_id},
        suggested_actions=["render.job.retry"],
    )
