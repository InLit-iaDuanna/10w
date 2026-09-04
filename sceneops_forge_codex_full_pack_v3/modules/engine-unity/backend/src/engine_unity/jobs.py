"""Observable state machine for Unity tests and builds."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS = {
    JobState.QUEUED: {JobState.RUNNING, JobState.WAITING_APPROVAL, JobState.CANCELLED},
    JobState.WAITING_APPROVAL: {JobState.QUEUED, JobState.CANCELLED},
    JobState.RUNNING: {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED},
    JobState.FAILED: {JobState.QUEUED},
    JobState.SUCCEEDED: set(),
    JobState.CANCELLED: {JobState.QUEUED},
}


@dataclass
class UnityJob:
    job_id: str
    request_id: str
    state: JobState = JobState.QUEUED
    attempt: int = 0
    max_attempts: int = 1
    log_codes: List[str] = field(default_factory=list)
    failure_code: Optional[str] = None

    def transition(self, target: JobState, log_code: str) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"invalid Unity job transition: {self.state} -> {target}")
        self.state = target
        self.log_codes.append(log_code)
        if target is JobState.RUNNING:
            self.attempt += 1

    def retry(self) -> None:
        if self.state not in {JobState.FAILED, JobState.CANCELLED}:
            raise ValueError("only failed or cancelled Unity jobs can be retried")
        if self.attempt >= self.max_attempts:
            raise ValueError("Unity job retry limit reached")
        self.failure_code = None
        self.transition(JobState.QUEUED, "UNITY_JOB_RETRY_QUEUED")
