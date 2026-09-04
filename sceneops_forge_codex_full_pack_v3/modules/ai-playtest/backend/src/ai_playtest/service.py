from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from .backpin import BackpinReviewError
from .changesets import propose_change_set
from .ports import (
    CancellationToken,
    PlaytestRunnerAdapter,
    RunAlreadyActiveError,
    RunIdentityConflictError,
)
from .regression import ComparisonIdentityConflictError, RegressionComparator
from .repository import PlaytestRepository
from .restoration import RestoreIssueCommand, create_restore_command
from .runner import AIPlaytestRunner, Clock, StepListener, utc_now
from .schemas import (
    ChangeSetProposal,
    CancelRunResult,
    Issue,
    PlaytestRun,
    RegressionComparison,
    RunId,
    RunRequest,
    StableId,
)


class AIPlaytestService:
    def __init__(
        self,
        adapter: PlaytestRunnerAdapter,
        repository: PlaytestRepository,
        clock: Clock = utc_now,
    ):
        self.repository = repository
        self.clock = clock
        self.runner = AIPlaytestRunner(adapter=adapter, clock=clock)
        self.comparator = RegressionComparator()
        self._active_runs: Dict[str, CancellationToken] = {}
        self._active_runs_lock = Lock()
        self._adapter_execution_lock = Lock()
        self._issue_review_lock = Lock()
        self._comparison_lock = Lock()

    def run(
        self,
        request: RunRequest,
        cancellation: Optional[CancellationToken] = None,
        on_step: Optional[StepListener] = None,
    ) -> PlaytestRun:
        token = cancellation or CancellationToken()
        with self._active_runs_lock:
            existing = self._idempotent_result(request)
            if existing is not None:
                return existing
            if request.run_id in self._active_runs:
                raise RunAlreadyActiveError(
                    f"run {request.run_id} is already active"
                )
            self._active_runs[request.run_id] = token
        try:
            with self._adapter_execution_lock:
                result = self.runner.run(request, token, on_step)
            self.repository.save_run(result)
            return result
        finally:
            with self._active_runs_lock:
                if self._active_runs.get(request.run_id) is token:
                    self._active_runs.pop(request.run_id, None)

    def _idempotent_result(self, request: RunRequest) -> Optional[PlaytestRun]:
        try:
            existing = self.repository.get_run(request.run_id)
        except KeyError:
            return None
        same_request = (
            existing.test_case == request.test_case
            and existing.build == request.build
            and existing.execution_mode == request.execution_mode
            and existing.replay_action_ids == request.replay_action_ids
        )
        if not same_request:
            raise RunIdentityConflictError(
                f"run_id {request.run_id} already belongs to a different request"
            )
        return existing

    def cancel(self, run_id: RunId) -> CancelRunResult:
        with self._active_runs_lock:
            token = self._active_runs.get(run_id)
            if token is None:
                return CancelRunResult(
                    run_id=run_id, accepted=False, status="not_running"
                )
            token.cancel()
        return CancelRunResult(
            run_id=run_id, accepted=True, status="cancel_requested"
        )

    def compare(
        self,
        comparison_id: StableId,
        baseline_run_id: RunId,
        candidate_run_id: RunId,
    ) -> RegressionComparison:
        with self._comparison_lock:
            try:
                existing = self.repository.get_comparison(comparison_id)
            except KeyError:
                existing = None
            if existing is not None:
                if (
                    existing.baseline_run_id == baseline_run_id
                    and existing.candidate_run_id == candidate_run_id
                ):
                    return existing
                raise ComparisonIdentityConflictError(
                    f"comparison_id {comparison_id} already belongs to other runs"
                )
            comparison = self.comparator.compare(
                comparison_id,
                self.repository.get_run(baseline_run_id),
                self.repository.get_run(candidate_run_id),
                self.clock(),
            )
            self.repository.save_comparison(comparison)
            return comparison

    def restore_issue(self, issue_id: str) -> RestoreIssueCommand:
        return create_restore_command(self.repository.get_issue(issue_id))

    def propose_issue_change(self, issue_id: str, **proposal_fields) -> ChangeSetProposal:
        return propose_change_set(
            self.repository.get_issue(issue_id), **proposal_fields
        )

    def get_issue(self, issue_id: str) -> Issue:
        return self.repository.get_issue(issue_id)

    def review_backpin(
        self, issue_id: str, reviewer_id: str, decision: str
    ) -> Issue:
        with self._issue_review_lock:
            issue = self.repository.get_issue(issue_id)
            if decision == "confirm":
                backpin = self.runner.backpin_resolver.confirm(
                    issue.backpin, reviewer_id, self.clock()
                )
            elif decision == "reject":
                backpin = self.runner.backpin_resolver.reject(
                    issue.backpin, reviewer_id, self.clock()
                )
            else:
                raise BackpinReviewError("decision must be confirm or reject")
            review_label = (
                "回钉已由认证用户人工确认。"
                if decision == "confirm"
                else "回钉已由认证用户人工拒绝；原始证据仍可恢复。"
            )
            limitation_labels = [
                label
                for label in issue.limitation_labels
                if not label.startswith("回钉")
            ]
            reviewed = issue.model_copy(
                update={
                    "backpin": backpin,
                    "limitation_labels": [review_label, *limitation_labels],
                }
            )
            self.repository.save_issue(reviewed)
            return reviewed
