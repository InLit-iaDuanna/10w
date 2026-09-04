"""Observable render job state transitions."""

from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set

from .schemas import ExecutionMode, JobFailure, RenderJob, RenderJobState


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ALLOWED_TRANSITIONS: Mapping[RenderJobState, Set[RenderJobState]] = {
    RenderJobState.QUEUED: {
        RenderJobState.RUNNING,
        RenderJobState.FAILED,
        RenderJobState.CANCELLED,
    },
    RenderJobState.RUNNING: {
        RenderJobState.WAITING_APPROVAL,
        RenderJobState.SUCCEEDED,
        RenderJobState.FAILED,
        RenderJobState.CANCELLED,
    },
    RenderJobState.WAITING_APPROVAL: {
        RenderJobState.RUNNING,
        RenderJobState.SUCCEEDED,
        RenderJobState.FAILED,
        RenderJobState.CANCELLED,
    },
    RenderJobState.SUCCEEDED: set(),
    RenderJobState.FAILED: {RenderJobState.QUEUED},
    RenderJobState.CANCELLED: {RenderJobState.QUEUED},
}


def transition_job(
    job: RenderJob,
    state: RenderJobState,
    *,
    progress: Optional[float] = None,
    failure: Optional[JobFailure] = None,
    execution_mode: Optional[ExecutionMode] = None,
    clock: Clock = utc_now,
) -> RenderJob:
    if state not in ALLOWED_TRANSITIONS[job.state]:
        raise ValueError("invalid render job transition: %s -> %s" % (job.state, state))
    if state == RenderJobState.FAILED and failure is None:
        raise ValueError("failure details are required")
    if state != RenderJobState.FAILED and failure is not None:
        raise ValueError("failure details are valid only for failed jobs")

    payload = job.model_dump(mode="python")
    payload.update(
        state=state,
        progress=progress if progress is not None else job.progress,
        failure=failure,
        execution_mode=execution_mode or job.execution_mode,
        updated_at=clock(),
    )
    if state == RenderJobState.SUCCEEDED:
        payload["progress"] = 1.0
    if state == RenderJobState.QUEUED:
        payload["progress"] = 0.0
        payload["attempt"] = job.attempt + 1
    return RenderJob.model_validate(payload)


class RenderJobRepository:
    """Module-owned job repository with deterministic snapshot/restore.

    The composition root can replace this with durable storage. Editor
    visibility never owns or destroys queue state.
    """

    def __init__(self, jobs: Iterable[RenderJob] = ()) -> None:
        self._jobs: Dict[str, RenderJob] = {job.job_id: job for job in jobs}

    def save(self, job: RenderJob) -> RenderJob:
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> RenderJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError("unknown render job: " + job_id) from exc

    def list(self) -> List[RenderJob]:
        return sorted(self._jobs.values(), key=lambda item: (item.created_at, item.job_id))

    def dump_snapshot(self) -> List[dict]:
        return [job.model_dump(mode="json") for job in self.list()]

    @classmethod
    def restore_snapshot(cls, payload: Iterable[dict]) -> "RenderJobRepository":
        return cls(RenderJob.model_validate(item) for item in payload)


class RenderQueue:
    def __init__(self, repository: RenderJobRepository, clock: Clock = utc_now) -> None:
        self._repository = repository
        self._clock = clock

    def enqueue(self, job: RenderJob) -> RenderJob:
        if any(item.job_id == job.job_id for item in self._repository.list()):
            existing = self._repository.get(job.job_id)
            if existing != job:
                raise ValueError("render job ID was reused for different inputs")
            return existing
        if job.state != RenderJobState.QUEUED:
            raise ValueError("new render jobs must be queued")
        return self._repository.save(job)

    def start(self, job_id: str) -> RenderJob:
        return self._move(job_id, RenderJobState.RUNNING)

    def wait_for_approval(self, job_id: str) -> RenderJob:
        return self._move(job_id, RenderJobState.WAITING_APPROVAL)

    def resume(self, job_id: str) -> RenderJob:
        return self._move(job_id, RenderJobState.RUNNING)

    def succeed(self, job_id: str) -> RenderJob:
        return self._move(job_id, RenderJobState.SUCCEEDED)

    def fail(self, job_id: str, failure: JobFailure) -> RenderJob:
        return self._move(job_id, RenderJobState.FAILED, failure=failure)

    def cancel(self, job_id: str) -> RenderJob:
        return self._move(job_id, RenderJobState.CANCELLED)

    def retry(self, job_id: str, execution_mode: Optional[ExecutionMode] = None) -> RenderJob:
        job = self._repository.get(job_id)
        if (
            job.state == RenderJobState.FAILED
            and job.failure is not None
            and not job.failure.retryable
        ):
            raise PermissionError("render job failure is not retryable")
        return self._move(
            job_id,
            RenderJobState.QUEUED,
            execution_mode=execution_mode,
        )

    def progress(self, job_id: str, value: float) -> RenderJob:
        job = self._repository.get(job_id)
        if job.state != RenderJobState.RUNNING:
            raise ValueError("only running jobs accept progress")
        payload = job.model_dump(mode="python")
        payload.update(progress=value, updated_at=self._clock())
        updated = RenderJob.model_validate(payload)
        return self._repository.save(updated)

    def _move(
        self,
        job_id: str,
        state: RenderJobState,
        failure: Optional[JobFailure] = None,
        execution_mode: Optional[ExecutionMode] = None,
    ) -> RenderJob:
        current = self._repository.get(job_id)
        updated = transition_job(
            current,
            state,
            failure=failure,
            execution_mode=execution_mode,
            clock=self._clock,
        )
        return self._repository.save(updated)
