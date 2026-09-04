from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from .service import AIPlaytestService
from .schemas import (
    CancelRunResult,
    PlaytestRun,
    RegressionComparison,
    RunId,
    RunRequest,
    StableId,
)


TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass(frozen=True)
class JobDefinition(Generic[TInput, TOutput]):
    job_id: str
    execute: Callable[[TInput], TOutput]
    cancellable: bool
    resumable: bool
    retryable: bool
    cancel: Optional[Callable[[RunId], CancelRunResult]] = None


@dataclass(frozen=True)
class RegressionJobInput:
    comparison_id: StableId
    baseline_run_id: RunId
    candidate_run_id: RunId


def create_job_definitions(service: AIPlaytestService) -> list:
    return [
        JobDefinition[RunRequest, PlaytestRun](
            job_id="playtest.execute",
            execute=service.run,
            cancellable=True,
            resumable=False,
            retryable=False,
            cancel=service.cancel,
        ),
        JobDefinition[RegressionJobInput, RegressionComparison](
            job_id="playtest.regression.compare",
            execute=lambda item: service.compare(
                item.comparison_id, item.baseline_run_id, item.candidate_run_id
            ),
            cancellable=False,
            resumable=False,
            retryable=True,
        ),
    ]
