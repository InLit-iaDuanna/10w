"""Validation for identifiers and output locators crossing the HTTP boundary."""

from pathlib import PurePosixPath
import re

from .errors import ComfyAdapterError
from .models import OutputDescriptor


PROMPT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def validate_prompt_id(prompt_id: str) -> None:
    if PROMPT_ID_PATTERN.fullmatch(prompt_id) is None:
        raise ComfyAdapterError(
            "PROMPT_ID_REJECTED",
            "ComfyUI prompt ID contains unsafe characters.",
            retryable=False,
        )


def validate_output_descriptor(descriptor: OutputDescriptor) -> None:
    if (
        "/" in descriptor.filename
        or "\\" in descriptor.filename
        or descriptor.filename in {".", ".."}
    ):
        raise ComfyAdapterError(
            "OUTPUT_PATH_REJECTED",
            "ComfyUI output filename must be a basename.",
            retryable=False,
        )
    if "\\" in descriptor.subfolder:
        raise ComfyAdapterError(
            "OUTPUT_PATH_REJECTED",
            "ComfyUI output subfolder must use POSIX separators.",
            retryable=False,
        )
    folder = PurePosixPath(descriptor.subfolder or "safe")
    if folder.is_absolute() or ".." in folder.parts or "." in folder.parts:
        raise ComfyAdapterError(
            "OUTPUT_PATH_REJECTED",
            "ComfyUI output subfolder cannot escape the output root.",
            retryable=False,
        )
