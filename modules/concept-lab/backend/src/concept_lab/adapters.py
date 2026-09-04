from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Protocol

from .errors import ConceptLabError
from .generation_schemas import (
    AdapterHealth,
    GenerationCapabilities,
    GenerationOutput,
    GenerationPlan,
    GenerationRequest,
)
from .schemas import ExecutionMode


class ConceptGenerationAdapter(Protocol):
    adapter_id: str

    def health_check(self) -> AdapterHealth: ...

    def capabilities(self) -> GenerationCapabilities: ...

    def dry_run(self, request: GenerationRequest) -> GenerationPlan: ...

    def execute(self, request: GenerationRequest) -> GenerationOutput: ...

    def cancel(self, run_id: str) -> bool: ...


class FixtureGenerationAdapter:
    """Exact fixture replay for honest mock or prior-real-run cached modes."""

    def __init__(self, fixture_path: Path, expected_mode: ExecutionMode) -> None:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.adapter_id = payload["adapter_id"]
        self._expected_mode = expected_mode
        self._capabilities = GenerationCapabilities.model_validate(payload["capabilities"])
        self._outputs: Dict[str, GenerationOutput] = {
            key: GenerationOutput.model_validate(value)
            for key, value in payload["outputs"].items()
        }
        if any(output.execution_mode != expected_mode for output in self._outputs.values()):
            raise ValueError("fixture output mode does not match adapter mode")

    def health_check(self) -> AdapterHealth:
        return AdapterHealth(
            adapter_id=self.adapter_id,
            available=True,
            execution_mode=self._expected_mode,
        )

    def capabilities(self) -> GenerationCapabilities:
        return self._capabilities.model_copy(deep=True)

    def dry_run(self, request: GenerationRequest) -> GenerationPlan:
        self._validate_request(request)
        return GenerationPlan(
            adapter_id=self.adapter_id,
            execution_mode=self._expected_mode,
            requested_views=request.requested_views,
            model=request.model,
            warnings=[
                "Fixture execution only; no external provider is called."
                if self._expected_mode == ExecutionMode.MOCK
                else "Cached contract replay; not a current live execution."
            ],
        )

    def execute(self, request: GenerationRequest) -> GenerationOutput:
        self._validate_request(request)
        return self._outputs[request.fixture_key].model_copy(deep=True)  # type: ignore[index]

    def cancel(self, run_id: str) -> bool:
        # Fixture execution is synchronous, so no in-flight work remains to cancel.
        return False

    def _validate_request(self, request: GenerationRequest) -> None:
        if request.execution_mode != self._expected_mode:
            raise ConceptLabError(
                "EXECUTION_MODE_MISMATCH",
                "Requested mode does not match the configured adapter.",
                details={
                    "requested": request.execution_mode.value,
                    "adapter": self._expected_mode.value,
                },
            )
        if not request.fixture_key or request.fixture_key not in self._outputs:
            raise ConceptLabError(
                "FIXTURE_NOT_FOUND",
                "No deterministic generation fixture matches this request.",
                details={"fixture_key": request.fixture_key},
            )
